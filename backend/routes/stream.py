"""Stream and WebSocket endpoints."""

import asyncio
import json
import time
from collections import deque

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
import cv2

from state import surveillance_state
import processor_instance as proc_inst

router = APIRouter()


async def broadcast_message(message: str) -> None:
    disconnected = []
    for conn in surveillance_state.active_connections:
        try:
            await conn.send_text(message)
        except Exception:
            disconnected.append(conn)
    for conn in disconnected:
        surveillance_state.active_connections.remove(conn)


def _read_frame(vp):
    """Blocking: read one frame (fast)."""
    success, frame = vp.cap.read()
    if not success or frame is None or frame.size == 0:
        return None
    return frame


def _process_frame(vp, frame):
    """Blocking: heavy processing (YOLO/DeepFace/HUD)."""
    processed_frame, detections = vp.process_frame(frame)
    return processed_frame, detections


async def process_frames_background() -> None:
    """Single producer: read camera in thread, update latest_frame, store detections, broadcast."""
    vp = proc_inst.video_processor
    if not vp or not vp.running:
        return
    while vp.running:
        try:
            frame = await asyncio.to_thread(_read_frame, vp)
            if frame is None:
                await asyncio.sleep(0.1)
                continue
            with surveillance_state.latest_frame_lock:
                surveillance_state.latest_frame = frame.copy()

            # Heavy processing off the event loop
            processed_frame, detections = await asyncio.to_thread(_process_frame, vp, frame)
            with surveillance_state.latest_frame_lock:
                surveillance_state.latest_processed_frame = processed_frame
            with surveillance_state.lock:
                for det in detections:
                    surveillance_state.detections.append(det)
            if detections and surveillance_state.active_connections:
                msg = json.dumps({"type": "detection", "data": detections})
                high_risk = [d for d in detections if d.get("risk_level") == "HIGH"]
                if high_risk:
                    await broadcast_message(
                        json.dumps({"type": "alert", "severity": "high", "data": high_risk})
                    )
                await broadcast_message(msg)
            await asyncio.sleep(0.001)
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[Stream] Error in frame processing: {e}")
            await asyncio.sleep(0.1)


async def generate_frames():
    """Stream generator: read latest_processed_frame only (no heavy work), encode, yield."""
    # Re-read processor on every iteration so we always use the current one.
    frame_times: deque = deque(maxlen=30)
    while True:
        vp = proc_inst.video_processor
        if not vp or not vp.running:
            await asyncio.sleep(0.1)
            continue
        start_time = time.time()
        with surveillance_state.latest_frame_lock:
            processed = surveillance_state.latest_processed_frame
        if processed is None:
            await asyncio.sleep(0.03)
            continue
        elapsed = time.time() - start_time
        frame_times.append(elapsed)
        if frame_times:
            avg = sum(frame_times) / len(frame_times)
            surveillance_state.fps = 1.0 / max(avg, 0.001)
        _, buffer = cv2.imencode(".jpg", processed, [cv2.IMWRITE_JPEG_QUALITY, 85])
        yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n"
        await asyncio.sleep(0.033)  # ~30fps max for stream


@router.get("/api/stream")
async def video_stream():
    # Always return the generator; it waits for the processor to become ready.
    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.websocket("/api/logs")
async def websocket_logs(websocket: WebSocket):
    await websocket.accept()
    surveillance_state.active_connections.append(websocket)
    try:
        with surveillance_state.lock:
            initial_data = list(surveillance_state.detections)[-50:]
        await websocket.send_text(json.dumps({"type": "initial", "data": initial_data}))
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        surveillance_state.active_connections.remove(websocket)
