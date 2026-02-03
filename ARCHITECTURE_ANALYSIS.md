# Architecture Analysis: Indoor Cricket Live Commentary System

## Executive Summary

This document provides a comprehensive analysis of the real-time indoor cricket live commentary system. The system is designed to provide live audio commentary with TTS (ElevenLabs), crowd SFX mixing, and database-driven commentary text. The architecture supports both polling-based (legacy) and WebSocket streaming (modern) modes.

---

## Current Architecture Overview

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Main Orchestrator                        │
│                      (main.py)                              │
│  - Polling loop / Event processing                          │
│  - Subsystem coordination                                   │
│  - Signal handling                                          │
└─────────────────────────────────────────────────────────────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│   Database   │ │  API Client  │ │    State     │ │   WebSocket  │
│   Manager    │ │              │ │   Manager    │ │    Client    │
│ (database.py)│ │(api_client.py)│ │(state_mgr.py)│ │ (ws_client.py)│
└──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
         │              │              │              │
         └──────────────┴──────────────┴──────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  Commentary     │
                    │  Generator      │
                    │ (commentary.py) │
                    └─────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  Audio Manager  │
                    │ (audio_manager) │
                    │  - TTS Stream   │
                    │  - Crowd SFX    │
                    │  - Ducking      │
                    └─────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  Event Queue    │
                    │ (event_queue.py)│
                    │  - Deduplication│
                    │  - Priority     │
                    │  - State persist│
                    └─────────────────┘
