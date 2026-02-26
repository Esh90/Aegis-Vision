"""
Aegis-Vision Surveillance System - PRODUCTION Backend
Competition-Grade: YOLOv11 + FaceNet + Super-Resolution + Motion Deblur
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import Config, IS_CLOUD
from state import surveillance_state
from ai_models import ai_models, YOLO_AVAILABLE, DEEPFACE_AVAILABLE, ESRGAN_AVAILABLE
from video_processor import VideoProcessor
from watchlist_disk import load_watchlist_from_disk
from processor_instance import set_video_processor
from routes import stream_router, watchlist_router, video_router, misc_router

app = FastAPI(
    title="Aegis-Vision Competition API",
    docs_url="/docs" if not IS_CLOUD else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.ALLOWED_ORIGINS if IS_CLOUD else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Config.ensure_dirs()

app.include_router(stream_router)
app.include_router(watchlist_router)
app.include_router(video_router)
app.include_router(misc_router)


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "service": "Aegis-Vision Surveillance API",
        "environment": "cloud" if IS_CLOUD else "local",
        "models": {
            "yolo": YOLO_AVAILABLE,
            "deepface": DEEPFACE_AVAILABLE,
            "esrgan": ESRGAN_AVAILABLE,
        },
    }


@app.get("/")
async def root():
    return {"status": "ok", "docs": "/docs"}


@app.on_event("startup")
async def startup_event():
    print("\n" + "=" * 60)
    print("AEGIS-VISION SURVEILLANCE SYSTEM")
    print("=" * 60)
    print(f"Environment: {'CLOUD' if IS_CLOUD else 'LOCAL'}")
    print(f"Models: YOLO={YOLO_AVAILABLE}, DeepFace={DEEPFACE_AVAILABLE}, ESRGAN={ESRGAN_AVAILABLE}")
    if ai_models:
        print(f"Face recognition: {ai_models.face_recognition_model}")
    load_watchlist_from_disk()
    if not IS_CLOUD:
        set_video_processor(
            VideoProcessor(source=0, camera_id="CAM-001", location="Main Entrance", source_type="webcam")
        )
    print("=" * 60 + "\n")


@app.on_event("shutdown")
async def shutdown_event():
    from processor_instance import video_processor
    if video_processor and video_processor.running:
        video_processor.stop()


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
