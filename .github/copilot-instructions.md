# Indoor Cricket Live Commentary System - AI Coding Instructions

## Project Overview
Real-time cricket match commentator that polls a MySQL database for live ball events and generates audio commentary with crowd sound effects. Uses static commentary templates (no LLM) with ElevenLabs TTS and pygame for audio playback.

## Architecture

### Modular Design (7 Core Modules)
- **[main.py](main.py)** - Orchestrator with main polling loop and phase handling
- **[config.py](config.py)** - Centralized configuration using dataclasses
- **[state_manager.py](state_manager.py)** - Match state encapsulation with lifecycle methods
- **[database.py](database.py)** - MySQL operations with context manager pattern
- **[api_client.py](api_client.py)** - Backend API client with session management
- **[audio_manager.py](audio_manager.py)** - Streaming TTS + playback (NO disk writes)
- **[commentary.py](commentary.py)** - Static template generation with excitement mapping

### Legacy Files
- **[app.py](app.py)** - Original monolithic version (kept for reference, not used)

### Data Flow
1. `CricketAPIClient` fetches match from booking API → updates `MatchState`
2. Poll innings status → determines phase (To Begin, Innings 1/2, Break, End)
3. `DatabaseManager` queries `Deliveries` table for new events (`event_id > last_seen_event_id`)
4. `CommentaryGenerator` extracts `sentence` field → maps `intensity` to excitement → `AudioManager` streams TTS to memory → playback with ducking

## Database Schema (MySQL)
**Table: `Deliveries`** (primary data source)
- `event_id` (INT, auto-increment): Primary key, monotonic ordering
- `match_id` (VARCHAR): Foreign key to match/slot (UUID format)
- `ball_id` (VARCHAR): Unique ball identifier (UUID)
- `batsman_id` (VARCHAR): Batsman identifier (UUID)
- `runs_scored` (INT): -1 for wicket, 0-6 for runs
- `sentence` (TEXT): **Pre-generated commentary text from database**
- `intensity` (VARCHAR): **Excitement level** (low/normal/medium/high/extreme)
- `ball_timestamp`, `camera_id`, `ball_position`, `hit_type`, `frame_number`, `createdAt`: Metadata fields

**Commentary Source**: Uses `sentence` field from database directly, with `intensity` mapped to TTS excitement (fallback to templates if sentence is empty)

**Connection**: Direct pymysql connection (not pooled) - reconnects per poll cycle

## Critical Workflows

### Running the Commentator
```bash
# Install dependencies
pip install -r requirements.txt

# Run new modular version
python main.py

# Or legacy monolithic version
python app.py

# Ctrl+C for graceful shutdown
```

### Audio Streaming (NEW APPROACH)
- **In-Memory TTS**: Audio generated to `BytesIO`, converted MP3→WAV in memory
- **No Disk Writes**: Eliminated temp file creation/deletion (faster, cleaner)
- **Background SFX**: `./downloads/crowd_of.wav` auto-converted to 22050Hz stereo
- **Ducking**: Smooth volume fade (30% → 8%) over 10 steps (200ms total)

### Match Lifecycle States
1. **To Begin**: Welcome announcement (once per `slot_id`)
2. **Innings 1/2**: Poll `Deliveries` table for new events, use database `sentence` field
3. **Innings Break**: Break announcement (flag prevents repeats)
4. **End Innings**: Winner announcement based on `winnerId`

## Project-Specific Conventions

### Commentary System (Database-Driven)
- **PRIMARY SOURCE**: Uses `sentence` field from database Deliveries table
- **Intensity Mapping**: `intensity` field mapped to TTS excitement levels
  - `low` → 2, `normal` → 5, `medium` → 7, `high` → 9, `extreme` → 10
- **Fallback Templates**: Static `TEMPLATES` dict used only if `sentence` is empty/null
- **No LLM**: All commentary pre-generated in database, system just reads and speaks it

### State Management (Object-Oriented)
- **Encapsulated State**: `MatchState` dataclass in [state_manager.py](state_manager.py)
- **Lifecycle Methods**: `should_announce_*()`, `mark_*_announced()` pattern
- **Event Deduplication**: `last_seen_event_id` tracked in state object
- **Auto-Reset**: Flags reset on `slot_id` change via `reset_for_new_match()`

