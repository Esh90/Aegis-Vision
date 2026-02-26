"""
Production-grade video processor: enhancement, face detection, recognition, HUD.
"""

import base64
import time
from datetime import datetime
import cv2
import numpy as np

from config import Config
from state import surveillance_state
from ai_models import ai_models, DEEPFACE_AVAILABLE

if DEEPFACE_AVAILABLE:
    from deepface import DeepFace


class VideoProcessor:
    """Full AI pipeline: enhance -> detect -> recognize -> draw -> HUD."""

    def __init__(
        self,
        source=0,
        camera_id="CAM-001",
        location="Unknown",
        source_type="webcam",
    ):
        self.source = source
        self.camera_id = camera_id
        self.location = location
        self.source_type = source_type
        self.cap = None
        self.running = False
        self.frame_skip_counter = 0
        self.face_recognition_interval = 10
        self.total_frames = 0
        self.current_frame_number = 0
        self.prev_frame_gray = None
        self.prev_faces = []
        self.vehicle_speeds = []
        self.fps = 30

    def start(self) -> bool:
        """Initialize video capture."""
        print(f"\n[Video] Starting source: {self.source_type} -> {self.source}")

        self.backend_name = None

        # Webcam/capture devices (Windows): try multiple backends and validate a real frame.
        if isinstance(self.source, int):
            attempted = []
            backends = [
                ("DSHOW", cv2.CAP_DSHOW),
                ("MSMF", cv2.CAP_MSMF),
                ("DEFAULT", None),
            ]

            cap = None
            for name, backend in backends:
                try:
                    attempted.append(name)
                    cap = (
                        cv2.VideoCapture(self.source, backend)
                        if backend is not None
                        else cv2.VideoCapture(self.source)
                    )
                    if not cap.isOpened():
                        cap.release()
                        cap = None
                        continue

                    # IMPORTANT: For MSMF/DEFAULT, don't set width/height/FourCC before first read.
                    # Many drivers will log "Failed to select stream 0" and then deliver no frames.
                    if backend == cv2.CAP_DSHOW:
                        # DSHOW sometimes needs an explicit format to avoid orange/black frames.
                        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
                        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                        cap.set(cv2.CAP_PROP_FPS, 30)
                        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    else:
                        # Keep it minimal first.
                        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

                    # Validate a real frame
                    ok, frame = cap.read()
                    if not ok or frame is None or frame.size == 0:
                        cap.release()
                        cap = None
                        continue

                    # Reject "dead" frames (black)
                    try:
                        if frame.std() < 2:
                            print(f"[Video] {name}: rejected black frame (std={frame.std():.1f})")
                            cap.release()
                            cap = None
                            continue
                    except Exception:
                        pass

                    # Reject DroidCam orange placeholder frames (high R+G, low B)
                    try:
                        avg_bgr = frame.mean(axis=(0, 1))
                        if avg_bgr[2] > 150 and avg_bgr[1] > 80 and avg_bgr[0] < 80:
                            print(f"[Video] {name}: rejected orange DroidCam frame (BGR={avg_bgr[0]:.0f},{avg_bgr[1]:.0f},{avg_bgr[2]:.0f})")
                            cap.release()
                            cap = None
                            continue
                    except Exception:
                        pass

                    self.cap = cap
                    self.fps = 30
                    self.backend_name = name
                    try:
                        h, w = frame.shape[:2]
                        print(f"[Video] Camera backend OK: {name} | first frame {w}x{h} std={frame.std():.1f}")
                    except Exception:
                        print(f"[Video] Camera backend OK: {name}")
                    break
                except Exception:
                    try:
                        if cap is not None:
                            cap.release()
                    except Exception:
                        pass
                    cap = None

            if not self.cap or not self.cap.isOpened():
                print(f"[Video] Failed to open camera index {self.source}. Tried: {', '.join(attempted)}")
                return False

        # Files / RTSP
        else:
            self.cap = cv2.VideoCapture(self.source)
            if not self.cap.isOpened():
                print(f"[Video] Failed to open source: {self.source}")
                return False

        if not self.cap.isOpened():
            print(f"[Video] Failed to open source: {self.source}")
            return False

        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        if self.fps == 0 or self.fps > 60:
            self.fps = 30

        if isinstance(self.source, int):
            # For non-DSHOW backends, don't force resolution here; keep driver defaults for stability.
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            self.fps = 30

        if self.source_type == "file":
            self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = self.total_frames / self.fps if self.fps > 0 else 0
            print(f"   Video: {self.total_frames} frames, {self.fps:.2f} FPS, {duration:.2f}s")
            surveillance_state.video_total_frames = self.total_frames

        self.running = True
        print("[Video] Source started successfully")
        surveillance_state.reset_session_stats()
        return True

    def stop(self) -> None:
        self.running = False
        if self.cap:
            self.cap.release()

    # ---------- Enhancement ----------

    def enhance_low_light(self, frame: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        avg_brightness = gray.mean()
        if avg_brightness > 100:
            lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))
            l = clahe.apply(l)
            return cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)
        elif avg_brightness > 50:
            lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
            l = clahe.apply(l)
            enhanced = cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)
            gamma, inv = 1.2, 1.0 / 1.2
            table = np.array([((i / 255.0) ** inv) * 255 for i in range(256)]).astype("uint8")
            return cv2.LUT(enhanced, table)
        else:
            frame_float = frame.astype(np.float32) / 255.0
            def single_scale_retinex(img, sigma):
                blurred = cv2.GaussianBlur(img, (0, 0), sigma)
                return np.log10(img + 1e-6) - np.log10(blurred + 1e-6)
            scales = [15, 80, 250]
            msr_output = np.zeros_like(frame_float)
            for scale in scales:
                for i in range(3):
                    msr_output[:, :, i] += single_scale_retinex(frame_float[:, :, i], scale)
            msr_output /= len(scales)
            msr_min, msr_max = msr_output.min(), msr_output.max()
            msr_normalized = ((msr_output - msr_min) / (msr_max - msr_min + 1e-6) * 255).astype(np.uint8)
            lab = cv2.cvtColor(msr_normalized, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            l = clahe.apply(l)
            enhanced = cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)
            gamma, inv = 1.5, 1.0 / 1.5
            table = np.array([((i / 255.0) ** inv) * 255 for i in range(256)]).astype("uint8")
            return cv2.LUT(enhanced, table)

    def correct_motion_blur(self, frame: np.ndarray) -> np.ndarray:
        gaussian = cv2.GaussianBlur(frame, (5, 5), 1.5)
        return cv2.addWeighted(frame, 1.5, gaussian, -0.5, 0)

    def super_resolve_face(self, face_img: np.ndarray) -> np.ndarray:
        h, w = face_img.shape[:2]
        if ai_models.upsampler is not None and (h < 128 or w < 128):
            try:
                output, _ = ai_models.upsampler.enhance(face_img, outscale=4)
                return output
            except Exception:
                pass
        if face_img.shape[0] < 128:
            scale = 128 / face_img.shape[0]
            upscaled = cv2.resize(face_img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            gaussian = cv2.GaussianBlur(upscaled, (0, 0), 2.0)
            return cv2.addWeighted(upscaled, 1.5, gaussian, -0.5, 0)
        return face_img

    # ---------- Detection ----------

    def detect_faces_yolo(self, frame: np.ndarray) -> list:
        if ai_models.yolo_model is None:
            return []
        try:
            results = ai_models.yolo_model(frame, conf=Config.FACE_DETECTION_CONFIDENCE, verbose=False)
            faces = []
            for result in results:
                for box in result.boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    conf = float(box.conf[0])
                    faces.append((x1, y1, x2 - x1, y2 - y1, conf))
            return faces
        except Exception:
            return []

    def detect_faces_haar(self, frame: np.ndarray) -> list:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = ai_models.haar_cascade.detectMultiScale(
            gray, scaleFactor=1.05, minNeighbors=5, minSize=(40, 40)
        )
        return [(x, y, w, h, 0.8) for x, y, w, h in faces]

    def detect_faces(self, frame: np.ndarray) -> list:
        faces = self.detect_faces_yolo(frame)
        if not faces:
            faces = self.detect_faces_haar(frame)
        return faces

    # ---------- Recognition ----------

    def extract_face_embedding(self, face_img: np.ndarray):
        if not DEEPFACE_AVAILABLE:
            return None
        try:
            face_rgb = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
            if face_rgb.shape[0] < 80 or face_rgb.shape[1] < 80:
                face_rgb = cv2.resize(face_rgb, (112, 112))
            embedding = DeepFace.represent(
                face_rgb,
                model_name=ai_models.face_recognition_model,
                enforce_detection=False,
                detector_backend="skip",
            )
            if embedding and len(embedding) > 0:
                return np.array(embedding[0]["embedding"])
        except Exception:
            pass
        return None

    def match_face(self, embedding) -> tuple:
        if embedding is None:
            return None, 0.0, {}
        if not surveillance_state.face_embeddings_db:
            return None, 0.0, {}
        best_match = None
        best_distance = float("inf")
        with surveillance_state.lock:
            for person_id, data in surveillance_state.face_embeddings_db.items():
                db_emb = data["embedding"]
                dot = np.dot(embedding, db_emb)
                norm_a = np.linalg.norm(embedding)
                norm_b = np.linalg.norm(db_emb)
                cosine_sim = dot / (norm_a * norm_b + 1e-8)
                distance = 1 - cosine_sim
                if distance < best_distance:
                    best_distance = distance
                    best_match = person_id
        confidence = max(0, 1 - (best_distance / 0.8))
        if confidence > Config.CONFIDENCE_THRESHOLD and best_match is not None:
            metadata = surveillance_state.face_embeddings_db[best_match]["metadata"]
            return best_match, confidence, metadata
        return None, confidence, {}

    # ---------- Main processing ----------

    def _get_risk_color(self, risk_level: str) -> tuple:
        colors = {
            "HIGH": (0, 0, 255),
            "MEDIUM": (0, 165, 255),
            "LOW": (0, 255, 0),
            "UNKNOWN": (128, 128, 128),
        }
        return colors.get(risk_level, (255, 255, 255))

    def estimate_vehicle_speed(self, frame: np.ndarray, current_faces: list):
        if not current_faces or not self.prev_faces:
            self.prev_faces = current_faces
            return None
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if self.prev_frame_gray is None:
            self.prev_frame_gray = gray
            self.prev_faces = current_faces
            return None
        try:
            curr_face, prev_face = current_faces[0], self.prev_faces[0]
            curr_cx = (curr_face[0] + curr_face[2]) / 2
            prev_cx = (prev_face[0] + prev_face[2]) / 2
            displacement_px = abs(curr_cx - prev_cx)
            if displacement_px > 2:
                pixels_per_meter = 20
                displacement_m = displacement_px / pixels_per_meter
                time_interval = 1.0 / self.fps
                speed_kmh = (displacement_m / time_interval) * 3.6
                speed_kmh = np.clip(speed_kmh, 10, 200)
                self.vehicle_speeds.append(speed_kmh)
                if len(self.vehicle_speeds) > 30:
                    self.vehicle_speeds.pop(0)
                self.prev_frame_gray = gray
                self.prev_faces = current_faces
                return int(np.mean(self.vehicle_speeds))
        except Exception:
            pass
        self.prev_frame_gray = gray
        self.prev_faces = current_faces
        return None

    def add_hud_overlay(
        self,
        frame: np.ndarray,
        face_count: int,
        timestamp: datetime,
        vehicle_speed=None,
    ) -> np.ndarray:
        overlay = frame.copy()
        h, w = frame.shape[:2]
        color = (59, 130, 246)
        bracket_len, thickness = 40, 2
        for (px, py) in [(20, 20), (w - 20, 20), (20, h - 20), (w - 20, h - 20)]:
            dx = -bracket_len if px > w // 2 else bracket_len
            dy = bracket_len if py < h // 2 else -bracket_len
            cv2.line(overlay, (px, py), (px + dx, py), color, thickness)
            cv2.line(overlay, (px, py), (px, py + dy), color, thickness)
        time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        cv2.putText(overlay, f"AEGIS-VISION | {time_str}", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        cv2.putText(overlay, f"{self.camera_id} | {self.location}", (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        speed_str = f" | SPEED: {vehicle_speed} km/h" if vehicle_speed else ""
        cv2.putText(
            overlay,
            f"TARGETS: {face_count} | FPS: {surveillance_state.fps:.1f}{speed_str}",
            (30, h - 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            color,
            2,
        )
        scan_y = int((time.time() % 2) * h / 2)
        cv2.line(overlay, (0, scan_y), (w, scan_y), color, 1)
        return cv2.addWeighted(overlay, 0.85, frame, 0.15, 0)

    def process_frame(self, frame: np.ndarray) -> tuple:
        processed = frame.copy()
        if surveillance_state.enhancement_enabled:
            avg_brightness = cv2.cvtColor(processed, cv2.COLOR_BGR2GRAY).mean()
            if avg_brightness < 120:
                processed = self.enhance_low_light(processed)
        faces = self.detect_faces(processed)
        detections = []
        timestamp = datetime.now()
        self.frame_skip_counter += 1
        skip_recognition = self.frame_skip_counter % self.face_recognition_interval != 0

        for idx, (x, y, w, h, det_conf) in enumerate(faces):
            face_crop = processed[y : y + h, x : x + w]
            if face_crop.size == 0:
                continue
            if w < 128 or h < 128:
                face_crop = self.super_resolve_face(face_crop)
            embedding = None
            person_id = None
            match_conf = 0.0
            metadata = {}
            if not skip_recognition:
                embedding = self.extract_face_embedding(face_crop)
                person_id, match_conf, metadata = self.match_face(embedding)
            if person_id:
                name = surveillance_state.face_embeddings_db[person_id]["metadata"].get("name", "Unknown")
                risk_level = surveillance_state.face_embeddings_db[person_id]["metadata"].get("risk_level", "UNKNOWN")
                display_conf = match_conf
            else:
                name = "Unknown"
                risk_level = "UNKNOWN"
                person_id = f"unknown_{int(time.time() * 1000)}_{idx}"
                display_conf = det_conf if skip_recognition else match_conf
            color = self._get_risk_color(risk_level)
            cv2.rectangle(processed, (x, y), (x + w, y + h), color, 2)
            label = f"{name} ({display_conf:.0%})"
            (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(processed, (x, y - lh - 10), (x + lw, y), color, -1)
            cv2.putText(processed, label, (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            _, buffer = cv2.imencode(".jpg", face_crop)
            face_b64 = base64.b64encode(buffer).decode("utf-8")
            detections.append({
                "id": f"{self.camera_id}_{int(timestamp.timestamp() * 1000)}_{idx}",
                "timestamp": timestamp.isoformat(),
                "camera_id": self.camera_id,
                "location": self.location,
                "person_id": person_id,
                "name": name,
                "confidence": float(display_conf),
                "detection_confidence": float(det_conf),
                "risk_level": risk_level,
                "bbox": {"x": int(x), "y": int(y), "w": int(w), "h": int(h)},
                "face_crop": face_b64,
                "metadata": metadata,
                "vehicle_speed": None,
            })

        with surveillance_state.lock:
            surveillance_state.current_session_stats["total_faces"] += len(faces)
            for det in detections:
                pid = det["person_id"]
                if pid and not pid.startswith("unknown_"):
                    surveillance_state.current_session_stats["unique_individuals"].add(pid)
                risk = det["risk_level"]
                if risk == "HIGH":
                    surveillance_state.current_session_stats["high_risk_count"] += 1
                elif risk == "MEDIUM":
                    surveillance_state.current_session_stats["medium_risk_count"] += 1
                elif risk == "LOW":
                    surveillance_state.current_session_stats["low_risk_count"] += 1
                else:
                    surveillance_state.current_session_stats["unknown_count"] += 1
            if self.source_type == "file":
                self.current_frame_number += 1
                surveillance_state.video_current_frame = self.current_frame_number
                if self.total_frames > 0 and self.current_frame_number >= self.total_frames:
                    surveillance_state.video_processing_complete = True
                    surveillance_state.current_session_stats["end_time"] = datetime.now().isoformat()

        vehicle_speed = self.estimate_vehicle_speed(processed, faces) if faces else None
        processed = self.add_hud_overlay(processed, len(faces), timestamp, vehicle_speed)
        return processed, detections
