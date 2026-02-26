"""Global surveillance state (thread-safe)."""

from collections import deque
from datetime import datetime
from typing import List, Set, Any
import threading
import time

# Avoid circular import: Config used for maxlen only
from config import Config


class SurveillanceState:
    """Shared state for detections, watchlist, video source, and session stats."""

    def __init__(self) -> None:
        self.detections: deque = deque(maxlen=Config.MAX_DETECTIONS_BUFFER)
        self.enhancement_enabled = True
        self.active_connections: List[Any] = []  # WebSocket
        self.face_embeddings_db: dict = {}
        self.lock = threading.Lock()
        self.frame_count = 0
        self.fps = 0.0
        self.last_fps_time = time.time()

        self.video_source_type = "webcam"
        self.video_source_path = None
        self.video_total_frames = 0
        self.video_current_frame = 0
        self.video_processing_complete = False
        self.current_session_stats = {
            "total_faces": 0,
            "unique_individuals": set(),
            "high_risk_count": 0,
            "medium_risk_count": 0,
            "low_risk_count": 0,
            "unknown_count": 0,
            "start_time": None,
            "end_time": None,
        }
        # Single producer: writes latest_frame and latest_processed_frame; stream only encodes
        self.latest_frame = None
        self.latest_processed_frame = None
        self.latest_frame_lock = threading.Lock()

    def reset_session_stats(self) -> None:
        with self.lock:
            self.current_session_stats = {
                "total_faces": 0,
                "unique_individuals": set(),
                "high_risk_count": 0,
                "medium_risk_count": 0,
                "low_risk_count": 0,
                "unknown_count": 0,
                "start_time": datetime.now().isoformat(),
                "end_time": None,
            }
            self.video_processing_complete = False
            self.video_current_frame = 0


surveillance_state = SurveillanceState()