### Threading & Concurrency
- **Queue Pattern**: `audio_queue` (thread-safe) in `AudioManager` decouples generation/playback
- **Daemon Threads**: Playback thread runs as daemon, auto-terminates on main exit
- **Signal Handling**: SIGINT/SIGTERM captured for graceful shutdown
- **No Locking**:Management

### Centralized Config ([config.py](config.py))
All settings organized in dataclasses:
- **DatabaseConfig**: MySQL host, credentials, connection params
- **APIConfig**: Backend URLs, endpoints, timeouts
- **AudioConfig**: Sampling rates (22050Hz), volumes (30%/8%), channels
- **ElevenLabsConfig**: API key (supports env var), voice ID, model settings
- **PollingConfIntensity Levels
Edit [commentary.py](commentary.py):
```python
INTENSITY_MAP = {
    "low": 2,
    "normal": 5,
    "critical": 10  # Add new intensity level
}
```

### Updating Database Commentary
Commentary is stored in `Deliveries.sentence` field - update database records:
```sql
UPDATE Deliveries 
SET sentence = 'New commentary text', intensity = 'high' 
WHERE event_id = 123;
```

### Fallback Template Customization
Templates in [commentary.py](commentary.py) are used only when `sentence` is NULL:
```python
TEMPLATES = {
    6: ["SIX! Custom template!", "Another six!"]
}
```python
# In config.py
api_key: str = os.getenv("ELEVENLABS_API_KEY", "default_key")
```writer pattern) Patterns


## Debugging Tip
```
2. Update `generate()` method logic to detect event type
3. Return appropriate excitement level (0-10)

### Changing Time Slot
Edit [config.py](config.py):
```python
@dataclass
class MatchConfig:
    default_time_hour: int = 19  # Change from 21 to 19
```

### Adding New Audio Channels
1. Update `AudioConfig.mixer_channels` in [config.py](config.py)
2. Allocate channels in `AudioManager.__init__()` in [audio_manager.py](audio_manager.py)
3. Create new playback methods following `commentary_channel` pattern
## Common Modifications

### Adding New Commentary Events
1. Add key to `STATIC_COMMENcricket_commentary.log` for database/API errors
- **Audio Issues**: Verify `downloads/crowd_of.wav` exists, check pygame mixer logs
- **State Problems**: Add debug prints in `MatchState` lifecycle methods
- **TTS Failures**: Check ElevenLabs API key in [config.py](config.py) or `ELEVENLABS_API_KEY` env var
- **Module Imports**: Ensure all files in same directory, run from project root

### Logging
- Console: INFO level
- File: `cricket_commentary.log` - detailed logs with timestamps
- Adjust level in [main.py](main.py): `logging.basicConfig(level=logging.DEBUG)`

## Key Improvements Over Legacy Code

### Streaming Audio (Major Performance Win)
- **Old**: Generate TTS → save `temp_*.mp3` → load → play → delete
- **New**: Generate TTS → `BytesIO` → convert in-memory → play (zero disk I/O)

### Better Code Organization
- **Old**: 429 lines monolithic [app.py](app.py)
- **New**: 7 focused modules, each <200 lines, single responsibility

### Type Safety & Error Handling
- Dataclasses with type hints throughout
- Context managers for resource cleanup (`DatabaseManager.get_connection`)
- Comprehensive logging with proper exception handling

### Testability
- All components independently instantiable
- Dependency injection (pass managers to orchestrator)
- Mock-friendly interfaces (e.g., `DatabaseManager.test_connection()`
### Supporting Multiple Matches
- Remove `current_slot_id` global, use per-thread/instance state
- Add match selector UI or command-line args
- Track `last_seen_event_id` per `match_id` (dict keyed by slot)

## Dependencies & Environment
```bash
pip install pymysql requests pygame soundfile pydub elevenlabs
# System deps: ffmpeg (for pydub audio conversion)
```

## Debugging Tips
- **No Commentary**: Check `Deliveries` table has `match_id` matching `current_slot_id`
- **Audio Gaps**: Verify SFX file exists and converted (watch console for "Crowd SFX started")
- **Timing Issues**: Adjust `time.sleep()` values in poll loops (shorter = more responsive)
- **TTS Failures**: API key expiry or rate limits (check ElevenLabs dashboard)

## Known Limitations
- Single match monitoring (one `slot_id` at a time)
- No reconnection logic for MySQL/API failures (retries with sleep)
- Hardcoded 21:00 time slot (not dynamic)
- TTS files accumulate if playback crashes (no cleanup on exception)
