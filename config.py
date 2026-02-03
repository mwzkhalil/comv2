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
    missed_events_endpoint: str = "/commentary/missed-events"
    timeout: int = int(os.getenv("API_TIMEOUT", "10"))
    use_dummy_mode: bool = os.getenv("USE_DUMMY_MODE", "true").lower() == "true"
    speak_only_deliveries: bool = os.getenv("SPEAK_ONLY_DELIVERIES", "true").lower() == "true"
    # Use WebSocket streaming client for live events (now default and required)
    use_ws_streaming: bool = os.getenv("USE_WS_STREAMING", "true").lower() == "true"


@dataclass
class WebSocketConfig:
    """WebSocket connection configuration."""
    ws_endpoint_template: str = "/ws/live-commentary/{match_id}"
    ping_interval: int = 30  # seconds
    ping_timeout: int = 10  # seconds
    reconnect_backoff_initial: float = 1.0  # seconds
    reconnect_backoff_max: float = 30.0  # seconds
    reconnect_backoff_multiplier: float = 2.0
    # Optional authentication
    ws_auth_token: str = os.getenv("WS_AUTH_TOKEN", "")
    ws_auth_header: str = "Authorization"


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
    # Timeout (seconds) to wait for TTS streaming chunks before treating as failed
    tts_stream_timeout: int = int(os.getenv("AUDIO_TTS_TIMEOUT", "8"))
    # Audio saving configuration
    save_audio: bool = os.getenv("SAVE_AUDIO", "true").lower() == "true"
    audio_storage_path: str = os.getenv("AUDIO_STORAGE_PATH", "./audio_history")
    audio_format: str = os.getenv("AUDIO_FORMAT", "wav")  # wav, mp3
    audio_sample_rate: int = 22050
    audio_channels: int = 1


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
class QueueConfig:
    """Event queue configuration."""
    queue_timeout: float = 0.5  # seconds to wait for next event
    max_queue_size: int = 1000  # maximum events in queue
    event_processing_interval: float = 0.1  # seconds between event processing checks


@dataclass
class MatchConfig:
    """Match-specific configuration."""
    default_time_hour: int = 21  # 21:00 - 9 PM
    default_time_minute: int = 0


# Global configuration instances
db_config = DatabaseConfig()
api_config = APIConfig()
ws_config = WebSocketConfig()
audio_config = AudioConfig()
tts_config = ElevenLabsConfig()
queue_config = QueueConfig()
match_config = MatchConfig()
