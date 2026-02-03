# Indoor Cricket Live Commentary System

Real-time cricket match commentator that receives live commentary events via WebSocket and plays them with TTS (ElevenLabs) and persistent crowd sound effects. All commentary text is provided by an external system via WebSocket.

## Features

- **WebSocket Streaming** - Real-time event reception via WebSocket (no database polling)
- **TTS Playback** - ElevenLabs streaming TTS with emotion/intensity mapping
- **Persistent Crowd SFX** - Continuous background audio that never restarts per event
- **Smart Ducking** - Background audio automatically ducks during commentary
- **Priority Queue** - System announcements > Wickets/Special > Normal events
- **Audio Saving** - Generated audio (TTS + SFX) saved to disk and database
- **Restart-Safe** - Automatic missed events catch-up on reconnect
- **Low Latency** - Non-blocking audio processing with real-time streaming

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              External Commentary System                     │
│              (Event Publisher)                              │
└──────────────────────┬──────────────────────────────────────┘
                       │ WebSocket
                       │ /ws/live-commentary/{match_id}
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              Commentary Engine (This System)                │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   │
│  │ WebSocket    │───▶│ Event Queue  │───▶│ Audio        │   │
│  │ Client       │    │ (Priority +  │    │ Manager      │   │
│  │              │    │  Dedupe)     │    │ (TTS + SFX)  │   │
│  └──────────────┘    └──────────────┘    └──────────────┘   │
│         │                    │                    │         │
│         │                    │                    ▼         │
│         │                    │            ┌──────────────┐  │
│         │                    │            │   Speakers   │  │
│         │                    │            └──────────────┘  │
│         │                    │                              │
│         │                    ▼                              │
│         │            ┌──────────────┐                       │
│         │            │ Runtime State│                       │
│         │            │ (Persisted)  │                       │
│         │            └──────────────┘                       │
│         │                                                   │
│         └───────────▶ Database (Audio History Only)         │
└─────────────────────────────────────────────────────────────┘
```

## Key Components

- **`main.py`** - Main orchestrator, event processing loop, metrics tracking
- **`ws_client.py`** - WebSocket client with auto-reconnect and missed events catch-up
- **`event_queue.py`** - Priority queue with deduplication and state persistence
- **`audio_manager.py`** - TTS streaming, crowd SFX mixing, ducking, audio saving
- **`config.py`** - Centralized configuration (no hardcoding elsewhere)
- **`database.py`** - Database operations (audio history saving only)
- **`commentary.py`** - Intensity → excitement mapping (no text generation)
- **`state_manager.py`** - Match state tracking (teams, innings status)
- **`api_client.py`** - Backend API client (match status checking)

## Event Payload Structure

All events from the external system must conform to this schema:

```json
{
  "event_id": "<uuid>",
  "match_id": "<uuid>",
  "batsman_name": "<string>",
  "sentences": "<string>",
  "intensity": "<low|normal|medium|high|extreme>"
}
```

**Field Descriptions:**
- `event_id`: Unique event identifier (used for deduplication)
- `match_id`: Match identifier
- `batsman_name`: Batsman name (optional, for metadata)
- `sentences`: **Authoritative commentary text** (must not be modified)
- `intensity`: Voice emotion level (maps to TTS excitement)

**⚠️ Important:** The `sentences` field is the single source of commentary text. The system does NOT generate or modify commentary text.

## Priority System

Events are processed in priority order:

- **Priority 0** (Highest): System announcements (welcome, break, end)
- **Priority 1** (High): Wickets and special events
- **Priority 2** (Normal): Regular ball events

Higher priority events preempt lower priority playback.

## Intensity Mapping

The `intensity` field maps to TTS voice excitement:

| Intensity | Excitement | Voice Characteristics |
|-----------|------------|----------------------|
| `low` | 2 | Calm, stable voice |
| `normal` | 5 | Standard voice |
| `medium` | 7 | Engaged voice |
| `high` | 9 | Excited voice |
| `extreme` | 10 | Maximum excitement |

## Installation

### Prerequisites

- Python 3.8+
- MySQL database (for audio history saving)
- ffmpeg (for audio processing, optional)

### Setup

```bash
# Clone/navigate to project directory
cd comv2

# Install Python dependencies
pip install -r requirements.txt

# Install ffmpeg (Ubuntu/Debian)
sudo apt-get install ffmpeg

# Or macOS
brew install ffmpeg

# Create directories
mkdir -p background_audio audio_history state