```

---

## Component Deep Dive

### 1. Main Orchestrator (`main.py`)

**Responsibilities:**
- Entry point and main event loop
- Coordinates all subsystems
- Handles match lifecycle (welcome, innings, break, end)
- Manages WebSocket vs polling mode switching
- Signal handling for graceful shutdown

**Key Methods:**
- `run()`: Main polling/processing loop
- `_poll_match()`: Fetches current match from API
- `_poll_innings()`: Fetches innings state
- `_poll_deliveries()`: Legacy DB polling mode
- `_process_stream_events()`: WebSocket streaming mode
- `_handle_match_phase()`: Routes to appropriate phase handler

**Current State:**
- ✅ Supports both polling and WebSocket modes
- ✅ Proper signal handling
- ✅ Match phase management
- ⚠️ Priority handling is done via temporary `default_priority` manipulation (could be cleaner)

---

### 2. Configuration (`config.py`)

**Structure:**
- `DatabaseConfig`: MySQL connection settings
- `APIConfig`: Backend endpoints, streaming flags
- `AudioConfig`: Volume, ducking, file paths, timeouts
- `ElevenLabsConfig`: TTS API settings, voice parameters
- `PollingConfig`: Intervals for various operations
- `MatchConfig`: Default match timing

**Key Features:**
- ✅ Environment variable support via `python-dotenv`
- ✅ Centralized configuration (no hardcoding elsewhere)
- ✅ Excitement-based TTS parameter mapping
- ✅ Configurable timeouts and intervals

**Environment Variables:**
- `USE_WS_STREAMING`: Enable WebSocket mode (default: false)
- `SPEAK_ONLY_DELIVERIES`: Skip announcements (default: true)
- `USE_DUMMY_MODE`: Use mock data (default: true)
- `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`: TTS credentials
- `AUDIO_TTS_TIMEOUT`: TTS stream timeout (default: 8s)

---

### 3. Database Manager (`database.py`)

**Responsibilities:**
- MySQL connection pooling
- Delivery polling with event_id/timestamp tracking
- Bootstrap logic for recent deliveries
- Optional audio history saving

**Key Methods:**
- `get_new_deliveries()`: Fetches deliveries after last_event_id
- `get_recent_deliveries()`: Bootstrap for new matches
- `test_connection()`: Health check

**Query Logic:**
- Checks booking API first to determine live status
- If `last_event_id <= 0`: Bootstrap with recent 6 deliveries
- Otherwise: Query `event_id > last_event_id` OR `ball_timestamp > last_seen_timestamp`
- Falls back to deliveries with non-null `sentence` if no booking

**Current State:**
- ✅ Proper connection management
- ✅ Bootstrap logic for restarts
- ⚠️ Only used in polling mode (legacy)

---

### 4. API Client (`api_client.py`)

**Responsibilities:**
- Backend REST API communication
- Match booking lookup
- Innings state fetching
- Session management

**Endpoints:**
- `GET /bookings/get_booking_by_time/`: Current match lookup
- `GET /innings/get_innings`: Innings status
- `GET /commentary/missed-events`: Missed events on reconnect (used by WS client)

**Current State:**
- ✅ Proper error handling
- ✅ Session reuse
- ✅ Match data enrichment

---

### 5. State Manager (`state_manager.py`)

**Responsibilities:**
- Match state encapsulation (`MatchState` dataclass)
- Event tracking (`last_seen_event_id`, `last_seen_ball_timestamp`)
- Announcement flags (welcome, break, end)
- State transitions

**Key State Fields:**
- `slot_id`: Match identifier
- `team_one_name`, `team_two_name`: Team names
- `innings_status`: Current phase (To Begin, Innings 1, Innings Break, etc.)
- `last_seen_event_id`: Last processed delivery
- `last_seen_ball_timestamp`: Timestamp-based tracking
- Announcement flags: `match_started_announced`, `innings_break_announced`, `match_ended_announced`

**Current State:**
- ✅ Clean encapsulation
- ✅ Proper state transitions
- ⚠️ Does NOT persist to disk (only in-memory)
- ⚠️ Separate from `event_queue.py` runtime state

---

### 6. Audio Manager (`audio_manager.py`)

**Responsibilities:**
- ElevenLabs TTS streaming (PCM format)
- Persistent crowd SFX looping
- Audio mixing and ducking
- Priority-based playback queue
- Non-blocking TTS synthesis

**Key Features:**
- ✅ Streaming TTS (no disk writes)
- ✅ Persistent background audio loop
- ✅ Smooth ducking during commentary
- ✅ Priority queue (lower number = higher priority)
- ✅ Preemption for higher-priority events
- ✅ Timeout handling for stalled TTS streams

**Audio Flow:**
1. Background SFX loops continuously in audio callback
2. Commentary events queued with priority
3. TTS stream collected in worker thread
4. Background ducked during TTS playback
5. TTS mixed with ducked background
6. Background restored after TTS completes

**Current State:**
- ✅ Modern sounddevice-based implementation
- ✅ Proper threading and non-blocking design
- ✅ Priority-aware queue
- ⚠️ Priority set via temporary `default_priority` attribute (could be cleaner API)

---

### 7. Commentary Generator (`commentary.py`)

**Responsibilities:**
- Primary: Extract `sentence` from DB delivery
- Fallback: Template-based commentary by `runs_scored`
- Intensity → Excitement mapping
- System announcements (welcome, break, end)

**Intensity Mapping:**
- `low` → excitement 2
- `normal` → excitement 5
- `medium` → excitement 7
- `high` → excitement 9
- `extreme` → excitement 10

**Template Structure:**
- Keyed by `runs_scored` (-1 for wickets, 0-6 for runs)
- Random selection from template list
- Future support for extras (wide, no_ball, bye, leg_bye)

**Current State:**
- ✅ Data-driven (DB sentence is primary)
- ✅ Fallback templates available
- ✅ No hardcoded commentary in main code
- ⚠️ System announcements still have hardcoded text (welcome, break, end)

---

### 8. Event Queue (`event_queue.py`)

**Responsibilities:**
- In-memory priority queue for WebSocket events
- Deduplication by `ball_detection_id`
- Priority determination from event type
- Runtime state persistence (`state/runtime_state.json`)

**Priority Levels:**
- `0`: System announcements
- `1`: Wickets / Special events
- `2`: Normal ball events

**State Persistence:**
- `last_spoken_ball_detection_id`: Last processed event
- `match_id`: Current match identifier
- `last_update`: Timestamp

**Current State:**
- ✅ Proper deduplication
- ✅ Priority queue implementation
- ✅ State persistence for restart safety
- ⚠️ Priority parsing from `ball_detection_id` string (fragile)

---

### 9. WebSocket Client (`ws_client.py`)

**Responsibilities:**
- WebSocket connection to `/ws/live-commentary/{match_id}`
- Event reception and enqueueing
- Auto-reconnect with exponential backoff
- Missed events fetching on reconnect

**Reconnection Logic:**
- Exponential backoff (1s → 2s → 4s → ... → max 30s)
- Fetches missed events via REST before resuming WS
- Uses `last_spoken_ball_detection_id` for catch-up

**Current State:**
- ✅ Proper reconnection handling
- ✅ Missed events catch-up
- ✅ Thread-safe operation
- ⚠️ No connection health monitoring/metrics

---

## Data Flow Analysis

### Polling Mode (Legacy)

```
1. Main loop polls API for match → State Manager
2. Main loop polls API for innings → State Manager
3. If innings live:
   a. Database Manager polls Deliveries table
   b. For each new delivery:
      - Commentary Generator extracts sentence + intensity
      - Audio Manager queues TTS synthesis
      - State Manager updates last_seen_event_id
