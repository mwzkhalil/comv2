
# Copilot Instructions: Indoor Cricket Live Commentary System

## Project Overview
- **Purpose:** Real-time, database-driven cricket commentary with live TTS audio and crowd SFX, modulated by match intensity.
- **Architecture:**
  - Main loop in [main.py](../../main.py) orchestrates polling, commentary, and audio playback.
  - Modular components: API/database access, state management, commentary generation, and audio streaming.
  - Data flow: Polls MySQL `Deliveries` table → commentary selection/generation → TTS synthesis → audio mixing with SFX.

## Key Components & Data Flow
- [main.py](../../main.py): Entry point, main loop, signal handling, and orchestrates all subsystems.
- [config.py](../../config.py): Centralizes all configuration (DB, API, audio, TTS). **Never hardcode config elsewhere.**
- [database.py](../../database.py): MySQL queries, schema logic, and delivery polling.
- [api_client.py](../../api_client.py): Backend API communication (if enabled).
- [state_manager.py](../../state_manager.py): Tracks match state, event progression, and announcement flags.
- [audio_manager.py](../../audio_manager.py): TTS synthesis, in-memory audio mixing, playback, and SFX ducking.
- [commentary.py](../../commentary.py): Fallback commentary templates (used if DB `sentence` is empty).

## Commentary & Audio Logic
- **Primary commentary:** Use `sentence` from DB if present; fallback to [commentary.py](../../commentary.py) templates keyed by `runs_scored`.
- **Voice excitement:** Map DB `intensity` (low/normal/medium/high/extreme) to TTS parameters (see [README.md](../../README.md)).
- **Audio:** All playback is in-memory; crowd SFX (`downloads/crowd_of.wav`) is mixed with TTS and ducked during speech.

## Developer Workflows
- **Run:** `python main.py` (main entry point)
- **Config:** Edit [config.py](../../config.py) for DB/API/audio/TTS settings
- **Logs:** Console (INFO) and `cricket_commentary.log` (detailed)
- **Shutdown:** Ctrl+C for graceful exit (signal handlers in [main.py](../../main.py))
- **Dependencies:** Install with `pip install -r requirements.txt` and ensure `ffmpeg` is available

## Project Conventions & Patterns
- All configuration is centralized in [config.py](../../config.py)
- Commentary logic is data-driven; **do not embed commentary text in code**
- Use the `intensity` field to drive all voice modulation and excitement
- Database schema is fixed; see [README.md](../../README.md) for field details
- Announcements (welcome, break, end) are handled by state flags in [state_manager.py](../../state_manager.py)

## Integration Points
- **MySQL DB:** `Deliveries` table is the primary data source (see schema in [README.md](../../README.md))
- **ElevenLabs API:** For TTS (configurable in [config.py](../../config.py))
- **Crowd SFX:** Place `crowd_of.wav` in `downloads/` directory

## Examples & Extensibility
- To add a new fallback commentary, update [commentary.py](../../commentary.py) templates
- To change TTS model/voice, update ElevenLabs section in [config.py](../../config.py)
- To adjust polling or audio parameters, edit [config.py](../../config.py)

## References
- See [README.md](../../README.md) for schema, setup, and architecture diagrams
- Key files: [main.py](../../main.py), [config.py](../../config.py), [database.py](../../database.py), [audio_manager.py](../../audio_manager.py), [commentary.py](../../commentary.py)

---
**For AI agents:**
- Always use config/data-driven logic; avoid hardcoding
- Follow the main loop and data flow as described in [main.py](../../main.py)
- When in doubt, check [README.md](../../README.md) and [config.py](../../config.py) for project-specific details

Additional agent guidance:
- Always use the `manage_todo_list` tool to plan and track progress for multi-step tasks. Start by creating a short plan, mark one item `in-progress`, then update statuses as work proceeds.
- Do not volunteer the model name unless explicitly asked. If explicitly asked about the model, state: "GPT-5 mini".

**Realtime Streaming Guidelines (Design Summary)**

Problem Statement:
- Commentary is only triggered on new DB deliveries; on restart previously generated events are not spoken and playback resumes only after the next delivery. Crowd SFX is restarted per-event rather than streaming continuously.

Target Architecture:
- Events pushed from a backend Event Publisher into a WebSocket Event Stream. Commentary engine acts as a WebSocket client and the Audio Engine performs TTS + persistent crowd SFX mixing.
- Key principle: events are pushed, not pulled; audio is streamed, not triggered per-row.

Event Delivery Mechanism:
- Transport: Primary WebSocket, fallback REST catch-up endpoint.
- WS endpoint: `/ws/live-commentary/{match_id}` — one connection per match; server guarantees ordered events.

Event Payload (authoritative):
```
{
  "ball_detection_id": "special_event_<event_type>_<timestamp>",
  "match_id": "<uuid>",
  "batsman_id": "<uuid | system>",
  "batsman_name": "<string>",
  "sentences": "<string>"
}
```
- `ball_detection_id` is the unique event id. `sentences` is the authoritative commentary text; the commentary engine must not alter or generate text.

Commentary Engine (Python) changes:
- Replace DB polling with a WebSocket client that subscribes to `match_id` on startup and enqueues received events into an in-memory FIFO.
- Add a new module `event_queue.py` to deduplicate by `ball_detection_id`, block overlapping commentary, enforce priority rules, and acknowledge processed events.
- Restart safety: persist `last_spoken_ball_detection_id` in `state/runtime_state.json`; on reconnect call REST `GET /commentary/missed-events?match_id=...&after_id=...` to enqueue missed events before resuming WS streaming.

Audio System changes:
- Start persistent crowd SFX once at app startup and loop continuously; do not restart per event.
- For each event: duck crowd audio, synthesize TTS from `sentences`, play TTS, then restore crowd volume.
- Enforce audio priority: System announcements > Wickets/Special > Normal ball events; queue manager may reorder by priority.

State and Backend responsibilities:
- Persist runtime state in `state/runtime_state.json`:
  ```json
  {
    "match_id": "<uuid>",
    "last_spoken_ball_detection_id": "<string>",
    "last_update": "<timestamp>"
  }
  ```
- Backend must publish exactly-once, in chronological order, and provide a REST missed-events endpoint for reconnects.

Failure handling & monitoring:
- Auto-reconnect WS with exponential backoff and request missed events using the last-spoken id.
- On audio failure, skip after timeout and continue streaming; log `event received`, `event spoken`, `event skipped (duplicate)`, and audio latency per event.
- Metrics to track: ball→commentary latency, queue depth, audio overlap errors.

Implementation phases:
- Phase 1: Backend streaming (WS + missed-events REST).
- Phase 2: Commentary engine (WS client, `event_queue.py`, restart safe state).
- Phase 3: Audio refactor (persistent crowd loop, ducking controller, non-blocking TTS).
- Phase 4: Testing (restart during live match, network drop recovery, high-frequency bursts).

Non-goals (explicit):
- No commentary text generation in Python.
- No DB polling for live events.
- No crowd audio restart per delivery.
- No hardcoded commentary logic.

Final outcome: The system will speak every event immediately, resume cleanly after restarts, and maintain continuous crowd ambience to behave like a live broadcast rather than a scripted reader.
