from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


def _load_local_env() -> None:
    if os.getenv("VIDEO_BREAKDOWN_SKIP_DOTENV") == "1":
        return
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key in os.environ:
            continue
        value = value.strip().strip('"').strip("'")
        os.environ[key] = value


class Settings:
    def __init__(self) -> None:
        _load_local_env()
        root = Path(__file__).resolve().parents[1]
        self.root_dir = root
        self.data_dir = Path(os.getenv("VIDEO_BREAKDOWN_DATA_DIR", root / "data")).resolve()
        self.upload_dir = Path(os.getenv("VIDEO_BREAKDOWN_UPLOAD_DIR", root / "uploads")).resolve()
        self.max_upload_mb = int(os.getenv("VIDEO_BREAKDOWN_MAX_UPLOAD_MB", "120"))
        self.provider = os.getenv("VIDEO_BREAKDOWN_PROVIDER", "mock").strip().lower() or "mock"
        self.gemini_video_model = os.getenv("GEMINI_VIDEO_MODEL", "gemini-2.5-pro")
        self.gemini_script_model = os.getenv("GEMINI_SCRIPT_MODEL", os.getenv("GEMINI_VIDEO_MODEL", "gemini-3.1-pro-preview"))
        self.gemini_script_voiceover_model = os.getenv(
            "GEMINI_SCRIPT_VOICEOVER_MODEL",
            os.getenv("GEMINI_SCRIPT_VOICEOVER_REVIEW_MODEL", self.gemini_script_model),
        )
        self.gemini_persona_model = os.getenv("GEMINI_PERSONA_MODEL", self.gemini_script_model)
        self.gemini_director_model = os.getenv("GEMINI_DIRECTOR_MODEL", "gemini-3.5-flash")
        self.script_generation_stale_after_seconds = int(os.getenv("SCRIPT_GENERATION_STALE_AFTER_SECONDS", "1800"))
        self.persona_generation_stale_after_seconds = int(os.getenv("PERSONA_GENERATION_STALE_AFTER_SECONDS", "1800"))
        self.director_generation_stale_after_seconds = int(
            os.getenv("VIDEO_FACTORY_DIRECTOR_GENERATION_STALE_AFTER_SECONDS", "1800")
        )
        self.director_render_stale_after_seconds = int(
            os.getenv("VIDEO_FACTORY_DIRECTOR_RENDER_STALE_AFTER_SECONDS", "1800")
        )
        self.director_render_artifact_retention_days = int(
            os.getenv("VIDEO_FACTORY_RENDER_ARTIFACT_RETENTION_DAYS", "14")
        )
        self.video_factory_enable_hyperframes_cli = (
            os.getenv("VIDEO_FACTORY_ENABLE_HYPERFRAMES_CLI", "0").strip().lower() in {"1", "true", "yes", "on"}
        )
        self.hyperframes_cli_command = os.getenv("VIDEO_FACTORY_HYPERFRAMES_CLI", "hyperframes").strip() or "hyperframes"
        self.hyperframes_cli_timeout_seconds = int(os.getenv("VIDEO_FACTORY_HYPERFRAMES_CLI_TIMEOUT_SECONDS", "120"))
        self.hyperframes_cli_home_dir = os.getenv(
            "VIDEO_FACTORY_HYPERFRAMES_HOME_DIR",
            str(self.data_dir / "hyperframes-home"),
        ).strip()
        self.hyperframes_cli_browser_path = os.getenv("VIDEO_FACTORY_HYPERFRAMES_BROWSER_PATH", "").strip()
        self.hyperframes_cli_no_browser_gpu = (
            os.getenv("VIDEO_FACTORY_HYPERFRAMES_NO_BROWSER_GPU", "1").strip().lower()
            in {"1", "true", "yes", "on"}
        )
        self.hyperframes_cli_use_docker = (
            os.getenv("VIDEO_FACTORY_HYPERFRAMES_USE_DOCKER", "0").strip().lower() in {"1", "true", "yes", "on"}
        )
        self.hyperframes_cli_workers = os.getenv("VIDEO_FACTORY_HYPERFRAMES_WORKERS", "1").strip()
        self.google_cloud_project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "")
        self.google_cloud_location = os.getenv("GOOGLE_CLOUD_LOCATION", "global")
        self.google_vertex_ai_api_key = os.getenv("GOOGLE_VERTEX_AI_API_KEY", "")
        self.vertex_base_url = os.getenv("VERTEX_AI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")
        self.vertex_endpoint_mode = os.getenv("VERTEX_AI_ENDPOINT_MODE", "auto").strip().lower() or "auto"
        self.request_timeout_seconds = int(os.getenv("GEMINI_REQUEST_TIMEOUT_SECONDS", "300"))
        self.ytdlp_proxy = os.getenv("VIDEO_BREAKDOWN_YTDLP_PROXY", "").strip()
        self.ytdlp_cookies_file = os.getenv("VIDEO_BREAKDOWN_YTDLP_COOKIES_FILE", "").strip()

    @property
    def db_path(self) -> Path:
        return self.data_dir / "breakdowns.sqlite3"

    def gemini_generate_url(self, model_name: str | None = None) -> str:
        base_url = self.vertex_base_url.rstrip("/")
        model = model_name or self.gemini_video_model
        mode = self.gemini_endpoint_mode()
        if mode == "vertex_standard":
            project_id = self.google_cloud_project_id.strip()
            location = self.google_cloud_location.strip() or "global"
            return f"{base_url}/projects/{project_id}/locations/{location}/publishers/google/models/{model}:generateContent"
        if mode == "vertex_express":
            return f"{base_url}/publishers/google/models/{model}:generateContent"
        return f"{base_url}/models/{model}:generateContent"

    def gemini_endpoint_mode(self) -> str:
        base_url = self.vertex_base_url.lower()
        if "generativelanguage.googleapis.com" in base_url:
            return "google_ai"
        if "aiplatform.googleapis.com" in base_url:
            if self.vertex_endpoint_mode in {"standard", "project", "vertex_standard"}:
                return "vertex_standard"
            return "vertex_express"
        return "custom"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    return settings