# Place crowd SFX file
# Add crowd_of_22050.wav to background_audio/ directory
```

## Configuration

### Environment Variables

Create a `.env` file or set environment variables:

```bash
# Backend API
API_BASE_URL=http://192.168.18.120:8000

# WebSocket (required)
USE_WS_STREAMING=true  # Default: true

# TTS (ElevenLabs)
ELEVENLABS_API_KEY=your_api_key_here
ELEVENLABS_VOICE_ID=PSk5GhCjavRcRMo6NtjK

# Audio Settings
SAVE_AUDIO=true  # Save audio files (default: true)
AUDIO_STORAGE_PATH=./audio_history  # Where to save audio files
AUDIO_FORMAT=wav  # wav or mp3
AUDIO_TTS_TIMEOUT=8  # TTS stream timeout in seconds

# Database (for audio history)
MYSQL_HOST=192.168.18.120
MYSQL_PORT=3306
MYSQL_USER=mahwiz
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=IndoorCricket

# WebSocket Authentication (optional)
WS_AUTH_TOKEN=your_token_here
```

All configuration defaults are defined in `config.py`. **Never hardcode configuration values elsewhere.**

## Usage

### Run the Commentator

```bash
# Set required environment variables
export API_BASE_URL="http://your.backend:8000"
export ELEVENLABS_API_KEY="your_key"

# Run
python main.py
```

### Logs

- **Console**: INFO level logging
- **File**: `cricket_commentary.log` (detailed logging)

### Metrics

The system tracks:
- Events received/spoken/skipped
- Audio latency (event → queue → playback)
- Queue depth
- Final metrics summary on shutdown

## Runtime State

Runtime state is persisted in `state/runtime_state.json`:

```json
{
  "last_spoken_event_id": "<uuid>",
  "match_id": "<uuid>",
  "last_update": 1670000000
}
```

This enables:
- **Restart Safety**: System resumes from last spoken event
- **Missed Events**: On reconnect, fetches missed events via REST API
- **Deduplication**: Prevents repeating events after restart

## Audio Saving

When `SAVE_AUDIO=true` (default), the system:

1. **Mixes TTS + Background SFX** - Creates final audio with ducked crowd ambience
2. **Saves to Disk** - Files saved to `audio_history/` directory (configurable)
3. **Saves to Database** - Metadata saved to `CommentaryAudioHistory` table

**Database Schema:**
```sql
CREATE TABLE CommentaryAudioHistory (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ball_id VARCHAR(50) NOT NULL,
    match_id VARCHAR(50) NOT NULL,
    audio_path VARCHAR(255) NOT NULL,
    duration_seconds FLOAT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## WebSocket Endpoints

### Connection
- **URL**: `ws://<API_BASE_URL>/ws/live-commentary/{match_id}`
- **Protocol**: WebSocket
- **Authentication**: Optional (via `WS_AUTH_TOKEN` header)

### Missed Events (REST)
- **Endpoint**: `GET /commentary/missed-events`
- **Parameters**: 
  - `match_id`: Match identifier
  - `after_id`: Last spoken event_id (optional)

## Reconnection Behavior

The WebSocket client automatically:

1. **Detects Disconnection** - Monitors connection health
2. **Exponential Backoff** - Reconnects with increasing delays (1s → 2s → 4s → ... → max 30s)
3. **Fetches Missed Events** - Calls REST endpoint before resuming stream
4. **Resumes Streaming** - Continues from last spoken event

## Persistent Crowd SFX

- **Starts Once**: Background audio starts at application startup
- **Never Restarts**: Continues looping throughout the match
- **Smart Ducking**: Automatically ducks during commentary playback
- **Volume Control**: 
  - Normal: 30% volume
  - Ducking: 8% volume (during TTS)

## File Structure

```
comv2/
├── main.py                 # Main orchestrator
├── ws_client.py            # WebSocket client
├── event_queue.py          # Event queue with priority
├── audio_manager.py        # TTS + SFX playback
├── config.py              # Configuration
├── database.py             # Database operations
├── commentary.py           # Intensity mapping
├── state_manager.py        # Match state
├── api_client.py           # Backend API
├── requirements.txt        # Python dependencies
├── state/
│   └── runtime_state.json  # Persisted runtime state
├── background_audio/
│   └── crowd_of_22050.wav # Background SFX
└── audio_history/          # Saved audio files
```

## Next Steps

Potential enhancements:
- Prometheus metrics endpoint
- Integration test harness
- Performance profiling and optimization
- Enhanced error recovery
- Monitoring dashboard