4. Audio Manager plays TTS with ducked crowd SFX
```

### WebSocket Streaming Mode (Modern)

```
1. Main loop polls API for match → State Manager
2. WebSocket Client subscribes to /ws/live-commentary/{match_id}
3. On reconnect: WS Client fetches missed events via REST
4. Events received → Event Queue (deduplication, priority)
5. Main loop processes Event Queue → Commentary Generator
6. Audio Manager queues TTS with priority
7. Event Queue marks processed → State persisted
```

---

## Commentary Text Flow

### Primary Path (Data-Driven)
```
Database Deliveries.sentence → CommentaryGenerator.get_from_database() 
→ AudioManager.queue_commentary() → TTS Stream → Playback
```

### Fallback Path (Templates)
```
Database Deliveries.runs_scored → CommentaryGenerator._generate_from_template()
→ AudioManager.queue_commentary() → TTS Stream → Playback
```

### WebSocket Path (Authoritative)
```
WebSocket event.sentences → EventQueue.enqueue() → Main._process_stream_events()
→ AudioManager.queue_commentary() → TTS Stream → Playback
```

**Key Principle:** Commentary text is NEVER generated by the Python code. It comes from:
1. Database `sentence` field (polling mode)
2. WebSocket `sentences` field (streaming mode)
3. Fallback templates only if `sentence` is empty/null

---

## Audio Playback Architecture

### Persistent Crowd SFX
- Loaded once at startup (`commentary_bg_file`)
- Loops continuously in audio callback
- Never restarted per event
- Volume controlled via ducking

### TTS Streaming
- Non-blocking synthesis via ElevenLabs streaming API
- PCM format (22050 Hz, 16-bit)
- Collected in worker thread with timeout
- Mixed with ducked background in real-time

### Ducking Logic
- Target volume: `background_volume` (0.30) → `ducked_volume` (0.08)
- Smooth fade via linear interpolation (10% per frame)
- Duck on TTS start, restore on TTS end

### Priority System
- Lower number = higher priority
- Preemption: Higher priority events replace current buffer
- Same priority: Append to current buffer (FIFO)

---

## State Management Analysis

### In-Memory State (`state_manager.py`)
- Match metadata (teams, scores, innings status)
- Event tracking (`last_seen_event_id`, `last_seen_ball_timestamp`)
- Announcement flags
- **Not persisted** (resets on restart)

### Runtime State (`event_queue.py` → `state/runtime_state.json`)
- `last_spoken_ball_detection_id`: Last processed WebSocket event
- `match_id`: Current match identifier
- `last_update`: Timestamp
- **Persisted** for restart safety

### Gap Analysis
- ⚠️ Two separate state systems (in-memory vs persisted)
- ⚠️ Polling mode uses `last_seen_event_id` (not persisted)
- ⚠️ Streaming mode uses `last_spoken_ball_detection_id` (persisted)
- ⚠️ No unified state persistence strategy

---

## Restart Safety Analysis

### Current Implementation

**WebSocket Mode:**
- ✅ `last_spoken_ball_detection_id` persisted
- ✅ Missed events fetched on reconnect
- ✅ Deduplication prevents repeats

**Polling Mode:**
- ⚠️ `last_seen_event_id` not persisted
- ⚠️ Bootstrap logic fetches recent 6 deliveries
- ⚠️ May miss events between restarts if >6 deliveries occurred

**Recommendations:**
1. Persist `last_seen_event_id` in runtime state for polling mode
2. Unified state persistence for both modes
3. Bootstrap logic should use persisted state

---

## Priority System Analysis

### Current Implementation

**Event Queue Priority:**
- Parsed from `ball_detection_id` string: `special_event_<type>_<timestamp>`
- Type-based: `announcement/system` → 0, `wicket/special` → 1, else → 2

**Audio Manager Priority:**
- Set via temporary `default_priority` attribute manipulation
- Preemption logic: Higher priority replaces buffer

**Issues:**
- ⚠️ Priority parsing is fragile (string-based)
- ⚠️ Priority setting API is awkward (`default_priority` manipulation)
- ⚠️ No explicit priority field in event payload

**Recommendations:**
1. Add explicit `priority` field to event payload
2. Cleaner API for priority setting in AudioManager
3. Centralized priority mapping logic

---

## Metrics & Monitoring Gaps

### Current Logging
- ✅ Event received (INFO)
- ✅ Event spoken (INFO)
- ✅ Audio queue latency (INFO)
- ✅ TTS timeout warnings

### Missing Metrics
- ❌ Ball → commentary latency (end-to-end)
- ❌ Queue depth over time
- ❌ Audio overlap errors
- ❌ WebSocket reconnection frequency
- ❌ TTS failure rate
- ❌ Duplicate event rate

**Recommendations:**
1. Add Prometheus metrics endpoint
2. Structured logging with event IDs
3. Latency tracking (event timestamp → playback start)

---

## Areas for Improvement

### 1. State Persistence Unification
**Issue:** Two separate state systems (in-memory vs persisted)
**Solution:** Unified state manager that persists all critical state

### 2. Priority System Refinement
**Issue:** Fragile string parsing, awkward API
**Solution:** Explicit priority field, cleaner AudioManager API

### 3. Metrics & Monitoring
**Issue:** Limited observability
**Solution:** Add structured metrics and latency tracking

### 4. Error Handling
**Issue:** Some failures are silent or not retried
**Solution:** Comprehensive error handling with retries and alerts

### 5. Testing Infrastructure
**Issue:** No automated tests
**Solution:** Unit tests, integration tests, WebSocket simulation

### 6. Configuration Validation
**Issue:** No validation of config values
**Solution:** Startup validation of all config parameters

---

## Compliance with Requirements

### ✅ Implemented
- [x] Data-driven commentary (DB sentence field)
- [x] WebSocket streaming mode
- [x] Event queue with deduplication
- [x] Priority-based playback
- [x] Persistent crowd SFX
- [x] Ducking during TTS
- [x] Restart-safe state (WebSocket mode)
- [x] Non-blocking TTS synthesis
- [x] Timeout handling
- [x] Auto-reconnect with backoff
- [x] Missed events catch-up

### ⚠️ Partially Implemented
- [ ] Restart safety (polling mode not fully safe)
- [ ] Metrics tracking (basic logging only)
- [ ] Priority system (works but fragile)

### ❌ Not Implemented
- [ ] Unified state persistence
- [ ] Prometheus metrics
- [ ] Comprehensive error recovery
- [ ] Automated testing

---

## Next Steps & Recommendations

### High Priority
1. **Unify State Persistence**: Merge `state_manager.py` and `event_queue.py` state
2. **Improve Priority System**: Add explicit priority field, cleaner API
3. **Add Metrics**: Prometheus endpoint, structured logging

### Medium Priority
4. **Error Handling**: Comprehensive retries, alerts
5. **Testing**: Unit tests, integration tests
6. **Documentation**: API docs, deployment guide

### Low Priority
7. **Performance Optimization**: Profile and optimize hot paths
8. **Configuration Validation**: Startup checks
9. **Monitoring Dashboard**: Real-time metrics visualization

---

## Conclusion

The system is well-architected with clear separation of concerns and modern streaming capabilities. The WebSocket mode provides low-latency event delivery, and the audio system handles persistent SFX with proper ducking. The main areas for improvement are state persistence unification, metrics/monitoring, and testing infrastructure.

The codebase follows good practices:
- ✅ Centralized configuration
- ✅ Data-driven commentary
- ✅ Modular design
- ✅ Proper error handling (in most places)
- ✅ Restart safety (for WebSocket mode)

With the recommended improvements, the system will be production-ready with full observability and robustness.
