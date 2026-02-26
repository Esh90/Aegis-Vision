"""Video source: upload, set-source, start-webcam, stop-stream, progress, session-stats."""

import asyncio
import time
from pathlib import Path

from fastapi import APIRouter, File, Form, UploadFile

from config import Config
from state import surveillance_state
import processor_instance as proc_inst
from video_processor import VideoProcessor
from .stream import process_frames_background

router = APIRouter()


@router.post("/api/video/upload")
async def upload_video(file: UploadFile = File(...)):
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in Config.SUPPORTED_VIDEO_FORMATS:
        return {
            "success": False,
            "error": f"Unsupported format. Supported: {', '.join(Config.SUPPORTED_VIDEO_FORMATS)}",
        }
    try:
        ts = int(time.time() * 1000)
        filename = f"video_{ts}{file_ext}"
        file_path = Config.VIDEO_UPLOADS_DIR / filename
        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)
        return {
            "success": True,
            "filename": filename,
            "filepath": str(file_path),
            "size_mb": len(contents) / (1024 * 1024),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/api/video/set-source")
async def set_video_source(
    source_type: str = Form(...),
    source_path: str = Form(None),
    camera_id: str = Form("CAM-001"),
    location: str = Form("Unknown"),
):
    try:
        if proc_inst.video_processor and proc_inst.video_processor.running:
            proc_inst.video_processor.stop()
        if source_type == "webcam":
            source = 0
        elif source_type == "file":
            if not source_path:
                return {"success": False, "error": "File path required for file source"}
            source = str(Config.VIDEO_UPLOADS_DIR / source_path)
            if not Path(source).exists():
                return {"success": False, "error": f"Video file not found: {source_path}"}
        elif source_type == "rtsp":
            if not source_path:
                return {"success": False, "error": "RTSP URL required"}
            source = source_path
        else:
            return {"success": False, "error": f"Unknown source type: {source_type}"}
        vp = VideoProcessor(source=source, camera_id=camera_id, location=location, source_type=source_type)
        proc_inst.set_video_processor(vp)
        with surveillance_state.lock:
            surveillance_state.video_source_type = source_type
            surveillance_state.video_source_path = source_path
            surveillance_state.detections.clear()
        if not vp.start():
            return {"success": False, "error": "Failed to start video source"}
        if proc_inst.frame_processing_task and not proc_inst.frame_processing_task.done():
            proc_inst.frame_processing_task.cancel()
            try:
                await proc_inst.frame_processing_task
            except asyncio.CancelledError:
                pass
        proc_inst.set_frame_processing_task(asyncio.create_task(process_frames_background()))
        return {
            "success": True,
            "source_type": source_type,
            "source_path": source_path,
            "camera_id": camera_id,
            "location": location,
            "total_frames": vp.total_frames if source_type == "file" else None,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/api/start-webcam/{camera_index}")
async def start_webcam(camera_index: int):
    try:
        # Reset shared frame buffer so "ready" can't be stale
        with surveillance_state.latest_frame_lock:
            surveillance_state.latest_frame = None
            surveillance_state.latest_processed_frame = None

        if proc_inst.video_processor and proc_inst.video_processor.running:
            proc_inst.video_processor.stop()
        if proc_inst.frame_processing_task and not proc_inst.frame_processing_task.done():
            proc_inst.frame_processing_task.cancel()
            try:
                await proc_inst.frame_processing_task
            except asyncio.CancelledError:
                pass
        vp = VideoProcessor(
            source=camera_index,
            camera_id=f"CAM-{camera_index:03d}",
            location=f"Camera {camera_index}",
            source_type="webcam",
        )
        proc_inst.set_video_processor(vp)
        if not vp.start():
            return {"success": False, "error": f"Failed to open camera {camera_index}"}

        # Start single-producer processing
        proc_inst.set_frame_processing_task(asyncio.create_task(process_frames_background()))

        # Wait for first raw frame (proves camera is truly delivering frames).
        # Processing can be slow on CPU, so don't gate "camera started" on AI speed.
        ready = False
        for _ in range(50):  # ~5s
            with surveillance_state.latest_frame_lock:
                ready = surveillance_state.latest_frame is not None
            if ready:
                break
            await asyncio.sleep(0.1)

        if not ready:
            try:
                if proc_inst.frame_processing_task and not proc_inst.frame_processing_task.done():
                    proc_inst.frame_processing_task.cancel()
            except Exception:
                pass
            try:
                vp.stop()
            except Exception:
                pass
            return {
                "success": False,
                "error": (
                    f"Camera {camera_index} opened but no frames were received within 5s. "
                    "This is usually caused by camera privacy permissions, another app using the camera, "
                    "or a driver/backend issue."
                ),
            }

        return {"success": True, "camera_index": camera_index, "message": f"Camera {camera_index} started"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/api/stop-stream")
async def stop_stream():
    try:
        if proc_inst.frame_processing_task and not proc_inst.frame_processing_task.done():
            proc_inst.frame_processing_task.cancel()
            try:
                await proc_inst.frame_processing_task
            except asyncio.CancelledError:
                pass
        if proc_inst.video_processor and proc_inst.video_processor.running:
            proc_inst.video_processor.stop()
            print("[Video] Stream stopped")
        return {"success": True, "message": "Stream stopped"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/api/video/progress")
async def get_video_progress():
    with surveillance_state.lock:
        total = surveillance_state.video_total_frames
        current = surveillance_state.video_current_frame
        pct = (current / total * 100) if total > 0 else 0
        return {
            "source_type": surveillance_state.video_source_type,
            "current_frame": current,
            "total_frames": total,
            "progress_percentage": pct,
            "processing_complete": surveillance_state.video_processing_complete,
        }


@router.get("/api/video/session-stats")
async def get_session_stats():
    with surveillance_state.lock:
        stats = surveillance_state.current_session_stats.copy()
        stats["unique_individuals"] = len(stats["unique_individuals"])
        return stats
