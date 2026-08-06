import os
from google.cloud import speech
from pathlib import Path


class STTService:
    def __init__(self):
        self.client = speech.SpeechClient()

    def transcribe(self, audio_path: str, language_code: str = "en-US") -> str:
        """Ses dosyasını metne çevir. WAV, WEBM, MP3 destekler. Uzun sesler için LongRunning kullanır."""
        with open(audio_path, "rb") as f:
            audio_content = f.read()

        audio = speech.RecognitionAudio(content=audio_content)

        ext = Path(audio_path).suffix.lower()
        if ext == ".webm":
            encoding = speech.RecognitionConfig.AudioEncoding.WEBM_OPUS
            sample_rate = None
        elif ext == ".ogg":
            encoding = speech.RecognitionConfig.AudioEncoding.OGG_OPUS
            sample_rate = None
        elif ext == ".mp3":
            encoding = speech.RecognitionConfig.AudioEncoding.MP3
            sample_rate = None
        else:
            encoding = speech.RecognitionConfig.AudioEncoding.LINEAR16
            sample_rate = 16000

        config_kwargs = {
            "encoding": encoding,
            "language_code": language_code,
            "enable_automatic_punctuation": True,
            "use_enhanced": True,
        }
        if sample_rate:
            config_kwargs["sample_rate_hertz"] = sample_rate
        if language_code == "tr-TR":
            config_kwargs["alternative_language_codes"] = ["en-US"]

        config = speech.RecognitionConfig(**config_kwargs)

        # 1 dakikadan kısa sesler için sync, uzunlar için async
        if len(audio_content) < 960_000:
            response = self.client.recognize(config=config, audio=audio)
        else:
            operation = self.client.long_running_recognize(config=config, audio=audio)
            response = operation.result(timeout=120)

        return " ".join(result.alternatives[0].transcript for result in response.results)
