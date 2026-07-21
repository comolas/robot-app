import hashlib
from google.cloud import texttospeech
from pathlib import Path


class TTSService:
    def __init__(self):
        self.client = texttospeech.TextToSpeechClient()
        self.output_dir = Path("audio_output")
        self.output_dir.mkdir(exist_ok=True)

    def text_to_speech(self, text: str, filename: str = "output.mp3") -> str:
        return self.text_to_speech_lang(text, filename, language_code="tr-TR")

    def text_to_speech_lang(self, text: str, filename: str = "output.mp3", language_code: str = "tr-TR") -> str:
        """Metni sese çevir — aynı metin+dil için cache kullan"""
        # Hash bazlı cache dosya adı
        cache_key = hashlib.md5(f"{language_code}:{text}".encode()).hexdigest()
        cache_path = self.output_dir / f"cache_{cache_key}.mp3"

        # Cache varsa direkt döndür
        if cache_path.exists():
            return str(cache_path)

        synthesis_input = texttospeech.SynthesisInput(text=text)

        voice_names = {
            "tr-TR": "tr-TR-Wavenet-E",
            "en-US": "en-US-Wavenet-F",
        }
        voice = texttospeech.VoiceSelectionParams(
            language_code=language_code,
            name=voice_names.get(language_code, voice_names["tr-TR"]),
            ssml_gender=texttospeech.SsmlVoiceGender.FEMALE
        )

        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=1.0,
            pitch=0.0
        )

        response = self.client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )

        with open(cache_path, "wb") as out:
            out.write(response.audio_content)

        return str(cache_path)
