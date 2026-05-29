from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class SettingsUpdateRequest(BaseModel):
    speechRecognitionApiUrl: str | None = None
    speechRecognitionAppKey: str | None = None
    speechRecognitionApiKey: str | None = None
    speechRecognitionModel: str | None = None
    ocrRecognitionApiUrl: str | None = None
    ocrRecognitionApiKey: str | None = None
    ocrRecognitionModel: str | None = None
    videoRecognitionApiUrl: str | None = None
    videoRecognitionApiKey: str | None = None
    videoRecognitionModel: str | None = None
    chatApiUrl: str | None = None
    chatApiKey: str | None = None
    chatModel: str | None = None


class AnalysisRequest(BaseModel):
    methodName: str = "standard"
    frameInterval: int = 5
    persistToDb: bool = False
    force: bool = False
    videoIds: list[str] | None = None
    settings: dict[str, Any] | None = None


class Task3MaterialPayload(BaseModel):
    id: str | None = None
    type: str = "text"
    name: str = "文本素材"
    text: str | None = None
    tags: list[str] = []


class Task3InputCreateRequest(BaseModel):
    topic: str = ""
    sellingPoints: list[str] = []
    copyText: str | None = None
    targetAudience: str | None = None
    platform: str | None = None
    stylePreference: str | None = None
    sourceAnalysisVideoIds: list[str] = []
    materials: list[Task3MaterialPayload] = []


class Task3InputUpdateRequest(BaseModel):
    topic: str | None = None
    sellingPoints: list[str] | None = None
    copyText: str | None = None
    targetAudience: str | None = None
    platform: str | None = None
    stylePreference: str | None = None
    materials: list[Task3MaterialPayload] | None = None


class Task3AnalyzeRequest(BaseModel):
    settings: dict[str, Any] | None = None
    videoId: str | None = None


class Task3GapUpdateRequest(BaseModel):
    gaps: list[dict[str, Any]]


class CompositionCreateRequest(BaseModel):
    videoId: str
    task3InputId: str
    task3AnalysisId: str
    versionStyle: str = "balanced"
    useFallback: bool = False
