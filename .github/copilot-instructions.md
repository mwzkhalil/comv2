
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
