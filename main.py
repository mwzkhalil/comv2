import time
import signal
import sys
import logging
from typing import Optional

from config import polling_config, api_config
from audio_manager import AudioManager
from commentary import CommentaryGenerator
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
    
    def __init__(self):
        logger.info("Initializing Cricket Commentator...")
        
        # Initialize components
        self.db = DatabaseManager()
        self.api = CricketAPIClient()
        self.audio = AudioManager()
        self.commentary_gen = CommentaryGenerator()
        self.state_mgr = MatchStateManager()
        self.event_queue = EventQueue()
        self.ws_client = WSClient(self.event_queue)
        
        # Runtime control
        self.running = False
        
        if api_config.use_dummy_mode:
            logger.warning("RUNNING IN DUMMY MODE - Using mock API and Database data")
            # In production, dummy mode should not be enabled
        if api_config.speak_only_deliveries:
            logger.info("DELIVERY-ONLY MODE - Speaking only database sentences")
        logger.info("Cricket Commentator initialized")
    
    def setup(self) -> bool:
        logger.info("Setting up subsystems...")
        
        if not self.db.test_connection():
            logger.error("Database connection failed")
            return False
        
        if not self.audio.start_background_sfx():
            logger.warning("Background SFX not available, continuing without it")
        
        self.audio.start_playback_loop()
        # Start WebSocket streaming client if configured
        if api_config.use_ws_streaming:
            # attempt an initial match poll to get match_id/slot
            try:
                self._poll_match()
                state = self.state_mgr.get_state()
                match_id = str(state.slot_id) if state.slot_id else None
                if match_id:
                    self.ws_client.start(match_id=match_id)
                else:
                    logger.info("No active match to subscribe to yet; WS client will wait")
            except Exception:
                logger.exception("Failed to start WS client")
        
        logger.info("All subsystems ready")
        return True
    
    def run(self):
        logger.info("=" * 60)
        logger.info("INDOOR CRICKET LIVE COMMENTATOR - STARTED")
        logger.info("Database-Driven Commentary (sentence + intensity)")
        logger.info("Using Deliveries Table")
        if api_config.use_dummy_mode:
            logger.info("MODE: TEST (Mock API Data)")
        logger.info("=" * 60)
        
        self.running = True
        
        while self.running:
            try:
                if not self._poll_match():
                    time.sleep(polling_config.error_retry_interval)
                    continue
                
                state = self.state_mgr.get_state()
                
                if not state.is_match_active():
                    time.sleep(polling_config.match_state_interval)
                    continue
                
                if not self._poll_innings():
                    time.sleep(polling_config.error_retry_interval)
                    continue
                
                self._handle_match_phase()
                
            except KeyboardInterrupt:
                logger.info("Received shutdown signal")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                time.sleep(polling_config.error_retry_interval)
        
        logger.info("Commentary loop stopped")
    
    def _poll_match(self) -> bool:
        match_data = self.api.fetch_current_match()
        if not match_data:
            return False
        
        state = self.state_mgr.get_state()
        is_new = state.update_from_api(match_data)
        
        if is_new:
            logger.info(f"NEW MATCH: {state.team_one_name} vs {state.team_two_name}")
            # If streaming is enabled, set match_id and (re)start WS client
            if api_config.use_ws_streaming:
                # backend may provide a uuid-style match_id, fall back to slot_id
                match_identifier = match_data.get("match_id") or match_data.get("slot_id") or state.slot_id
                try:
                    self.event_queue.set_match_id(str(match_identifier) if match_identifier is not None else None)
                    self.ws_client.start(match_id=str(match_identifier))
                    logger.info(f"WS client subscribed to match {match_identifier}")
                except Exception:
                    logger.exception("Failed to start/subscribe WS client for new match")
        
        return True
    
    def _poll_innings(self) -> bool:
        state = self.state_mgr.get_state()
        
        innings_data = self.api.fetch_innings_state(state.slot_id)
        if not innings_data:
            return False
        
        state.update_innings_status(innings_data)
        return True
    
    def _handle_match_phase(self):
        """Handle current match phase based on innings status."""
        state = self.state_mgr.get_state()
        
        # Skip announcements if configured to speak only deliveries
        if api_config.speak_only_deliveries:
            # Only poll deliveries during live innings
            if state.is_innings_live():
                self._poll_deliveries()
                time.sleep(polling_config.deliveries_interval)
            else:
                # Just mark announcements as done without speaking
                if state.should_announce_welcome():
                    state.mark_welcome_announced()
                    logger.info("Skipping welcome announcement (speak_only_deliveries=True)")
                elif state.should_announce_break():
                    state.mark_break_announced()
                    logger.info("Skipping innings break announcement (speak_only_deliveries=True)")
                elif state.should_announce_end():
                    state.mark_end_announced()
                    logger.info("Skipping match end announcement (speak_only_deliveries=True)")
                time.sleep(polling_config.match_state_interval)
            return
        
        # Normal flow with all announcements
        if state.should_announce_welcome():
            self._announce_welcome()
            time.sleep(polling_config.match_state_interval)
        
        elif state.is_innings_live():
            if api_config.use_ws_streaming:
                # Process any queued events from the stream
                self._process_stream_events()
                time.sleep(polling_config.deliveries_interval)
            else:
                self._poll_deliveries()
                time.sleep(polling_config.deliveries_interval)
        
        elif state.should_announce_break():
            self._announce_innings_break()
            time.sleep(polling_config.innings_break_sleep)
        
        elif state.should_announce_end():
            self._announce_match_end()
            time.sleep(polling_config.match_end_sleep)
        
        else:
            time.sleep(polling_config.match_state_interval)
    
    def _announce_welcome(self):
        state = self.state_mgr.get_state()
        text, excitement = self.commentary_gen.generate_welcome(
            state.team_one_name,
            state.team_two_name
        )
        # System announcements are highest priority (0)
        try:
            self.audio.default_priority = 0
            self.audio.queue_commentary(text, excitement)
        finally:
            self.audio.default_priority = 2
        state.mark_welcome_announced()
        logger.info("Welcome announcement queued")
    
    def _announce_innings_break(self):
        """Announce innings break."""
        state = self.state_mgr.get_state()
        text, excitement = self.commentary_gen.generate_innings_break()
        try:
            self.audio.default_priority = 0
            self.audio.queue_commentary(text, excitement)
        finally:
            self.audio.default_priority = 2
        state.mark_break_announced()
        logger.info("Innings break announcement queued")
    
    def _announce_match_end(self):
        """Announce match end with winner."""
        state = self.state_mgr.get_state()
        winner = state.get_winner_name()
        text, excitement = self.commentary_gen.generate_match_end(winner)
        try:
            self.audio.default_priority = 0
            self.audio.queue_commentary(text, excitement)
        finally:
            self.audio.default_priority = 2
        state.mark_end_announced()
        logger.info(f"Match end announcement queued - Winner: {winner}")
    
    def _poll_deliveries(self):
        """Poll and process new ball deliveries."""
        state = self.state_mgr.get_state()
        
        deliveries = self.db.get_new_deliveries(
            state.last_seen_event_id,
            state.slot_id,
            state.last_seen_ball_timestamp
        )
        
        for delivery in deliveries:
            event_id = delivery.get("event_id")
            
            # Get commentary from database sentence field
            commentary_text, excitement = self.commentary_gen.generate(delivery)
            
            # Queue for playback
            self.audio.queue_commentary(commentary_text, excitement)
            
            # Update state
            state.update_last_event_id(event_id)
            # Update last seen timestamp from DB delivered value
            ts = delivery.get("ball_timestamp")
            state.update_last_seen_timestamp(ts)
            
            logger.info(
                f"Ball #{event_id}: {commentary_text} "
                f"(intensity={delivery.get('intensity')}, excitement={excitement})"
            )

    def _process_stream_events(self):
        """Consume events from the in-memory event queue (WebSocket stream)."""
        while True:
            ev = self.event_queue.get_next(timeout=0.2)
            if not ev:
                break

            # Event payload authoritative: sentences must be used as-is
            text = ev.get("sentences") or ""
            # Simple excitement heuristic (can be refined)
            excitement = 5 if "ANNOUNCEMENT" in (text or "").upper() else 3

            # Determine priority similar to EventQueue
            bid = ev.get("ball_detection_id") or ""
            parts = bid.split("_")
            ev_type = parts[2].lower() if len(parts) >= 3 else None
            if ev_type in ("announcement", "system"):
                priority = 0
            elif ev_type in ("wicket", "special"):
                priority = 1
            else:
                priority = 2

            # Use audio default_priority temporarily to pass priority through
            try:
                self.audio.default_priority = priority
                self.audio.queue_commentary(text, excitement)
            finally:
                self.audio.default_priority = 2

            if bid:
                self.event_queue.mark_processed(bid)
                logger.info(f"Spoken event {bid}: {text[:80]}")
    
    def shutdown(self):
        """Graceful shutdown of all subsystems."""
        logger.info("Shutting down commentator...")
        self.running = False
        
        # Stop audio
        self.audio.stop()
        # Stop websocket client
        try:
            self.ws_client.stop()
        except Exception:
            pass
        
        # Close API client
        self.api.close()
        
        logger.info("Commentator shutdown complete")


def signal_handler(sig, frame):
    """Handle shutdown signals."""
    logger.info("\nReceived interrupt signal, shutting down...")
    sys.exit(0)


def main():
    """Main entry point."""
    # Setup signal handlers
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
    finally:
        commentator.shutdown()


if __name__ == "__main__":
    main()
