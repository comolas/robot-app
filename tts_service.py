import hashlib
import os
from pathlib import Path

import requests
from google.cloud import texttospeech


class TTSService:
    def __init__(self):
        self.output_dir = Path("audio_output")
        self.output_dir.mkdir(exist_ok=True)

        self.minimax_api_key = os.getenv("MINIMAX_API_KEY", "").strip()
        self.minimax_voice_id = os.getenv("MINIMAX_VOICE_ID", "").strip()
        self.minimax_model = os.getenv("MINIMAX_MODEL", "speech-2.8-turbo").strip()
        self.minimax_api_url = os.getenv(
            "MINIMAX_TTS_URL", "https://api.minimax.io/v1/t2a_v2"
        ).strip()
        self.minimax_speed = float(os.getenv("MINIMAX_SPEECH_SPEED", "1.0"))
        self.minimax_enabled = bool(self.minimax_api_key and self.minimax_voice_id)

        self.google_client = None
        try:
            self.google_client = texttospeech.TextToSpeechClient()
        except Exception as exc:
            print(f"Google TTS yedegi baslatilamadi: {exc}")

        if not self.minimax_enabled and not self.google_client:
            raise RuntimeError("MiniMax veya Google TTS yapilandirmasi bulunamadi")

    @property
    def provider_name(self) -> str:
        return "MiniMax (Google TTS yedekli)" if self.minimax_enabled else "Google Cloud TTS"

    def text_to_speech(self, text: str, filename: str = "output.mp3") -> str:
        return self.text_to_speech_lang(text, filename, language_code="tr-TR")

    def text_to_speech_lang(
        self,
        text: str,
        filename: str = "output.mp3",
        language_code: str = "tr-TR",
    ) -> str:
        """Convert text to speech with MiniMax first and Google TTS as fallback."""
        if self.minimax_enabled:
            try:
                return self._minimax_speech(text, language_code)
            except Exception as exc:
                print(f"MiniMax TTS hatasi, Google TTS deneniyor: {exc}")

        if self.google_client:
            return self._google_speech(text, language_code)
        raise RuntimeError("Ses olusturulamadi ve Google TTS yedegi kullanilamiyor")

    def _cache_path(self, provider_key: str, language_code: str, text: str) -> Path:
        cache_key = hashlib.md5(
            f"{provider_key}:{language_code}:{text}".encode("utf-8")
        ).hexdigest()
        return self.output_dir / f"cache_{cache_key}.mp3"

    def _minimax_speech(self, text: str, language_code: str) -> str:
        provider_key = f"minimax:{self.minimax_model}:{self.minimax_voice_id}"
        cache_path = self._cache_path(provider_key, language_code, text)
        if cache_path.exists():
            return str(cache_path)

        language_boost = "English" if language_code.lower().startswith("en") else "Turkish"
        payload = {
            "model": self.minimax_model,
            "text": text,
            "stream": False,
            "language_boost": language_boost,
            "output_format": "hex",
            "voice_setting": {
                "voice_id": self.minimax_voice_id,
                "speed": self.minimax_speed,
                "vol": 1,
                "pitch": 0,
                "english_normalization": False,
            },
            "audio_setting": {
                "sample_rate": 32000,
                "bitrate": 128000,
                "format": "mp3",
                "channel": 1,
            },
        }
        response = requests.post(
            self.minimax_api_url,
            headers={
                "Authorization": f"Bearer {self.minimax_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=45,
        )
        response.raise_for_status()
        result = response.json()
        base_response = result.get("base_resp") or {}
        if base_response.get("status_code", 0) != 0:
            raise RuntimeError(
                f"MiniMax {base_response.get('status_code')}: "
                f"{base_response.get('status_msg', 'bilinmeyen hata')}"
            )

        audio_hex = (result.get("data") or {}).get("audio")
        if not audio_hex:
            raise RuntimeError("MiniMax yanitinda ses verisi bulunamadi")
        try:
            audio_bytes = bytes.fromhex(audio_hex)
        except ValueError as exc:
            raise RuntimeError("MiniMax gecersiz ses verisi dondurdu") from exc
        if not audio_bytes:
            raise RuntimeError("MiniMax bos ses verisi dondurdu")

        cache_path.write_bytes(audio_bytes)
        return str(cache_path)

    def _google_speech(self, text: str, language_code: str) -> str:
        cache_path = self._cache_path("google-wavenet", language_code, text)
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
            ssml_gender=texttospeech.SsmlVoiceGender.FEMALE,
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=1.0,
            pitch=0.0,
        )
        response = self.google_client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config,
        )
        cache_path.write_bytes(response.audio_content)
        return str(cache_path)
