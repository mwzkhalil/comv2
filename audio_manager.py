"""
Audio manager with ElevenLabs streaming TTS + looping background audio
(using sounddevice, true PCM streaming, no disk writes).
"""

import time
import threading
import queue
import logging
from typing import Optional, Iterable

import numpy as np
import sounddevice as sd
import soundfile as sf

from elevenlabs.client import ElevenLabs
from elevenlabs import VoiceSettings

from config import audio_config, tts_config

logger = logging.getLogger(__name__)


class AudioManager:
    def __init__(self):
        self.config = audio_config
        self.tts_config = tts_config

        self.sample_rate = self.config.sampling_rate
        self.channels = 1
        self.dtype = "float32"

        self.elevenlabs = ElevenLabs(api_key=self.tts_config.api_key)

        # Load background audio into memory (mono, float32)
        self.bg_audio, bg_sr = sf.read(self.config.commentary_bg_file, dtype="float32")
        if bg_sr != self.sample_rate:
            # Auto-resample to match sample rate
            logger.warning(f"Resampling background audio from {bg_sr} Hz to {self.sample_rate} Hz")
            self.bg_audio = np.interp(
                np.linspace(0, len(self.bg_audio), int(len(self.bg_audio) * self.sample_rate / bg_sr)),
                np.arange(len(self.bg_audio)),
                self.bg_audio,
            )

        if self.bg_audio.ndim > 1:
            self.bg_audio = self.bg_audio[:, 0]  # force mono

        self.bg_index = 0

        # Volume state
        self.bg_volume = self.config.background_volume
        self.target_bg_volume = self.bg_volume

        # Commentary queue
        self.audio_queue: queue.Queue[Iterable[bytes]] = queue.Queue()

        # TTS buffer for streaming playback
        self.tts_buffer = np.zeros(0, dtype=np.float32)

        # Playback state
        self.stop_event = threading.Event()
        self.playback_thread: Optional[threading.Thread] = None

        logger.info("AudioManager initialized (sounddevice backend)")

    # ------------------------------------------------------------------
    # ELEVENLABS STREAMING TTS (PCM)
    # ------------------------------------------------------------------
    def generate_tts_stream(self, text: str, excitement: int = 0):
        if excitement == 0:
            stability = self.tts_config.stability_calm
            speed = self.tts_config.speed_calm
            style = self.tts_config.style_calm
        elif excitement < 6:
            stability = self.tts_config.stability_medium
            speed = self.tts_config.speed_medium
            style = self.tts_config.style_excited
        else:
            stability = self.tts_config.stability_excited
            speed = self.tts_config.speed_excited
            style = self.tts_config.style_excited

        settings = VoiceSettings(
            stability=stability,
            similarity_boost=self.tts_config.similarity_boost,
            style=style,
            speed=speed,
            use_speaker_boost=self.tts_config.use_speaker_boost,
        )

        try:
            return self.elevenlabs.text_to_speech.stream(
                text=text,
                voice_id=self.tts_config.voice_id,
                model_id=self.tts_config.model_id,
                voice_settings=settings,
                output_format="pcm_22050",
            )
        except Exception as e:
            logger.error(f"TTS streaming error: {e}")
            return None

    # ------------------------------------------------------------------
    # COMMENTARY QUEUE
    # ------------------------------------------------------------------
    def queue_commentary(self, text: str, excitement: int = 0):
        stream = self.generate_tts_stream(text, excitement)
        if stream:
            self.audio_queue.put(stream)
            logger.info(f"Queued commentary: {text[:60]}...")

    # ------------------------------------------------------------------
    # BACKGROUND / PLAYBACK COMPATIBILITY
    # ------------------------------------------------------------------
    def start_background_sfx(self) -> bool:
        """Compatibility for old pygame code: background starts automatically"""
        logger.info("Background SFX handled by audio engine (auto-start)")
        return True

    def start_playback_loop(self):
        """Compatibility for old pygame code: starts sounddevice engine"""
        self.start()

    # ------------------------------------------------------------------
    # AUDIO ENGINE
    # ------------------------------------------------------------------
    def start(self):
        if self.playback_thread and self.playback_thread.is_alive():
            return

        self.stop_event.clear()
        self.playback_thread = threading.Thread(
            target=self._audio_loop,
            daemon=True,
            name="AudioEngine",
        )
        self.playback_thread.start()
        logger.info("Audio engine started")

    def _audio_loop(self):
        blocksize = 1024

        def callback(outdata, frames, time_info, status):
            if status:
                logger.warning(status)

            # ---------------- BACKGROUND LOOP ----------------
            end = self.bg_index + frames
            if end >= len(self.bg_audio):
                chunk = np.concatenate(
                    (self.bg_audio[self.bg_index:], self.bg_audio[: end % len(self.bg_audio)])
                )
                self.bg_index = end % len(self.bg_audio)
            else:
                chunk = self.bg_audio[self.bg_index:end]
                self.bg_index = end

            # Smooth ducking
            self.bg_volume += (self.target_bg_volume - self.bg_volume) * 0.1
            mixed = chunk * self.bg_volume

            # ---------------- COMMENTARY MIX ----------------
            if self.tts_buffer.size > 0:
                take = min(frames, len(self.tts_buffer))
                mixed[:take] += self.tts_buffer[:take]
                self.tts_buffer = self.tts_buffer[take:]

                if self.tts_buffer.size == 0:
                    self._duck_background(False)

            outdata[:, 0] = mixed

        with sd.OutputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            blocksize=blocksize,
            callback=callback,
        ):
            while not self.stop_event.is_set():
                try:
                    tts_stream = self.audio_queue.get(timeout=0.2)
                except queue.Empty:
                    continue

                self._duck_background(True)

                pcm_chunks = []
                for chunk in tts_stream:
                    if self.stop_event.is_set():
                        break
                    if not isinstance(chunk, bytes):
                        continue
                    audio = np.frombuffer(chunk, dtype=np.int16).astype(np.float32)
                    audio /= 32768.0
                    pcm_chunks.append(audio)

                if pcm_chunks:
                    self.tts_buffer = np.concatenate(pcm_chunks)

    # ------------------------------------------------------------------
    # DUCKING
    # ------------------------------------------------------------------
    def _duck_background(self, duck: bool):
        self.target_bg_volume = (
            self.config.ducked_volume if duck else self.config.background_volume
        )

    # ------------------------------------------------------------------
    # SHUTDOWN
    # ------------------------------------------------------------------
    def stop(self):
        logger.info("Stopping AudioManager...")
        self.stop_event.set()
        if self.playback_thread:
            self.playback_thread.join(timeout=5)
        sd.stop()
        logger.info("AudioManager stopped")

    def get_queue_size(self) -> int:
        return self.audio_queue.qsize()
