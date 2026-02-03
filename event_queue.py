"""In-memory FIFO event queue with deduplication and persistent runtime state.

This module provides a simple queue for events received from the WebSocket
stream and persists the last processed `event_id` to
`state/runtime_state.json` for restart safety.
"""

import threading
import queue
import json
import os
import time
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)

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
        """Load persisted runtime state from disk."""
        try:
            if os.path.exists(RUNTIME_STATE):
                with open(RUNTIME_STATE, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                    # Support both old (ball_detection_id) and new (event_id) formats
                    self.last_spoken = data.get("last_spoken_event_id") or data.get("last_spoken_ball_detection_id")
                    self.match_id = data.get("match_id")
                    logger.info(f"Loaded state: match_id={self.match_id}, last_spoken={self.last_spoken}")
        except Exception as e:
            # Ignore corrupt state; start fresh
            logger.warning(f"Failed to load state: {e}, starting fresh")
            self.last_spoken = None

    def _save_state(self):
        """Persist runtime state to disk."""
        try:
            with open(RUNTIME_STATE, "w", encoding="utf-8") as fh:
                json.dump({
                    "last_spoken_event_id": self.last_spoken,
                    "match_id": self.match_id,
                    "last_update": int(time.time())
                }, fh, indent=2)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def enqueue(self, event: Dict):
        """Enqueue an event if not seen before (deduplicate by event_id).
        
        Event payload expected:
        {
            "event_id": "<uuid>",
            "match_id": "<uuid>",
            "batsman_name": "<string>",
            "sentences": "<string>",
            "intensity": "<low|normal|medium|high|extreme>"
        }
        """
        event_id = event.get("event_id")
        if not event_id:
            logger.warning("Event missing event_id, skipping")
            return

        with self.lock:
            # Deduplicate: skip if already processed or seen
            if event_id == self.last_spoken or event_id in self.seen:
                logger.debug(f"Event {event_id} already processed or seen, skipping")
                return
            
            self.seen.add(event_id)

            # Determine priority: lower number = higher priority
            priority = self._determine_priority(event)
            # Use a counter to preserve FIFO order for same-priority items
            self._counter += 1
            self.queue.put((priority, self._counter, time.time(), event))
            logger.info(f"Event enqueued: event_id={event_id}, priority={priority}, queue_size={self.queue.qsize()}")

    def set_match_id(self, match_id: Optional[str]):
        """Set current match_id for persisted state and reset seen set if changed."""
        with self.lock:
            if match_id != self.match_id:
                logger.info(f"Match ID changed: {self.match_id} -> {match_id}")
                self.match_id = match_id
                # reset seen when match changes to avoid cross-match dedupe
                self.seen.clear()
                self.last_spoken = None  # Reset last spoken for new match
                self._save_state()

    def get_next(self, timeout: float = 0.5) -> Optional[Dict]:
        """Get next event from queue with timeout.
        
        Returns:
            Event dict or None if timeout
        """
        try:
            item = self.queue.get(timeout=timeout)
            # item is (priority, counter, enqueue_ts, event)
            return item[3]
        except queue.Empty:
            return None

    def mark_processed(self, event_id: str):
        """Mark the event processed: update last_spoken and persist state."""
        with self.lock:
            self.last_spoken = event_id
            # keep a small seen set to avoid unbounded growth
            self.seen = {s for s in self.seen if s == event_id}
            self._save_state()
            logger.debug(f"Event marked processed: {event_id}")

    def _determine_priority(self, event: Dict) -> int:
        """Determine priority based on event content.
        
        Priority levels:
        - 0: System announcements (highest)
        - 1: Wickets / Special events
        - 2: Normal ball events (default)
        
        Returns lower numbers for higher-priority events.
        """
        # Check for explicit priority field first
        if "priority" in event:
            return int(event["priority"])
        
        # Check sentences for announcement keywords
        sentences = event.get("sentences", "").upper()
        if any(keyword in sentences for keyword in ["ANNOUNCEMENT", "WELCOME", "BREAK", "END", "SYSTEM"]):
            return 0
        
        # Check for wicket/special indicators
        if any(keyword in sentences for keyword in ["WICKET", "OUT", "BOWLED", "CAUGHT", "SPECIAL"]):
            return 1
        
        # Default: normal event
        return 2

    def get_last_spoken(self) -> Optional[str]:
        """Get the last spoken event_id for missed events fetch."""
        return self.last_spoken
    
    def get_queue_size(self) -> int:
        """Get current queue size."""
        return self.queue.qsize()