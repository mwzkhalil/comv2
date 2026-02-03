"""
Indoor Cricket Live Commentary System - WebSocket Streaming Mode

This system receives commentary events via WebSocket and plays them with TTS
and persistent crowd SFX. All commentary text comes from the external system.
"""

import time
import signal
import sys
import logging
from typing import Optional

from config import api_config, queue_config, audio_config
from audio_manager import AudioManager
from commentary import CommentaryGenerator  # For intensity mapping only
from state_manager import MatchStateManager
from api_client import CricketAPIClient
from database import DatabaseManager
from event_queue import EventQueue
from ws_client import WSClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('cricket_commentary.log')
    ]
)

logger = logging.getLogger(__name__)


class CricketCommentator:
    """Main commentator orchestrator - WebSocket streaming mode only."""
    
    def __init__(self):
        logger.info("Initializing Cricket Commentator (WebSocket Streaming Mode)...")
        
        # Initialize components
        self.db = DatabaseManager()
        self.api = CricketAPIClient()
        self.audio = AudioManager(db_manager=self.db)  # Pass DB for audio saving
        self.commentary_gen = CommentaryGenerator()  # For intensity mapping only
        self.state_mgr = MatchStateManager()
        self.event_queue = EventQueue()
        self.ws_client = WSClient(self.event_queue)
        
        # Runtime control
        self.running = False
        
        # Metrics tracking
        self.metrics = {
            "events_received": 0,
            "events_spoken": 0,
            "events_skipped": 0,
            "audio_latencies": []
        }
        
        logger.info("Cricket Commentator initialized")
    
    def setup(self) -> bool:
        """Setup all subsystems."""
        logger.info("Setting up subsystems...")
        
        # Test database connection (needed for audio history saving)
        if not self.db.test_connection():
            logger.warning("Database connection failed - audio history saving disabled")
        else:
            logger.info("Database connection successful")
        
        # Start persistent background SFX and audio engine
        if not self.audio.start_background_sfx():
            logger.warning("Background SFX not available, continuing without it")
        
        self.audio.start_playback_loop()
        logger.info("Audio engine started with persistent crowd SFX")
        
        # Attempt to get initial match_id for WebSocket subscription
        try:
            match_data = self.api.fetch_current_match()
            if match_data:
                state = self.state_mgr.get_state()
                state.update_from_api(match_data)
                match_id = match_data.get("match_id") or match_data.get("slot_id") or state.slot_id
                if match_id:
                    match_id_str = str(match_id)
                    self.event_queue.set_match_id(match_id_str)
                    self.ws_client.start(match_id=match_id_str)
                    logger.info(f"WebSocket client subscribed to match: {match_id_str}")
                else:
                    logger.info("No active match found - WebSocket will start when match is available")
            else:
                logger.info("No match data available - WebSocket will start when match is available")
        except Exception as e:
            logger.warning(f"Failed to get initial match: {e} - will retry in main loop")
        
        logger.info("All subsystems ready")
        return True
    
    def run(self):
        """Main event processing loop."""
        logger.info("=" * 60)
        logger.info("INDOOR CRICKET LIVE COMMENTATOR - STARTED")
        logger.info("Mode: WebSocket Streaming (No DB Polling)")
        logger.info("Commentary: External System via WebSocket")
        logger.info("Audio: TTS + Persistent Crowd SFX")
        logger.info("=" * 60)
        
        self.running = True
        last_match_poll = 0
        match_poll_interval = 30  # Poll for match changes every 30 seconds
        
        while self.running:
            try:
                # Periodically check for match changes (for WebSocket reconnection)
                current_time = time.time()
                if current_time - last_match_poll > match_poll_interval:
                    self._check_match_status()
                    last_match_poll = current_time
                
                # Process events from WebSocket queue
                self._process_stream_events()
                
                # Small sleep to prevent CPU spinning
                time.sleep(queue_config.event_processing_interval)
                
            except KeyboardInterrupt:
                logger.info("Received shutdown signal")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                time.sleep(1)  # Brief pause on error
        
        logger.info("Commentary loop stopped")
        self._log_metrics()
    
    def _check_match_status(self):
        """Periodically check for match status changes."""
        try:
            match_data = self.api.fetch_current_match()
            if not match_data:
                return
            
            state = self.state_mgr.get_state()
            is_new = state.update_from_api(match_data)
            
            if is_new:
                logger.info(f"NEW MATCH: {state.team_one_name} vs {state.team_two_name}")
            
            # Update WebSocket subscription if match_id changed
            match_id = match_data.get("match_id") or match_data.get("slot_id") or state.slot_id
            if match_id:
                match_id_str = str(match_id)
                current_match_id = self.event_queue.match_id
                if match_id_str != current_match_id:
                    logger.info(f"Match ID changed: {current_match_id} -> {match_id_str}")
                    self.event_queue.set_match_id(match_id_str)
                    self.ws_client.start(match_id=match_id_str)
        except Exception as e:
            logger.debug(f"Error checking match status: {e}")
    
    def _process_stream_events(self):
        """Process events from WebSocket queue.
        
        Event payload format:
        {
            "event_id": "<uuid>",
            "match_id": "<uuid>",
            "batsman_name": "<string>",
            "sentences": "<string>",  # Authoritative commentary text
            "intensity": "<low|normal|medium|high|extreme>"
        }
        """
        processed_count = 0
        max_per_iteration = 10  # Process up to 10 events per iteration
        
        while processed_count < max_per_iteration:
            ev = self.event_queue.get_next(timeout=queue_config.queue_timeout)
            if not ev:
                break
            
            self.metrics["events_received"] += 1
            event_id = ev.get("event_id")
            
            if not event_id:
                logger.warning("Event missing event_id, skipping")
                continue
            
            # Extract commentary text (authoritative - do not modify)
            text = ev.get("sentences", "").strip()
            if not text:
                logger.warning(f"Event {event_id} has empty sentences, skipping")
                self.event_queue.mark_processed(event_id)
                self.metrics["events_skipped"] += 1
                continue
            
            # Map intensity to excitement level
            intensity = ev.get("intensity", "normal").lower().strip()
            excitement = self.commentary_gen.INTENSITY_MAP.get(intensity, 5)
            
            # Determine priority (EventQueue already determined, but we can override)
            priority = ev.get("priority")
            if priority is None:
                # Fallback priority determination
                sentences_upper = text.upper()
                if any(kw in sentences_upper for kw in ["ANNOUNCEMENT", "WELCOME", "BREAK", "END", "SYSTEM"]):
                    priority = 0
                elif any(kw in sentences_upper for kw in ["WICKET", "OUT", "BOWLED", "CAUGHT", "SPECIAL"]):
                    priority = 1
                else:
                    priority = 2
            
            # Queue for playback with metadata
            event_start_time = time.time()
            self.audio.queue_commentary(
                text=text,
                excitement=excitement,
                priority=priority,
                event_id=event_id,
                match_id=ev.get("match_id"),
                batsman_name=ev.get("batsman_name"),
                intensity=intensity
            )
            
            # Mark as processed
            self.event_queue.mark_processed(event_id)
            self.metrics["events_spoken"] += 1
            
            # Calculate latency (event received -> queued)
            latency_ms = (time.time() - event_start_time) * 1000
            self.metrics["audio_latencies"].append(latency_ms)
            if len(self.metrics["audio_latencies"]) > 1000:
                self.metrics["audio_latencies"] = self.metrics["audio_latencies"][-1000:]
            
            logger.info(
                f"Event processed: event_id={event_id}, "
                f"intensity={intensity}, excitement={excitement}, "
                f"priority={priority}, latency={latency_ms:.1f}ms, "
                f"text={text[:60]}..."
            )
            
            processed_count += 1
    
    def _log_metrics(self):
        """Log final metrics summary."""
        if self.metrics["audio_latencies"]:
            avg_latency = sum(self.metrics["audio_latencies"]) / len(self.metrics["audio_latencies"])
            max_latency = max(self.metrics["audio_latencies"])
            min_latency = min(self.metrics["audio_latencies"])
        else:
            avg_latency = max_latency = min_latency = 0
        
        logger.info("=" * 60)
        logger.info("METRICS SUMMARY")
        logger.info(f"Events received: {self.metrics['events_received']}")
        logger.info(f"Events spoken: {self.metrics['events_spoken']}")
        logger.info(f"Events skipped: {self.metrics['events_skipped']}")
        logger.info(f"Audio latency - avg: {avg_latency:.1f}ms, min: {min_latency:.1f}ms, max: {max_latency:.1f}ms")
        logger.info(f"Queue size: {self.event_queue.get_queue_size()}")
        logger.info("=" * 60)
    
    def shutdown(self):
        """Graceful shutdown of all subsystems."""
        logger.info("Shutting down commentator...")
        self.running = False
        
        # Stop WebSocket client
        try:
            self.ws_client.stop()
            logger.info("WebSocket client stopped")
        except Exception as e:
            logger.error(f"Error stopping WebSocket client: {e}")
        
        # Stop audio (this will finish current playback)
        try:
            self.audio.stop()
            logger.info("Audio engine stopped")
        except Exception as e:
            logger.error(f"Error stopping audio engine: {e}")
        
        # Close API client
        try:
            self.api.close()
        except Exception as e:
            logger.error(f"Error closing API client: {e}")
        
        # Log final metrics
        self._log_metrics()
        
        logger.info("Commentator shutdown complete")


def signal_handler(sig, frame):
    """Handle shutdown signals gracefully."""
    logger.info("\nReceived interrupt signal, shutting down gracefully...")
    # The main loop will handle cleanup via shutdown()
    sys.exit(0)


def main():
    """Main entry point."""
    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create and run commentator
    commentator = CricketCommentator()
    
    if not commentator.setup():
        logger.error("Setup failed, exiting")
        sys.exit(1)
    
    try:
        commentator.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        commentator.shutdown()


if __name__ == "__main__":
    main()
