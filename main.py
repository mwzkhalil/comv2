import time
import signal
import sys
import logging
from typing import Optional

from config import polling_config, api_config
from audio_manager import AudioManager
from commentary import CommentaryGenerator
from state_manager import MatchStateManager
from dummy_api_client import get_api_client
from dummy_database import get_database_manager

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
        self.db = get_database_manager(use_dummy=api_config.use_dummy_mode)
        self.api = get_api_client(use_dummy=api_config.use_dummy_mode)
        self.audio = AudioManager()
        self.commentary_gen = CommentaryGenerator()
        self.state_mgr = MatchStateManager()
        
        # Runtime control
        self.running = False
        
        if api_config.use_dummy_mode:
            logger.warning("⚠️  RUNNING IN DUMMY MODE - Using mock API and Database data")
        if api_config.speak_only_deliveries:
            logger.info("📢 DELIVERY-ONLY MODE - Speaking only database sentences")
        
        logger.info("Cricket Commentator initialized")
    
    def setup(self) -> bool:
        logger.info("Setting up subsystems...")
        
        if not self.db.test_connection():
            logger.error("Database connection failed")
            return False
        
        if not self.audio.start_background_sfx():
            logger.warning("Background SFX not available, continuing without it")
        
        self.audio.start_playback_loop()
        
        logger.info("All subsystems ready")
        return True
    
    def run(self):
        logger.info("=" * 60)
        logger.info("INDOOR CRICKET LIVE COMMENTATOR - STARTED")
        logger.info("Database-Driven Commentary (sentence + intensity)")
        logger.info("Using Deliveries Table")
        if api_config.use_dummy_mode:
            logger.info("🧪 MODE: DUMMY/TEST (Mock API Data)")
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
        self.audio.queue_commentary(text, excitement)
        state.mark_welcome_announced()
        logger.info("Welcome announcement queued")
    
    def _announce_innings_break(self):
        """Announce innings break."""
        state = self.state_mgr.get_state()
        text, excitement = self.commentary_gen.generate_innings_break()
        self.audio.queue_commentary(text, excitement)
        state.mark_break_announced()
        logger.info("Innings break announcement queued")
    
    def _announce_match_end(self):
        """Announce match end with winner."""
        state = self.state_mgr.get_state()
        winner = state.get_winner_name()
        text, excitement = self.commentary_gen.generate_match_end(winner)
        self.audio.queue_commentary(text, excitement)
        state.mark_end_announced()
        logger.info(f"Match end announcement queued - Winner: {winner}")
    
    def _poll_deliveries(self):
        """Poll and process new ball deliveries."""
        state = self.state_mgr.get_state()
        
        deliveries = self.db.get_new_deliveries(
            state.last_seen_event_id,
            state.slot_id
        )
        
        for delivery in deliveries:
            event_id = delivery.get("event_id")
            
            # Get commentary from database sentence field
            commentary_text, excitement = self.commentary_gen.generate(delivery)
            
            # Queue for playback
            self.audio.queue_commentary(commentary_text, excitement)
            
            # Update state
            state.update_last_event_id(event_id)
            
            logger.info(
                f"Ball #{event_id}: {commentary_text} "
                f"(intensity={delivery.get('intensity')}, excitement={excitement})"
            )
    
    def shutdown(self):
        """Graceful shutdown of all subsystems."""
        logger.info("Shutting down commentator...")
        self.running = False
        
        # Stop audio
        self.audio.stop()
        
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
