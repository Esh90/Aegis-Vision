"""AI model loading: YOLOv11, Haar, Real-ESRGAN, DeepFace."""

import cv2
import numpy as np
from pathlib import Path

from config import Config

# Optional imports
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    print("WARN: YOLOv11 not installed. Run: pip install ultralytics")

try:
    from deepface import DeepFace
    DEEPFACE_AVAILABLE = True
except ImportError:
    DEEPFACE_AVAILABLE = False
    print("WARN: DeepFace not installed. Run: pip install deepface")

try:
    from realesrgan import RealESRGANer
    from basicsr.archs.rrdbnet_arch import RRDBNet
    ESRGAN_AVAILABLE = True
except ImportError:
    ESRGAN_AVAILABLE = False
    print("WARN: Real-ESRGAN not installed. Run: pip install realesrgan basicsr")


class AIModels:
    """Singleton for AI model management."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        print("[Aegis] Loading AI Models...")

        if YOLO_AVAILABLE:
            try:
                model_path = Config.MODELS_DIR / "yolo11n-face.pt"
                if not model_path.exists():
                    print("[Aegis] Downloading YOLOv11 face detection model...")
                    self.yolo_model = YOLO("yolo11n.pt")
                else:
                    self.yolo_model = YOLO(str(model_path))
                print("[Aegis] YOLOv11 loaded")
            except Exception as e:
                print(f"WARN: YOLOv11 failed: {e}")
                self.yolo_model = None
        else:
            self.yolo_model = None

        self.haar_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )

        if ESRGAN_AVAILABLE:
            try:
                model = RRDBNet(
                    num_in_ch=3, num_out_ch=3, num_feat=64,
                    num_block=23, num_grow_ch=32, scale=4
                )
                self.upsampler = RealESRGANer(
                    scale=4,
                    model_path="https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
                    model=model,
                    tile=0,
                    tile_pad=10,
                    pre_pad=0,
                    half=False,
                )
                print("[Aegis] Real-ESRGAN super-resolution loaded")
            except Exception as e:
                print(f"WARN: Real-ESRGAN failed: {e}")
                self.upsampler = None
        else:
            self.upsampler = None

        self.face_recognition_model = "Facenet512"
        if DEEPFACE_AVAILABLE:
            try:
                print("[Aegis] Warming up DeepFace...")
                DeepFace.represent(
                    np.zeros((224, 224, 3), dtype=np.uint8),
                    model_name=self.face_recognition_model,
                    enforce_detection=False,
                )
                print(f"[Aegis] DeepFace ({self.face_recognition_model}) ready")
            except Exception as e:
                print(f"WARN: DeepFace warmup failed: {e}")

        self._initialized = True
        print("[Aegis] All AI models initialized\n")


# Eager load at import so stream/watchlist work immediately
ai_models = AIModels()
