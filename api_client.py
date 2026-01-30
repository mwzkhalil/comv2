"""API client for cricket match backend services."""

import requests
from typing import Optional, Dict
from datetime import datetime
import logging

from config import api_config, match_config

logger = logging.getLogger(__name__)


class CricketAPIClient:
    """Client for interacting with cricket match backend APIs."""
    
    def __init__(self):
        """Initialize API client."""
        self.config = api_config
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Indoor-Cricket-Commentator/1.0'
        })
    
    def get_booking_url(self) -> str:
        """Construct booking API URL."""
        return f"{self.config.base_url}{self.config.booking_endpoint}"
    
    def get_innings_url(self) -> str:
        """Construct innings API URL."""
        return f"{self.config.base_url}{self.config.innings_endpoint}"
    
    def fetch_current_match(self, custom_hour: Optional[int] = None) -> Optional[Dict]:
        """
        Fetch current match booking by time slot.
        
        Args:
            custom_hour: Override default time slot hour (default: 21:00)
            
        Returns:
            Match dictionary or None if not found
        """
        try:
            now = datetime.now()
            hour = custom_hour if custom_hour is not None else match_config.default_time_hour
            ts = now.replace(
                hour=hour, 
                minute=match_config.default_time_minute, 
                second=0, 
                microsecond=0
            )
            # timestamp_str = ts.strftime("%Y-%m-%dT%H:%M:%S")
            timestamp_str = ts.strftime("%Y-%m-%dT15:00:00")
            
            url = self.get_booking_url()
            params = {"timestamp": timestamp_str}
            
            logger.info(f"Fetching match for time: {timestamp_str}")
            response = self.session.get(url, params=params, timeout=self.config.timeout)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get("message") == "Successfully fetched Match Slot":
                match = data.get("match", {})
                logger.info(f"Match found: {match.get('teamOneName')} vs {match.get('teamTwoName')}")
                return self._enrich_match_data(match)
            else:
                logger.warning(f"No match found for timestamp {timestamp_str}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"API request error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching match: {e}")
            return None
    
    def fetch_innings_state(self, match_id: int) -> Optional[Dict]:
        """
        Fetch current innings state for a match.
        
        Args:
            match_id: Match slot_id
            
        Returns:
            Innings state dictionary or None
        """
        try:
            url = self.get_innings_url()
            params = {"match_id": match_id}
            
            response = self.session.get(url, params=params, timeout=self.config.timeout)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get("message") == "Successfully fetched Innings":
                innings = data.get("innings", {})
                inning_status = innings.get("inning")
                logger.debug(f"Innings status: {inning_status}")
                return data
            else:
                logger.warning(f"Failed to fetch innings for match {match_id}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"Innings API error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching innings: {e}")
            return None
    
    def _enrich_match_data(self, match: Dict) -> Dict:
        """
        Enrich match data with computed fields.
        
        Args:
            match: Raw match dictionary from API
            
        Returns:
            Enriched match dictionary with batting/bowling teams
        """
        # Determine batting and bowling teams
        team_one_batting = match.get("teamOneInnings") == "Batting First"
        
        match["batting_team"] = (
            match.get("teamOneName", "Team 1") if team_one_batting 
            else match.get("teamTwoName", "Team 2")
        )
        match["bowling_team"] = (
            match.get("teamTwoName", "Team 2") if team_one_batting 
            else match.get("teamOneName", "Team 1")
        )
        
        return match
    
    def close(self):
        """Close the API client session."""
        self.session.close()
        logger.info("API client session closed")
