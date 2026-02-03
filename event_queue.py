"""In-memory FIFO event queue with deduplication and persistent runtime state.

This module provides a simple queue for events received from the WebSocket
stream and persists the last processed `ball_detection_id` to
`state/runtime_state.json` for restart safety.
"""

import threading
import queue
import json
import os
import time
from typing import Optional, Dict

RUNTIME_STATE = os.path.join("state", "runtime_state.json")


class EventQueue:
    def __init__(self):
        os.makedirs(os.path.dirname(RUNTIME_STATE), exist_ok=True)
        # Use PriorityQueue to allow priority-based ordering
        self.queue = queue.PriorityQueue()
        self.seen = set()
        self.lock = threading.Lock()
        self.last_spoken: Optional[str] = None
        self.match_id: Optional[str] = None
        self._load_state()
        self._counter = 0

    def _load_state(self):
        try:
            if os.path.exists(RUNTIME_STATE):
                with open(RUNTIME_STATE, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                    self.last_spoken = data.get("last_spoken_ball_detection_id")
                    self.match_id = data.get("match_id")
        except Exception:
            # Ignore corrupt state; start fresh
            self.last_spoken = None

    def _save_state(self):
        try:
            with open(RUNTIME_STATE, "w", encoding="utf-8") as fh:
                json.dump({
                    "last_spoken_ball_detection_id": self.last_spoken,
                    "match_id": self.match_id,
                    "last_update": int(time.time())
                }, fh)
        except Exception:
            pass

    def enqueue(self, event: Dict):
        """Enqueue an event if not seen before (deduplicate by ball_detection_id)."""
        bid = event.get("ball_detection_id")
        if not bid:
            return

        with self.lock:
            if bid == self.last_spoken or bid in self.seen:
                return
            self.seen.add(bid)

            # Determine priority: lower number = higher priority
            priority = self._determine_priority(event)
            # Use a counter to preserve FIFO order for same-priority items
            self._counter += 1
            self.queue.put((priority, self._counter, event))

    def set_match_id(self, match_id: Optional[str]):
        """Set current match_id for persisted state and reset seen set if changed."""
        with self.lock:
            if match_id != self.match_id:
                self.match_id = match_id
                # reset seen when match changes to avoid cross-match dedupe
                self.seen.clear()
                self._save_state()

    def get_next(self, timeout: float = 0.5) -> Optional[Dict]:
        try:
            item = self.queue.get(timeout=timeout)
            # item is (priority, counter, event)
            return item[2]
        except queue.Empty:
            return None

    def mark_processed(self, ball_detection_id: str):
        """Mark the event processed: update last_spoken and persist state."""
        with self.lock:
            self.last_spoken = ball_detection_id
            # keep a small seen set to avoid unbounded growth
            self.seen = {s for s in self.seen if s == ball_detection_id}
            self._save_state()

    def _determine_priority(self, event: Dict) -> int:
        """Determine priority based on event type encoded in ball_detection_id.

        Returns lower numbers for higher-priority events.
        """
        bid = event.get("ball_detection_id", "") or ""
        # Attempt to parse structure like: special_event_<type>_<ts>
        parts = bid.split("_")
        ev_type = None
        if len(parts) >= 3:
            ev_type = parts[2].lower()

        if ev_type in ("announcement", "system"):
            return 0
        if ev_type in ("wicket", "special"):
            return 1
        return 2

    def get_last_spoken(self) -> Optional[str]:
        return self.last_spoken
