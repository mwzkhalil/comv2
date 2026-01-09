"""Audio management with streaming TTS playback (no disk writes)."""

import io
import time
import threading
import queue
import os
import logging
from typing import Optional

import pygame
import soundfile as sf
from pydub import AudioSegment
from elevenlabs import VoiceSettings
from elevenlabs.client import ElevenLabs

from config import audio_config, tts_config

logger = logging.getLogger(__name__)


class AudioManager:
    """Manages TTS generation and audio playback with background sound effects."""
    
    def __init__(self):
        """Initialize audio manager."""
        self.config = audio_config
        self.tts_config = tts_config
        self.elevenlabs = ElevenLabs(api_key=self.tts_config.api_key)
        
        # Initialize pygame mixer
        pygame.mixer.init(
            frequency=self.config.sampling_rate,
            size=-16,
            channels=self.config.mixer_channels,
            buffer=self.config.mixer_buffer
        )
        
        # Audio channels
        self.commentary_channel = pygame.mixer.Channel(self.config.commentary_channel)
        self.background_channel: Optional[pygame.mixer.Channel] = None
        
        # Playback queue
        self.audio_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.playback_thread: Optional[threading.Thread] = None
        
        logger.info("Audio manager initialized")
    
    def start_background_sfx(self):
        """Load and start looping background crowd sound effects."""
        sfx_path = self.config.sfx_file
        
        if not os.path.exists(sfx_path):
            logger.warning(f"SFX file not found: {sfx_path}")
            return False
        
        try:
            # Check if conversion is needed
            with sf.SoundFile(sfx_path) as f:
                needs_conversion = (
                    f.samplerate != self.config.sampling_rate or 
                    f.channels != self.config.mixer_channels
                )
            
            if needs_conversion:
                logger.info(f"Converting SFX to {self.config.sampling_rate}Hz stereo")
                audio = AudioSegment.from_file(sfx_path)
                audio = audio.set_frame_rate(self.config.sampling_rate).set_channels(2)
                converted_path = sfx_path.replace(".wav", "_conv.wav")
                audio.export(converted_path, format="wav")
                sfx_path = converted_path
            
            # Load and play
            sound = pygame.mixer.Sound(sfx_path)
            self.background_channel = pygame.mixer.Channel(self.config.sfx_channel)
            self.background_channel.set_volume(self.config.background_volume)
            self.background_channel.play(sound, loops=-1)
            
            logger.info("Background crowd SFX started")
            return True
            
        except Exception as e:
            logger.error(f"Error loading SFX: {e}")
            return False
    
    def duck_background(self, duck: bool = True):
        """
        Smoothly adjust background volume (ducking).
        
        Args:
            duck: True to reduce volume, False to restore
        """
        if not self.background_channel:
            return
        
        target = self.config.ducked_volume if duck else self.config.background_volume
        current = self.background_channel.get_volume()
        
        # Smooth fade in steps
        for _ in range(self.config.duck_fade_steps):
            current += (target - current) / self.config.duck_fade_steps
            self.background_channel.set_volume(current)
            time.sleep(self.config.duck_fade_delay)
    
    def generate_tts_stream(self, text: str, excitement: int = 0) -> Optional[bytes]:
        """
        Generate TTS audio directly to memory (no disk writes).
        
        Args:
            text: Text to convert to speech
            excitement: Excitement level 0-10 (affects voice characteristics)
            
        Returns:
            Audio bytes (MP3 format) or None on error
        """
        # Map excitement to voice settings
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
            use_speaker_boost=self.tts_config.use_speaker_boost,
            speed=speed
        )
        
        try:
            logger.debug(f"Generating TTS (excitement={excitement}): {text[:50]}...")
            
            response = self.elevenlabs.text_to_speech.convert(
                voice_id=self.tts_config.voice_id,
                output_format=self.tts_config.output_format,
                text=text,
                model_id=self.tts_config.model_id,
                voice_settings=settings,
            )
            
            # Stream to memory
            audio_bytes = io.BytesIO()
            for chunk in response:
                if chunk:
                    audio_bytes.write(chunk)
            
            audio_bytes.seek(0)
            return audio_bytes.getvalue()
            
        except Exception as e:
            logger.error(f"TTS generation error: {e}")
            return None
    
    def queue_commentary(self, text: str, excitement: int = 0):
        """
        Queue commentary for playback.
        
        Args:
            text: Commentary text
            excitement: Excitement level 0-10
        """
        audio_data = self.generate_tts_stream(text, excitement)
        if audio_data:
            self.audio_queue.put((audio_data, excitement))
            logger.info(f"Queued commentary: {text[:50]}...")
    
    def start_playback_loop(self):
        """Start the audio playback thread."""
        if self.playback_thread and self.playback_thread.is_alive():
            logger.warning("Playback loop already running")
            return
        
        self.stop_event.clear()
        self.playback_thread = threading.Thread(
            target=self._playback_loop,
            daemon=True,
            name="AudioPlayback"
        )
        self.playback_thread.start()
        logger.info("Playback loop started")
    
    def _playback_loop(self):
        """Internal playback loop (runs in separate thread)."""
        logger.info("Playback loop thread started")
        
        while not self.stop_event.is_set():
            try:
                # Get next audio from queue (with timeout)
                item = self.audio_queue.get(timeout=1)
                
                if not item:
                    continue
                
                audio_bytes, excitement = item if isinstance(item, tuple) else (item, 3)
                
                # Wait for channel to be free
                while self.commentary_channel.get_busy():
                    time.sleep(0.1)
                
                # Duck background
                self.duck_background(duck=True)
                
                # Play audio from memory
                audio_stream = io.BytesIO(audio_bytes)
                
                # Convert MP3 to WAV in memory for pygame
                audio_segment = AudioSegment.from_file(audio_stream, format="mp3")
                wav_stream = io.BytesIO()
                audio_segment.export(wav_stream, format="wav")
                wav_stream.seek(0)
                
                sound = pygame.mixer.Sound(wav_stream)
                self.commentary_channel.play(sound)
                
                # Wait for playback to complete
                time.sleep(sound.get_length() + 0.3)
                
                # Restore background volume
                self.duck_background(duck=False)
                
                logger.debug("Commentary playback complete")
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Playback error: {e}")
                # Ensure background is restored even on error
                self.duck_background(duck=False)
        
        logger.info("Playback loop thread stopped")
    
    def stop(self):
        """Stop all audio playback and cleanup."""
        logger.info("Stopping audio manager...")
        self.stop_event.set()
        
        if self.playback_thread:
            self.playback_thread.join(timeout=5)
        
        pygame.mixer.quit()
        logger.info("Audio manager stopped")
    
    def get_queue_size(self) -> int:
        """Get current audio queue size."""
        return self.audio_queue.qsize()
