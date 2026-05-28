from __future__ import annotations

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT_DIR / ".env"
DATA_DIR = ROOT_DIR / "backend_data"
UPLOAD_DIR = DATA_DIR / "uploads"
COVER_DIR = DATA_DIR / "covers"
TASK3_MATERIAL_DIR = DATA_DIR / "task3_materials"
DB_PATH = DATA_DIR / "videos.json"
ANALYSIS_CACHE_PATH = DATA_DIR / "analysis_cache.json"
TASK3_INPUTS_PATH = DATA_DIR / "task3_inputs.json"
TASK3_ANALYSIS_PATH = DATA_DIR / "task3_analysis.json"

ALLOWED_EXTENSIONS = {".mp4", ".mov"}
TASK3_ALLOWED_EXTENSIONS = {".mp4", ".mov", ".jpg", ".jpeg", ".png", ".webp", ".txt"}
MAX_UPLOAD_SIZE_BYTES = 1024 * 1024 * 1024
BROWSER_COMPATIBLE_CODECS = {"h264", "avc1", "avc"}

SETTINGS_DEFINITIONS: list[dict[str, str]] = [
    {
        "key": "speechRecognitionApiUrl",
        "label": "语音识别",
        "env_name": "SPEECH_RECOGNITION_API_URL",
        "description": "语音识别服务的 API 链接。",
    },
    {
        "key": "speechRecognitionAppKey",
        "label": "语音识别 App Key",
        "env_name": "SPEECH_RECOGNITION_APP_KEY",
        "description": "火山语音识别 X-Api-App-Key。",
    },
    {
        "key": "speechRecognitionApiKey",
        "label": "语音识别 Access Key",
        "env_name": "SPEECH_RECOGNITION_API_KEY",
        "description": "火山语音识别 X-Api-Access-Key。",
    },
    {
        "key": "speechRecognitionModel",
        "label": "语音识别模型",
        "env_name": "SPEECH_RECOGNITION_MODEL",
        "description": "语音识别服务使用的模型或资源 ID。",
    },
    {
        "key": "ocrRecognitionApiUrl",
        "label": "OCR 识别",
        "env_name": "OCR_RECOGNITION_API_URL",
        "description": "OCR 识别服务的 API 链接。",
    },
    {
        "key": "ocrRecognitionApiKey",
        "label": "OCR / 视觉识别 API Key",
        "env_name": "OCR_RECOGNITION_API_KEY",
        "description": "OCR、图片识别或视觉结构拆解模型使用的 API Key。",
    },
    {
        "key": "ocrRecognitionModel",
        "label": "OCR 识别模型",
        "env_name": "OCR_RECOGNITION_MODEL",
        "description": "OCR 识别服务使用的模型或资源 ID。",
    },
    {
        "key": "videoRecognitionApiUrl",
        "label": "视频识别",
        "env_name": "VIDEO_RECOGNITION_API_URL",
        "description": "视频识别服务的 API 链接。",
    },
    {
        "key": "videoRecognitionApiKey",
        "label": "视频识别 API Key",
        "env_name": "VIDEO_RECOGNITION_API_KEY",
        "description": "直接视频理解模型使用的 API Key。",
    },
    {
        "key": "videoRecognitionModel",
        "label": "视频识别模型",
        "env_name": "VIDEO_RECOGNITION_MODEL",
        "description": "直接视频理解服务使用的模型名称。",
    },
    {
        "key": "chatApiUrl",
        "label": "文本交互（chat）",
        "env_name": "CHAT_API_URL",
        "description": "文本交互（chat）服务的 API 链接。",
    },
    {
        "key": "chatApiKey",
        "label": "文本交互 API Key",
        "env_name": "CHAT_API_KEY",
        "description": "拆解概览、结构化总结和迁移建议模型使用的 API Key。",
    },
    {
        "key": "chatModel",
        "label": "文本交互模型",
        "env_name": "CHAT_MODEL",
        "description": "拆解概览和结构化总结使用的语言模型。",
    },
]
