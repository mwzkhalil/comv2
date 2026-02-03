# Indoor Cricket Live Commentary System

Real-time cricket match commentator that generates live audio commentary with crowd sound effects using pre-generated commentary from the database.

## Features

- **Commentary** - Uses pre-generated commentary from MySQL `sentence` field
- **Audio Streaming** - In-memory TTS playback (no disk writes for better performance)
- **Background SFX** - Automatic crowd sound effects with smart ducking
- **MySQL Integration** - Polls live match data from Deliveries table
- **Intensity-Based Dynamics** - Voice modulation based on database `intensity` field (low/normal/medium/high/extreme)

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  API Client │────▶│ State Manager│────▶│  Database   │
└─────────────┘     └──────────────┘     └─────────────┘
       │                    │                    │
       ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────┐
│              Main Commentator Loop                  |
└─────────────────────────────────────────────────────┘
       │                    │                    │
       ▼                    ▼                    ▼
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│ Commentary  │────▶│ Audio Manager│────▶│  Speakers   │
│  Generator  │     │  (Streaming) │     │             │
└─────────────┘     └──────────────┘     └─────────────┘
```

## Installation

### Prerequisites
- Python 3.8+
- MySQL database
- ffmpeg (for audio conversion)

### Setup

```bash
# Clone/navigate to project directory
cd cricket_comp

# Install Python dependencies
pip install -r requirements.txt

# Install ffmpeg (Ubuntu/Debian)
sudo apt-get install ffmpeg

# Or macOS
brew install ffmpeg

# Place crowd SFX file
mkdir -p downloads
# Add crowd_of.wav to downloads/ directory
```

## Configuration

Edit [config.py](config.py) to customize:

- **Database credentials** - MySQL connection settings
- **API endpoints** - Backend server URLs
- **Audio settings** - Volume levels, sampling rates
- **ElevenLabs API** - TTS voice and model settings
- **Match timing** - Default time slot (currently 21:00)

## Database Schema

The system reads from the `Deliveries` table with the following key fields:

```sql
mysql> DESCRIBE Deliveries;
+----------------+---------------+
| Field          | Type          |
+----------------+---------------+
| event_id       | int(11)       | -- Auto-increment, primary key
| ball_id        | varchar(36)   | -- UUID
| match_id       | varchar(36)   | -- UUID, links to match
| batsman_id     | varchar(36)   | -- UUID
| runs_scored    | int(11)       | -- -1 for wicket, 0-6 for runs
| sentence       | text          | -- Pre-generated commentary (PRIMARY SOURCE)
| intensity      | varchar(20)   | -- low/normal/medium/high/extreme
| ball_timestamp | datetime      |
| createdAt      | datetime      |
+----------------+---------------+
```

**Commentary Source**: The `sentence` field contains pre-generated commentary text. The `intensity` field controls voice excitement:
- `low` → Calm voice (excitement level 2)
- `normal` → Standard voice (excitement level 5)
- `medium` → Engaged voice (excitement level 7)
- `high` → Excited voice (excitement level 9)
- `extreme` → Maximum excitement (excitement level 10)

**Fallback**: If `sentence` is empty/null, the system falls back to built-in templates based on `runs_scored`.

## Usage

### Run the commentator

```bash
python main.py
```
# Indoor Cricket Live Commentary System

Real-time cricket match commentator that generates live audio commentary with crowd sound effects using pre-generated commentary from the database — now with a realtime WebSocket streaming mode for low-latency live audio.

## Highlights
- Push-based live events over WebSocket (recommended) with REST catch-up for reconnects
- Persistent crowd SFX loop with smart ducking during TTS playback
- Priority-aware commentary queue (system announcements > wickets/special > normal)
- Restart-safe runtime state persisted to `state/runtime_state.json`
- Non-blocking TTS streaming with configurable timeouts and latency logging

## Architecture (high level)

Source → Backend Event Publisher → WebSocket Event Stream → Commentary Engine → Audio Engine (TTS + crowd SFX)

Key components
- `main.py` — orchestrator and main loop
- `config.py` — all configuration and environment flags
- `api_client.py` — backend API helper (bookings, innings)
- `database.py` — legacy polling-based DB helper (still used in non-streaming mode)
- `event_queue.py` — in-memory priority queue with dedup and persisted runtime state
- `ws_client.py` — WebSocket client subscribing to `/ws/live-commentary/{match_id}` and fetching missed events
- `audio_manager.py` — priority-aware audio engine with TTS streaming and persistent crowd SFX
- `state/runtime_state.json` — runtime file used to store `match_id` and `last_spoken_ball_detection_id`

## Event Schema (Authoritative)
All events published by the backend MUST conform to this schema. The `sentences` field is the single source of commentary text — the commentary engine must not alter or generate text.

```json
{
       "ball_detection_id": "special_event_<event_type>_<timestamp>",
       "match_id": "<uuid>",
       "batsman_id": "<uuid | system>",
       "batsman_name": "<string>",
       "sentences": "<string>"
}
```
- `ball_detection_id`: unique event id (used for dedupe + ACK)
- `sentences`: authoritative commentary text (do not modify)

Event priority (determined by `ball_detection_id` type):
- System/Announcement → Highest (0)
- Wicket / Special → High (1)
- Normal ball events → Normal (2)

## Realtime Streaming vs Polling
- Streaming (recommended): Enable WebSocket streaming with `USE_WS_STREAMING=true` and the app will subscribe to `ws://<API>/ws/live-commentary/{match_id}` and immediately speak incoming events. On reconnect the client will call `GET /commentary/missed-events?match_id=...&after_id=...` to fetch and enqueue missed events.
- Polling (legacy): When streaming is disabled the app falls back to polling the `Deliveries` DB table using the logic in `database.py`.

