"""Match state management with proper encapsulation."""

from typing import Optional, Dict
from dataclasses import dataclass, field
import logging
import datetime

logger = logging.getLogger(__name__)


@dataclass
class MatchState:
    """Encapsulates all match state information."""
    
    slot_id: Optional[int] = None
    team_one_name: str = "Team 1"
    team_two_name: str = "Team 2"
    team_one_id: Optional[int] = None
    team_two_id: Optional[int] = None
    team_one_runs: int = 0
    team_two_runs: int = 0
    winner_id: Optional[int] = None
    batting_team: Optional[str] = None
    bowling_team: Optional[str] = None
    innings_status: Optional[str] = None
    
    # Event tracking
    last_seen_event_id: int = 0
    # Timestamp of the last seen delivery (ball_timestamp)
    last_seen_ball_timestamp: Optional[datetime.datetime] = None
    
    # Announcement flags
    match_started_announced: bool = False
    innings_break_announced: bool = False
    match_ended_announced: bool = False
    
    def update_from_api(self, match_data: Dict) -> bool:
        """
        Update state from API match data.
        
        Args:
            match_data: Match dictionary from API
            
        Returns:
            True if this is a new match (slot_id changed)
        """
        new_slot_id = match_data.get("slot_id")
        is_new_match = (new_slot_id != self.slot_id)
        
        if is_new_match:
            logger.info(f"New match detected: slot_id {self.slot_id} -> {new_slot_id}")
            self.reset_for_new_match()
        
        self.slot_id = new_slot_id
        self.team_one_name = match_data.get("teamOneName", "Team 1")
        self.team_two_name = match_data.get("teamTwoName", "Team 2")
        self.team_one_id = match_data.get("teamOneId")
        self.team_two_id = match_data.get("teamTwoId")
        self.team_one_runs = match_data.get("teamOneRuns", 0)
        self.team_two_runs = match_data.get("teamTwoRuns", 0)
        self.winner_id = match_data.get("winnerId")
        self.batting_team = match_data.get("batting_team")
        self.bowling_team = match_data.get("bowling_team")
        
        return is_new_match
    
    def update_innings_status(self, innings_data: Dict) -> bool:
        """
        Update innings status from API data.
        
        Args:
            innings_data: Innings dictionary from API
            
        Returns:
            True if innings status changed
        """
        innings = innings_data.get("innings", {})
        new_status = innings.get("inning")
        
        changed = (new_status != self.innings_status)
        if changed:
            logger.info(f"Innings status changed: {self.innings_status} -> {new_status}")
        
        self.innings_status = new_status
        return changed
    
    def reset_for_new_match(self):
        """Reset announcement flags and event tracking for new match."""
        self.last_seen_event_id = 0
        self.match_started_announced = False
        self.innings_break_announced = False
        self.match_ended_announced = False
        logger.info("Match state reset for new match")
    
    def update_last_event_id(self, event_id: int):
        """Update the last seen event ID."""
        self.last_seen_event_id = event_id

    def update_last_seen_timestamp(self, ts):
        """Update last seen ball timestamp. Accepts datetime or string."""
        if ts is None:
            return

        if isinstance(ts, str):
            try:
                # Attempt to parse ISO-like string
                parsed = datetime.datetime.fromisoformat(ts)
            except Exception:
                return
            self.last_seen_ball_timestamp = parsed
        elif isinstance(ts, datetime.datetime):
            self.last_seen_ball_timestamp = ts
        else:
            # Unsupported type
            return
    
    def get_winner_name(self) -> str:
        """
        Get the winner team name.
        
        Returns:
            Winner team name or "Draw" if no winner
        """
        if not self.winner_id:
            return "Draw"
        
        if self.winner_id == self.team_one_id:
            return self.team_one_name
        elif self.winner_id == self.team_two_id:
            return self.team_two_name
        else:
            return "Draw"
    
    def is_match_active(self) -> bool:
        """Check if match is currently active."""
        return self.slot_id is not None
    
    def is_innings_live(self) -> bool:
        """Check if innings is currently live."""
        return self.innings_status in ("Innings 1", "Innings 2")
    
    def should_announce_welcome(self) -> bool:
        """Check if welcome announcement should be made."""
        return (
            self.innings_status == "To Begin" and 
            not self.match_started_announced
        )
    
    def should_announce_break(self) -> bool:
        """Check if innings break announcement should be made."""
        return (
            self.innings_status == "Innings Break" and 
            not self.innings_break_announced
        )
    
    def should_announce_end(self) -> bool:
        """Check if match end announcement should be made."""
        return (
            self.innings_status == "End Innings" and 
            not self.match_ended_announced
        )
    
    def mark_welcome_announced(self):
        """Mark welcome announcement as completed."""
        self.match_started_announced = True
        logger.debug("Welcome announcement marked as completed")
    
    def mark_break_announced(self):
        """Mark innings break announcement as completed."""
        self.innings_break_announced = True
        logger.debug("Break announcement marked as completed")
    
    def mark_end_announced(self):
        """Mark match end announcement as completed."""
        self.match_ended_announced = True
        logger.debug("End announcement marked as completed")
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"MatchState(slot_id={self.slot_id}, "
            f"{self.team_one_name} vs {self.team_two_name}, "
            f"status={self.innings_status}, "
            f"last_event={self.last_seen_event_id})"
        )


class MatchStateManager:
    """Manages match state lifecycle."""
    
    def __init__(self):
        """Initialize match state manager."""
        self.state = MatchState()
        logger.info("Match state manager initialized")
    
    def get_state(self) -> MatchState:
        """Get current match state."""
        return self.state
    
    def reset(self):
        """Reset to initial state."""
        self.state = MatchState()
        logger.info("Match state manager reset")
