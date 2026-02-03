"""WebSocket client that subscribes to live commentary events and enqueues them.

This uses `websocket-client` (WebSocketApp) and falls back to requesting
missed events on reconnect using the REST `missed-events` endpoint.
"""

import threading
import json
import time
import logging
from typing import Optional

import requests
import websocket

from config import api_config

logger = logging.getLogger(__name__)


class WSClient:
    def __init__(self, event_queue, match_id: Optional[str] = None):
        self.event_queue = event_queue
        self.match_id = match_id
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def start(self, match_id: Optional[str] = None):
        if match_id:
            self.match_id = match_id

        if not self.match_id:
            logger.warning("WSClient start called without match_id")
            return

        # If already running for the same match, nothing to do
        if self._thread and self._thread.is_alive():
            if self.match_id == match_id or match_id is None:
                return
            # If match_id changed, stop existing client and restart
            self.stop()

        # Clear stop flag and start new thread
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="WSClient")
        self._thread.start()

    def stop(self):
        self._stop.set()
        # join the thread to ensure clean shutdown
        if self._thread and self._thread.is_alive():
            try:
                self._thread.join(timeout=5)
            except Exception:
                pass
        self._thread = None

    def _run(self):
        base = api_config.base_url.rstrip("/")
        ws_url = base.replace("http://", "ws://").replace("https://", "wss://")
        ws_url = f"{ws_url}/ws/live-commentary/{self.match_id}"

        backoff = 1
        while not self._stop.is_set():
            try:
                logger.info(f"Connecting to WS: {ws_url}")

                def _on_message(ws, message):
                    try:
                        ev = json.loads(message)
                        self.event_queue.enqueue(ev)
                        logger.debug(f"Event enqueued: {ev.get('ball_detection_id')}")
                    except Exception as e:
                        logger.error(f"Malformed WS message: {e}")

                def _on_close(ws, close_status_code, close_msg):
                    logger.warning(f"WS connection closed: {close_status_code} {close_msg}")

                wsapp = websocket.WebSocketApp(
                    ws_url,
                    on_message=_on_message,
                    on_close=_on_close,
                )

                # Before running, attempt to fetch missed events (safe to call repeatedly)
                self._fetch_missed_events()

                wsapp.run_forever(ping_interval=30, ping_timeout=10)

            except Exception as e:
                logger.error(f"WS error: {e}")

            # Exponential backoff on reconnect
            if self._stop.is_set():
                break
            time.sleep(backoff)
            backoff = min(backoff * 2, 30)

    def _fetch_missed_events(self):
        last = self.event_queue.get_last_spoken()
        try:
            url = api_config.base_url.rstrip("/") + "/commentary/missed-events"
            params = {"match_id": self.match_id}
            if last:
                params["after_id"] = last

            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                items = resp.json() or []
                logger.info(f"Fetched {len(items)} missed events")
                for ev in items:
                    self.event_queue.enqueue(ev)
        except Exception as e:
            logger.debug(f"Failed to fetch missed events: {e}")
