"""Configuration settings for the Indoor Cricket Commentary System."""

import os
from dataclasses import dataclass

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv not installed, will use system env vars only
    pass


@dataclass
class DatabaseConfig:
    """MySQL database configuration."""
    host: str = os.getenv("MYSQL_HOST", "192.168.18.120")
    port: int = int(os.getenv("MYSQL_PORT", "3306"))
    user: str = os.getenv("MYSQL_USER", "mahwiz")
    password: str = os.getenv("MYSQL_PASSWORD", "")
    database: str = os.getenv("MYSQL_DATABASE", "IndoorCricket")
    pool_size: int = 5
    pool_recycle: int = 3600


@dataclass
class APIConfig:
    """Backend API endpoints configuration."""
    base_url: str = os.getenv("API_BASE_URL", "http://192.168.18.120:8000")
    booking_endpoint: str = "/bookings/get_booking_by_time/"
    innings_endpoint: str = "/innings/get_innings"
    timeout: int = int(os.getenv("API_TIMEOUT", "10"))
    use_dummy_mode: bool = os.getenv("USE_DUMMY_MODE", "true").lower() == "true"
    speak_only_deliveries: bool = os.getenv("SPEAK_ONLY_DELIVERIES", "true").lower() == "true"


@dataclass
class AudioConfig:
    """Audio processing and playback configuration."""
    sampling_rate: int = 22050
    background_volume: float = 0.30
    ducked_volume: float = 0.08
    duck_fade_steps: int = 10
    duck_fade_delay: float = 0.02
    sfx_file: str = "./downloads/crowd_of.wav"
    commentary_bg_file: str = "./background_audio/crowd_of_22050.wav"  # For commentary mixing
    mixer_buffer: int = 512
    mixer_channels: int = 2
    commentary_channel: int = 0
    sfx_channel: int = 1


@dataclass
class ElevenLabsConfig:
    """ElevenLabs TTS API configuration."""
    api_key: str = os.getenv("ELEVENLABS_API_KEY", "")
    voice_id: str = os.getenv("ELEVENLABS_VOICE_ID", "PSk5GhCjavRcRMo6NtjK")
    model_id: str = "eleven_multilingual_v2"
    output_format: str = "mp3_22050_32"
    
    # Excitement-based voice settings
    stability_calm: float = 0.5
    stability_medium: float = 0.3
    stability_excited: float = 0.15
    similarity_boost: float = 0.9
    style_calm: float = 0.7
    style_excited: float = 0.9
    speed_calm: float = 0.9
    speed_medium: float = 0.95
    speed_excited: float = 1.0
    use_speaker_boost: bool = True


@dataclass
class PollingConfig:
    """Polling intervals for various operations."""
    deliveries_interval: float = 0.4
    match_state_interval: float = 3.0
    error_retry_interval: float = 5.0
    innings_break_sleep: float = 8.0
    match_end_sleep: float = 15.0
    # Consider deliveries with a ball_timestamp within this many seconds as "recent".
    deliveries_recent_seconds: int = int(os.getenv("DELIVERIES_RECENT_SECONDS", "10"))


@dataclass
class MatchConfig:
    """Match-specific configuration."""
    default_time_hour: int = 21  # 21:00 - 9 PM
    default_time_minute: int = 0


# Global configuration instances
db_config = DatabaseConfig()
api_config = APIConfig()
audio_config = AudioConfig()
tts_config = ElevenLabsConfig()
polling_config = PollingConfig()
match_config = MatchConfig()
