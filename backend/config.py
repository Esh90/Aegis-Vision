"""Application configuration and paths."""

import os
from pathlib import Path


IS_CLOUD = os.getenv("ENVIRONMENT", "local") == "cloud" or os.getenv("RENDER") is not None


class Config:
    """Central configuration for Aegis-Vision backend."""

    FACE_DATABASE_DIR = Path("./face_database")
    MODELS_DIR = Path("./models")
    VIDEO_UPLOADS_DIR = Path("./video_uploads")
    CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.4"))
    FACE_DETECTION_CONFIDENCE = float(os.getenv("FACE_DETECTION_CONFIDENCE", "0.5"))
    MAX_DETECTIONS_BUFFER = 500
    SUPPORTED_VIDEO_FORMATS = [".mp4", ".avi", ".mov", ".mkv", ".flv", ".wmv"]

    ALLOWED_ORIGINS = [
        o.strip()
        for o in os.getenv(
            "ALLOWED_ORIGINS",
            "http://localhost:5173,http://localhost:3000",
        ).split(",")
    ]

    @classmethod
    def ensure_dirs(cls) -> None:
        cls.FACE_DATABASE_DIR.mkdir(exist_ok=True)
        cls.MODELS_DIR.mkdir(exist_ok=True)
        cls.VIDEO_UPLOADS_DIR.mkdir(exist_ok=True)
