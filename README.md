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

### Logging

Logs are written to:
- Console (stdout) - INFO level
- `cricket_commentary.log` - Detailed logs

### Stopping

Press `Ctrl+C` for graceful shutdown

## Project Structure

```
cricket_comp/
├── main.py              # Entry point and orchestration
├── config.py            # All configuration settings
├── state_manager.py     # Match state tracking
├── database.py          # MySQL operations
├── api_client.py        # Backend API interactions
├── audio_manager.py     # TTS and audio playback (streaming)
├── commentary.py        # Static commentary templates
├── requirements.txt     # Python dependencies
├── app.py              # Original monolithic version (legacy)
└── downloads/
    └── crowd_of.wav    # Background crowd SFX
```

