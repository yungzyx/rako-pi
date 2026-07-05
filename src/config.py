"""Configuración tipada de Rako (lee `.env`).

Usa pydantic-settings. Todos los campos opcionales para que el bootstrap
de dev funcione sin credenciales reales.
"""

from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Núcleo ---
    rako_env: Literal["dev", "staging", "prod"] = "dev"
    rako_log_level: str = "INFO"
    rako_device_id: str | None = None
    rako_mode: Literal["normal", "offline", "private"] = "normal"

    # --- LLM ---
    llm_provider: Literal["openai", "anthropic"] = "openai"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-haiku-4-5"
    anthropic_max_tokens: int = 512
    anthropic_timeout_s: float = 15.0

    # --- Voz ---
    stt_provider: Literal["google", "openai_whisper"] = "google"
    tts_provider: Literal["elevenlabs", "google"] = "elevenlabs"
    google_application_credentials: str | None = None
    google_stt_language: str = "es-CL"
    openai_stt_model: str = "whisper-1"
    google_tts_voice: str = "es-CL-Neural2-A"
    google_tts_speaking_rate: float = 0.95
    elevenlabs_api_key: str | None = None
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"
    elevenlabs_model: str = "eleven_flash_v2_5"
    elevenlabs_stability: float = 0.55
    elevenlabs_similarity_boost: float = 0.8
    # Cache de frases curadas pre-sintetizadas (rako-pregen-tts): permite
    # que crisis/derivaciones hablen sin internet. Solo audio de salida.
    tts_cache_dir: str = "./data/tts-cache"
    # STT local de fallback (whisper.cpp). Vacíos = deshabilitado; con
    # binario + modelo presentes, entra a la cadena si el cloud falla.
    whisper_cpp_bin: str | None = None
    whisper_cpp_model: str | None = None

    # --- RAG ---
    chroma_db_path: str = "./chroma_db"
    chroma_collection: str = "rako_kb"
    rag_embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    rag_top_k: int = 5
    obsidian_vault_path: str = "./knowledge-base"

    # --- SER ---
    ser_model: str = "audeering/wav2vec2-large-robust-12-ft-emotion-msp-dim"
    ser_device: str = "cpu"

    # --- Estado local ---
    sqlite_path: str = "./data/rako.db"
    sqlite_encryption_key: str | None = None

    # --- API local ---
    # Si está definido, la app móvil debe enviar Authorization: Bearer <token>.
    # En staging/prod es obligatorio; en dev se permite omitirlo para pruebas locales.
    rako_api_token: str | None = None

    # --- Setup WiFi ---
    # Por seguridad, el API puede registrar el SSID para onboarding, pero solo
    # ejecuta `nmcli` cuando este flag está activo.
    rako_wifi_apply_enabled: bool = False
    rako_setup_hotspot_enabled: bool = False
    rako_setup_hotspot_ssid_prefix: str = "Rako-Setup"
    rako_setup_hotspot_interface: str = "wlan0"
    rako_setup_hotspot_url: str = "http://10.42.0.1:8765/setup"

    # --- WhatsApp ---
    whatsapp_client: Literal["memory", "cloud"] = "memory"
    whatsapp_cloud_access_token: str | None = None
    whatsapp_cloud_phone_number_id: str | None = None
    whatsapp_cloud_api_version: str = "v20.0"
    whatsapp_cloud_verify_token: str | None = None
    whatsapp_cloud_app_secret: str | None = None
    whatsapp_cloud_timeout_s: float = 10.0

    # --- OTA ---
    rako_release_channel: Literal["stable", "beta", "dev"] = "stable"
    rako_update_manifest_path: str | None = None
    rako_update_public_key_path: str | None = None
    rako_update_apply_enabled: bool = False

    # --- Wake word ---
    # `text_stt` es fallback dev: transcribe audio con STT y busca texto.
    # Para producto, preferir `porcupine` con keyword custom entrenada para Rako.
    wake_word_engine: Literal["text_stt", "porcupine"] = "text_stt"
    wake_words: str = "hey rako,hola rako,oye rako"
    porcupine_access_key: str | None = None
    porcupine_keyword_path: str | None = None
    porcupine_sensitivity: float = 0.65

    # --- Firebase ---
    firebase_credentials_path: str | None = None
    firebase_project_id: str | None = None

    # --- DND ---
    do_not_disturb_start: str = "22:00"
    do_not_disturb_end: str = "08:00"

    @property
    def wake_words_tuple(self) -> tuple[str, ...]:
        return tuple(w.strip() for w in self.wake_words.split(",") if w.strip())