## Runtime State
`state/runtime_state.json` is used to persist:
```json
{
       "match_id": "<uuid>",
       "last_spoken_ball_detection_id": "<string>",
       "last_update": 1670000000
}
```
This enables restart recovery and prevents duplicate commentary after restarts.

## Installation

### Prerequisites
- Python 3.8+
- ffmpeg (for any offline audio conversions)
- MySQL for production usage (or run with dummy mode for tests)

### Python deps

Install dependencies:

```bash
pip install -r requirements.txt
```

Note: `requirements.txt` now includes `websocket-client` required for streaming.

## Configuration (env / `config.py`)
Important environment variables and flags:
- `API_BASE_URL` — backend base URL (e.g. `http://192.168.18.120:8000`)
- `USE_WS_STREAMING` — `true` to enable WebSocket streaming mode (default: false)
- `SPEAK_ONLY_DELIVERIES` — speak only DB deliveries and skip announcements
- `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID` — TTS credentials
- `AUDIO_TTS_TIMEOUT` — seconds to wait for TTS chunks before skipping (default: 8)

All defaults are defined in `config.py`.

## Running

Start the commentator:

```bash
# Streaming mode (recommended)
export USE_WS_STREAMING=true
export API_BASE_URL="http://your.backend:8000"
export ELEVENLABS_API_KEY="<key>"
python main.py

# Polling mode (legacy)
export USE_WS_STREAMING=false
python main.py
```

Logs:
- Console (INFO)
- `cricket_commentary.log` in the working directory

## Files of interest
- `state/runtime_state.json` — runtime persisted state
- `downloads/crowd_of.wav` — SFX (used by legacy mixer), keep in `downloads/`
- `background_audio/crowd_of_22050.wav` — pre-sampled background audio used by audio engine

## Developer notes
- The commentary engine treats `sentences` from the event payload as authoritative.
- `event_queue.py` deduplicates by `ball_detection_id` and persists `last_spoken_ball_detection_id` for restarts.
- `ws_client.py` will fetch missed events on reconnect from `/commentary/missed-events`.
- `audio_manager.py` uses a priority queue and may preempt playback for higher-priority events.
- To change priority mapping, adjust the logic in `event_queue.py` or `main.py` where priorities are assigned.

## Testing and next steps
Recommended next steps if you want to expand this work:
- Add unit/integration tests that simulate WebSocket messages and slow/missing TTS streams.
- Add Prometheus metrics for queue depth and latencies.
- Harden cancellations of stalled TTS streams if the TTS API exposes a cancel handle.

## Troubleshooting
- If no audio plays, verify `ELEVENLABS_API_KEY` and network access to the API and TTS endpoints.
- If streaming mode fails to connect, check `API_BASE_URL` and that the backend exposes `/ws/live-commentary/{match_id}`.

---

If you want, I can now:
- Add a small integration test harness that simulates WS messages locally, or
- Add Prometheus metrics and a simple `/metrics` endpoint, or
- Create a minimal example publisher (backend stub) that emits test events.

Which of these would you like next?

