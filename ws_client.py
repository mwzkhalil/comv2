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

from config import api_config, ws_config

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
        ws_url = f"{ws_url}{ws_config.ws_endpoint_template.format(match_id=self.match_id)}"

        backoff = ws_config.reconnect_backoff_initial
        while not self._stop.is_set():
            try:
                logger.info(f"Connecting to WS: {ws_url}")

                def _on_message(ws, message):
                    try:
                        ev = json.loads(message)
                        event_id = ev.get("event_id")
                        if event_id:
                            logger.info(f"Event received: event_id={event_id}, match_id={ev.get('match_id')}")
                        self.event_queue.enqueue(ev)
                    except Exception as e:
                        logger.error(f"Malformed WS message: {e}")

                def _on_close(ws, close_status_code, close_msg):
                    logger.warning(f"WS connection closed: {close_status_code} {close_msg}")

                def _on_error(ws, error):
                    logger.error(f"WS error: {error}")

                headers = {}
                if ws_config.ws_auth_token:
                    headers[ws_config.ws_auth_header] = f"Bearer {ws_config.ws_auth_token}"

                wsapp = websocket.WebSocketApp(
                    ws_url,
                    on_message=_on_message,
                    on_close=_on_close,
                    on_error=_on_error,
                    header=headers if headers else None,
                )

                # Before running, attempt to fetch missed events (safe to call repeatedly)
                self._fetch_missed_events()

                wsapp.run_forever(
                    ping_interval=ws_config.ping_interval,
                    ping_timeout=ws_config.ping_timeout
                )

            except Exception as e:
                logger.error(f"WS error: {e}")

            # Exponential backoff on reconnect
            if self._stop.is_set():
                break
            logger.info(f"Reconnecting in {backoff:.1f}s...")
            time.sleep(backoff)
            backoff = min(backoff * ws_config.reconnect_backoff_multiplier, ws_config.reconnect_backoff_max)

    def _fetch_missed_events(self):
        """Fetch missed events from REST endpoint on reconnect."""
        last = self.event_queue.get_last_spoken()
        try:
            url = api_config.base_url.rstrip("/") + api_config.missed_events_endpoint
            params = {"match_id": self.match_id}
            if last:
                params["after_id"] = last

            logger.info(f"Fetching missed events: match_id={self.match_id}, after_id={last}")
            resp = requests.get(url, params=params, timeout=api_config.timeout)
            if resp.status_code == 200:
                items = resp.json() or []
                logger.info(f"Fetched {len(items)} missed events")
                for ev in items:
                    self.event_queue.enqueue(ev)
            else:
                logger.warning(f"Missed events endpoint returned {resp.status_code}")
        except Exception as e:
            logger.warning(f"Failed to fetch missed events: {e}")
