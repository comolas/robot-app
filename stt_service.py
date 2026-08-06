from pathlib import Path

from google.cloud import speech


class STTService:
    def __init__(self):
        self.client = speech.SpeechClient()

    def transcribe(self, audio_path: str, language_code: str = "en-US") -> str:
        result = self.transcribe_with_metadata(audio_path, language_code)
        return result["transcript"]

    def transcribe_with_metadata(self, audio_path: str, language_code: str = "en-US") -> dict:
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

        if len(audio_content) < 960_000:
            response = self.client.recognize(config=config, audio=audio)
        else:
            operation = self.client.long_running_recognize(config=config, audio=audio)
            response = operation.result(timeout=120)

        transcript = " ".join(result.alternatives[0].transcript for result in response.results)
        return {
            "transcript": transcript,
            "result_count": len(response.results),
            "audio_bytes": len(audio_content),
            "encoding": encoding.name,
            "language_code": language_code,
        }
