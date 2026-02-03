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

        # Commentary queue (priority queue: lower number = higher priority)
        # Tuple: (priority, counter, enqueue_ts, stream)
        self.audio_queue: queue.PriorityQueue = queue.PriorityQueue()
        self._aq_counter = 0

        # TTS buffer for streaming playback
        self.tts_buffer = np.zeros(0, dtype=np.float32)
        self._current_priority: Optional[int] = None

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
        """Queue commentary for playback with optional priority.

        Priority: lower integer means higher priority. Default priority is 2 (normal).
        """
        stream = self.generate_tts_stream(text, excitement)
        if not stream:
            return

        # Default priority choices could be refined by caller
        priority = getattr(self, "default_priority", 2)
        self._aq_counter += 1
        enqueue_ts = time.time()
        # Store enqueue timestamp for latency metrics and the stream object
        self.audio_queue.put((priority, self._aq_counter, enqueue_ts, stream))
        logger.info(f"Queued commentary (prio={priority}): {text[:60]}...")

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
                    item = self.audio_queue.get(timeout=0.2)
                except queue.Empty:
                    continue

                # item is (priority, counter, enqueue_ts, stream)
                priority, _cnt, enqueue_ts, tts_stream = item

                # Log enqueue->start latency
                latency = time.time() - enqueue_ts
                logger.info(f"Audio queue latency: {latency:.3f}s (prio={priority})")

                self._duck_background(True)

                # Collect PCM chunks from streaming generator in a worker thread
                pcm_raw_chunks = []

                def _collect():
                    try:
                        for chunk in tts_stream:
                            if self.stop_event.is_set():
                                break
                            if not isinstance(chunk, bytes):
                                continue
                            pcm_raw_chunks.append(chunk)
                    except Exception as e:
                        logger.error(f"Error while collecting TTS stream: {e}")

                collector = threading.Thread(target=_collect, daemon=True)
                collector.start()

                # Wait up to configured timeout for TTS to finish/produce data
                timeout = getattr(self.config, "tts_stream_timeout", 8)
                collector.join(timeout=timeout)

                if collector.is_alive():
                    logger.warning(f"TTS stream timed out after {timeout}s (prio={priority})")
                    # We won't attempt to forcibly close underlying stream; proceed with collected data

                if not pcm_raw_chunks:
                    logger.error("No audio received from TTS stream; skipping event")
                    # restore background ducking state
                    self._duck_background(False)
                    continue

                # Convert raw PCM byte chunks into float32 arrays and concatenate
                pcm_chunks = []
                for chunk in pcm_raw_chunks:
                    audio = np.frombuffer(chunk, dtype=np.int16).astype(np.float32)
                    audio /= 32768.0
                    pcm_chunks.append(audio)

                new_buffer = np.concatenate(pcm_chunks)

                # If something is already playing, decide whether to preempt
                if self.tts_buffer.size > 0 and self._current_priority is not None:
                    # Preempt if incoming has higher priority (lower number)
                    if priority < self._current_priority:
                        self.tts_buffer = new_buffer
                        self._current_priority = priority
                    else:
                        # Append after current buffer
                        self.tts_buffer = np.concatenate((self.tts_buffer, new_buffer))
                else:
                    self.tts_buffer = new_buffer
                    self._current_priority = priority

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
