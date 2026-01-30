"""Database operations for cricket match data."""

import pymysql
from pymysql.cursors import DictCursor
from typing import List, Dict, Optional
from contextlib import contextmanager
import logging

from config import db_config, api_config
from api_client import CricketAPIClient
import datetime
from config import polling_config

logger = logging.getLogger(__name__)


class DatabaseManager:

    def __init__(self):
        self.config = db_config
        # API client will be created on demand when booking check is required
        self._api_client: Optional[CricketAPIClient] = None

    @contextmanager
    def get_connection(self):
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

    # -------------------------------------------------
    # FETCH DELIVERIES (SOURCE OF COMMENTARY)
    # -------------------------------------------------

    def get_new_deliveries(
        self,
        last_event_id: int,
        match_id: str,
        last_seen_timestamp=None
    ) -> List[Dict]:
        """
        Fetch deliveries for commentary.

        Behavior:
        - Check booking API first. If a booking exists:
          - If `last_event_id` is not set (<=0) bootstrap with recent deliveries.
          - Otherwise return deliveries with `event_id > last_event_id` or
            `ball_timestamp > last_seen_timestamp` (if provided).
        - If no booking exists, fall back to returning deliveries that have a
          non-null `sentence` and `event_id > last_event_id`.
        """
        try:
            # Check booking (API-driven) to determine live status
            client = CricketAPIClient()
            booking = client.fetch_current_match()
            client.close()

            if booking:
                # Bootstrap: return last N deliveries if we don't have a last_event_id
                if not last_event_id or last_event_id <= 0:
                    return self.get_recent_deliveries(match_id, limit=6)

                # When we have a last_event_id, prefer strict event_id-based
                # selection, but allow selecting by timestamp if a last seen
                # timestamp exists (prevents missing very-new rows).
                with self.get_connection() as conn:
                    with conn.cursor() as cur:
                        if last_seen_timestamp:
                            query_new = """
                                SELECT
                                    event_id,
                                    ball_id,
                                    match_id,
                                    batsman_id,
                                    ball_hit,
                                    ball_timestamp,
                                    runs_scored,
                                    hit_type,
                                    frame_number,
                                    sentence,
                                    intensity
                                FROM Deliveries
                                WHERE match_id = %s
                                  AND (
                                      event_id > %s
                                      OR ball_timestamp > %s
                                  )
                                ORDER BY event_id ASC
                            """
                            cur.execute(query_new, (match_id, last_event_id, last_seen_timestamp))
                        else:
                            query_new = """
                                SELECT
                                    event_id,
                                    ball_id,
                                    match_id,
                                    batsman_id,
                                    ball_hit,
                                    ball_timestamp,
                                    runs_scored,
                                    hit_type,
                                    frame_number,
                                    sentence,
                                    intensity
                                FROM Deliveries
                                WHERE event_id > %s
                                  AND match_id = %s
                                ORDER BY event_id ASC
                            """
                            cur.execute(query_new, (last_event_id, match_id))

                        rows = cur.fetchall()
                        logger.info(f"Fetched {len(rows)} live deliveries after event_id={last_event_id}")
                        return rows

            # No booking: return only deliveries that have non-null sentences
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    query = """
                        SELECT
                            event_id,
                            ball_id,
                            match_id,
                            batsman_id,
                            ball_hit,
                            ball_timestamp,
                            runs_scored,
                            hit_type,
                            frame_number,
                            sentence,
                            intensity
                        FROM Deliveries
                        WHERE event_id > %s
                          AND match_id = %s
                          AND sentence IS NOT NULL
                        ORDER BY event_id ASC
                    """
                    cur.execute(query, (last_event_id, match_id))
                    rows = cur.fetchall()

                    logger.info(
                        f"Fetched {len(rows)} deliveries after event_id={last_event_id}"
                    )
                    return rows
        except Exception as e:
            logger.error(f"Error fetching deliveries: {e}")
            return []

    def get_recent_deliveries(self, match_id: str, limit: int = 6) -> List[Dict]:
        """
        Fetch the most recent `limit` deliveries for a match (including NULL sentences).
        Results are returned in chronological order (oldest -> newest).
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    query = """
                        SELECT
                            event_id,
                            ball_id,
                            match_id,
                            batsman_id,
                            ball_hit,
                            ball_timestamp,
                            runs_scored,
                            hit_type,
                            frame_number,
                            sentence,
                            intensity
                        FROM Deliveries
                        WHERE match_id = %s
                        ORDER BY event_id DESC
                        LIMIT %s
                    """
                    cur.execute(query, (match_id, limit))
                    rows = cur.fetchall()

                    # rows are returned newest->oldest; reverse to chronological
                    rows.reverse()

                    logger.info(f"Fetched {len(rows)} recent deliveries for match={match_id}")
                    return rows
        except Exception as e:
            logger.error(f"Error fetching recent deliveries: {e}")
            return []

    # -------------------------------------------------
    # OPTIONAL: SAVE AUDIO HISTORY (NON-BLOCKING)
    # -------------------------------------------------

    def save_commentary_audio_history(
        self,
        ball_id: str,
        match_id: str,
        audio_path: str,
        duration: float = None
    ):
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    query = """
                        INSERT INTO CommentaryAudioHistory
                        (ball_id, match_id, audio_path, duration_seconds)
                        VALUES (%s, %s, %s, %s)
                    """
                    cur.execute(query, (ball_id, match_id, audio_path, duration))
                    conn.commit()
        except Exception as e:
            logger.error(f"Error saving commentary audio history: {e}")

    # -------------------------------------------------
    # MATCH SUMMARY
    # -------------------------------------------------

    def get_match_summary(self, match_id: str) -> Optional[Dict]:
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    query = """
                        SELECT
                            match_id,
                            COUNT(*) AS total_balls,
                            SUM(CASE WHEN runs_scored = -1 THEN 1 ELSE 0 END) AS wickets,
                            SUM(CASE WHEN runs_scored >= 0 THEN runs_scored ELSE 0 END) AS total_runs
                        FROM Deliveries
                        WHERE match_id = %s
                        GROUP BY match_id
                    """
                    cur.execute(query, (match_id,))
                    return cur.fetchone()
        except Exception as e:
            logger.error(f"Error fetching match summary: {e}")
            return None

    # -------------------------------------------------
    # HEALTH CHECK
    # -------------------------------------------------

    def test_connection(self) -> bool:
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    return cur.fetchone() is not None
        except Exception:
            return False
