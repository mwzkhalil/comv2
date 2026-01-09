"""Database operations for cricket match data."""

import pymysql
from pymysql.cursors import DictCursor
from typing import List, Dict, Optional
from contextlib import contextmanager
import logging

from config import db_config

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages MySQL database connections and queries."""
    
    def __init__(self):
        """Initialize database manager."""
        self.config = db_config
        
    @contextmanager
    def get_connection(self):
        """
        Context manager for database connections.
        Ensures proper connection cleanup.
        
        Yields:
            pymysql.Connection: Database connection
        """
        conn = None
        try:
            conn = pymysql.connect(
                host=self.config.host,
                port=self.config.port,
                user=self.config.user,
                password=self.config.password,
                database=self.config.database,
                cursorclass=DictCursor,
                connect_timeout=10,
                read_timeout=10,
                write_timeout=10
            )
            yield conn
        except pymysql.Error as e:
            logger.error(f"Database connection error: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def get_new_deliveries(self, last_event_id: int, match_id: int) -> List[Dict]:
        """
        Fetch new ball delivery events with commentary from DeliveryAudio table.
        
        Args:
            last_event_id: The last processed event_id
            match_id: Current match slot_id
            
        Returns:
            List of delivery event dictionaries with commentary
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    query = """
                        SELECT 
                            da.audio_id,
                            da.event_id,
                            da.delivery_id,
                            da.match_id,
                            da.sentence,
                            da.intensity,
                            da.audio_file_path,
                            da.audio_generated_at,
                            da.audio_duration_seconds,
                            da.status,
                            d.d_id,
                            d.line,
                            d.b_length,
                            d.speed,
                            d.shot_outcome
                        FROM DeliveryAudio da
                        INNER JOIN Deliveries d ON da.delivery_id = d.d_id
                        WHERE da.event_id > %s AND da.match_id = %s
                        ORDER BY da.event_id ASC
                    """
                    cur.execute(query, (last_event_id, match_id))
                    rows = cur.fetchall()
                    logger.debug(f"Fetched {len(rows)} new deliveries from DeliveryAudio")
                    return rows
        except Exception as e:
            logger.error(f"Error fetching deliveries: {e}")
            return []
    
    def save_audio_path(self, event_id: int, audio_path: str, duration: float = None):
        """
        Save the audio file path for a delivery event in DeliveryAudio table.
        
        Args:
            event_id: The delivery event_id
            audio_path: Path to the generated audio file
            duration: Audio duration in seconds (optional)
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    query = """
                        UPDATE DeliveryAudio 
                        SET audio_file_path = %s,
                            audio_generated_at = NOW(),
                            audio_duration_seconds = %s,
                            status = 'generated',
                            updatedAt = NOW()
                        WHERE event_id = %s
                    """
                    cur.execute(query, (audio_path, duration, event_id))
                    conn.commit()
                    logger.debug(f"Saved audio path for event {event_id}: {audio_path}")
        except Exception as e:
            logger.error(f"Error saving audio path: {e}")
    
    def mark_audio_played(self, event_id: int):
        """
        Mark audio as played and increment play count.
        
        Args:
            event_id: The delivery event_id
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    query = """
                        UPDATE DeliveryAudio 
                        SET status = 'played',
                            play_count = play_count + 1,
                            last_played_at = NOW(),
                            updatedAt = NOW()
                        WHERE event_id = %s
                    """
                    cur.execute(query, (event_id,))
                    conn.commit()
                    logger.debug(f"Marked event {event_id} as played")
        except Exception as e:
            logger.error(f"Error marking audio as played: {e}")
    
    def get_match_summary(self, match_id: int) -> Optional[Dict]:
        """
        Fetch match summary information.
        
        Args:
            match_id: Match slot_id
            
        Returns:
            Match summary dictionary or None
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    query = """
                        SELECT 
                            match_id,
                            COUNT(*) as total_balls,
                            SUM(CASE WHEN runs_scored = -1 THEN 1 ELSE 0 END) as wickets,
                            SUM(CASE WHEN runs_scored >= 0 THEN runs_scored ELSE 0 END) as total_runs
                        FROM Deliveries
                        WHERE match_id = %s
                        GROUP BY match_id
                    """
                    cur.execute(query, (match_id,))
                    return cur.fetchone()
        except Exception as e:
            logger.error(f"Error fetching match summary: {e}")
            return None
    
    def test_connection(self) -> bool:
        """
        Test database connectivity.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    result = cur.fetchone()
                    logger.info("Database connection test successful")
                    return result is not None
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False
