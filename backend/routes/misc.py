"""Misc API: toggle-enhancement, detections, export-log, stats."""

from datetime import datetime

from fastapi import APIRouter

from state import surveillance_state
from ai_models import YOLO_AVAILABLE, DEEPFACE_AVAILABLE, ESRGAN_AVAILABLE, ai_models
import processor_instance as proc_inst

router = APIRouter()


@router.post("/api/toggle-enhancement")
async def toggle_enhancement():
    surveillance_state.enhancement_enabled = not surveillance_state.enhancement_enabled
    return {"enabled": surveillance_state.enhancement_enabled}


@router.get("/api/detections")
async def get_detections(limit: int = 50):
    with surveillance_state.lock:
        recent = list(surveillance_state.detections)[-limit:]
    return {"detections": recent, "total": len(surveillance_state.detections)}


@router.get("/api/export-log")
async def export_log():
    vp = proc_inst.video_processor
    with surveillance_state.lock:
        return {
            "export_time": datetime.now().isoformat(),
            "camera_id": vp.camera_id if vp else None,
            "location": vp.location if vp else None,
            "total_detections": len(surveillance_state.detections),
            "detections": list(surveillance_state.detections),
        }


@router.get("/api/stats")
async def get_stats():
    with surveillance_state.lock:
        detections = list(surveillance_state.detections)
    high_risk = sum(1 for d in detections if d.get("risk_level") == "HIGH")
    medium_risk = sum(1 for d in detections if d.get("risk_level") == "MEDIUM")
    known = sum(1 for d in detections if not (d.get("person_id") or "").startswith("unknown"))
    return {
        "total_detections": len(detections),
        "high_risk_count": high_risk,
        "medium_risk_count": medium_risk,
        "known_persons": known,
        "unknown_persons": len(detections) - known,
        "watchlist_size": len(surveillance_state.face_embeddings_db),
        "enhancement_enabled": surveillance_state.enhancement_enabled,
        "active_connections": len(surveillance_state.active_connections),
        "fps": round(surveillance_state.fps, 2),
        "models_loaded": {
            "yolo": YOLO_AVAILABLE and ai_models is not None and ai_models.yolo_model is not None,
            "deepface": DEEPFACE_AVAILABLE,
            "esrgan": ESRGAN_AVAILABLE and ai_models is not None and ai_models.upsampler is not None,
        },
    }
