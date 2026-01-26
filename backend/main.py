"""
Aegis-Vision Surveillance System - PRODUCTION Backend
Competition-Grade: YOLOv11 + FaceNet + Super-Resolution + Motion Deblur
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import cv2
import numpy as np
import asyncio
import json
from datetime import datetime
from typing import List, Dict, Optional
import base64
from collections import deque
import threading
import time
from pathlib import Path

# AI/ML Imports
try:
    from ultralytics import YOLO  # YOLOv11
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    print("⚠️  YOLOv11 not installed. Run: pip install ultralytics")

try:
    from deepface import DeepFace  # Face recognition with multiple backends
    DEEPFACE_AVAILABLE = True
except ImportError:
    DEEPFACE_AVAILABLE = False
    print("⚠️  DeepFace not installed. Run: pip install deepface")

try:
    from realesrgan import RealESRGANer
    from basicsr.archs.rrdbnet_arch import RRDBNet
    ESRGAN_AVAILABLE = True
except ImportError:
    ESRGAN_AVAILABLE = False
    print("⚠️  Real-ESRGAN not installed. Run: pip install realesrgan basicsr")


app = FastAPI(title="Aegis-Vision Competition API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
class Config:
    FACE_DATABASE_DIR = Path("./face_database")
    MODELS_DIR = Path("./models")
    VIDEO_UPLOADS_DIR = Path("./video_uploads")
    CONFIDENCE_THRESHOLD = 0.4  # Lowered for easier matching (was 0.6)
    FACE_DETECTION_CONFIDENCE = 0.5
    MAX_DETECTIONS_BUFFER = 500
    SUPPORTED_VIDEO_FORMATS = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv']
    
Config.FACE_DATABASE_DIR.mkdir(exist_ok=True)
Config.MODELS_DIR.mkdir(exist_ok=True)
Config.VIDEO_UPLOADS_DIR.mkdir(exist_ok=True)


# Global state with thread-safe operations
class SurveillanceState:
    def __init__(self):
        self.detections: deque = deque(maxlen=Config.MAX_DETECTIONS_BUFFER)
        self.enhancement_enabled = True
        self.active_connections: List[WebSocket] = []
        self.face_embeddings_db = {}  # {person_id: {"name": str, "embedding": np.array, "metadata": dict}}
        self.lock = threading.Lock()
        self.frame_count = 0
        self.fps = 0
        self.last_fps_time = time.time()
        
        # Video source management
        self.video_source_type = "webcam"  # webcam, file, rtsp
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
            "start_time": None,
            "end_time": None
        }
        
surveillance_state = SurveillanceState()


class AIModels:
    """Singleton for AI model management"""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        print("🔷 Loading AI Models...")
        
        # 1. YOLOv11 Face Detection
        if YOLO_AVAILABLE:
            try:
                # Download YOLOv11 face model if not exists
                model_path = Config.MODELS_DIR / "yolo11n-face.pt"
                if not model_path.exists():
                    print("📥 Downloading YOLOv11 face detection model...")
                    # Use pre-trained YOLO model (can be fine-tuned for faces)
                    self.yolo_model = YOLO('yolo11n.pt')  # Start with base model
                else:
                    self.yolo_model = YOLO(str(model_path))
                print("✅ YOLOv11 loaded")
            except Exception as e:
                print(f"⚠️  YOLOv11 failed: {e}")
                self.yolo_model = None
        else:
            self.yolo_model = None
            
        # 2. Haar Cascade Fallback
        self.haar_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        
        # 3. Super-Resolution Model
        if ESRGAN_AVAILABLE:
            try:
                model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
                self.upsampler = RealESRGANer(
                    scale=4,
                    model_path='https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth',
                    model=model,
                    tile=0,
                    tile_pad=10,
                    pre_pad=0,
                    half=False
                )
                print("✅ Real-ESRGAN super-resolution loaded")
            except Exception as e:
                print(f"⚠️  Real-ESRGAN failed: {e}")
                self.upsampler = None
        else:
            self.upsampler = None
        
        # 4. Face Recognition Backend (DeepFace supports multiple: VGG-Face, Facenet, ArcFace, etc.)
        self.face_recognition_model = 'Facenet512'  # Best for production
        if DEEPFACE_AVAILABLE:
            try:
                # Warmup DeepFace
                print("🔥 Warming up DeepFace...")
                DeepFace.represent(np.zeros((224, 224, 3), dtype=np.uint8), 
                                 model_name=self.face_recognition_model, 
                                 enforce_detection=False)
                print(f"✅ DeepFace ({self.face_recognition_model}) ready")
            except Exception as e:
                print(f"⚠️  DeepFace warmup failed: {e}")
        
        self._initialized = True
        print("🚀 All AI models initialized\n")


# Initialize models globally
ai_models = AIModels()


class VideoProcessor:
    """Production-grade video processor with full AI pipeline"""
    
    def __init__(self, source=0, camera_id="CAM-001", location="Unknown", source_type="webcam"):
        self.source = source
        self.camera_id = camera_id
        self.location = location
        self.source_type = source_type  # webcam, file, rtsp
        self.cap = None
        self.running = False
        self.frame_skip_counter = 0
        self.face_recognition_interval = 5  # Process face recognition every 5 frames
        self.total_frames = 0
        self.current_frame_number = 0
        
    def start(self):
        """Initialize video capture with optimizations"""
        print(f"\n📹 Starting video source: {self.source_type}")
        print(f"   Source: {self.source}")
        
        # Use DirectShow backend for Windows webcams (much faster)
        if isinstance(self.source, int):
            self.cap = cv2.VideoCapture(self.source, cv2.CAP_DSHOW)
        else:
            self.cap = cv2.VideoCapture(self.source)
        
        if not self.cap.isOpened():
            print(f"❌ Failed to open video source: {self.source}")
            return False
        
        # Set resolution to 1280x720 for webcams (HD quality)
        # For IP cameras/files, resolution is auto-detected
        if isinstance(self.source, int):  # Webcam
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            self.cap.set(cv2.CAP_PROP_FPS, 30)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimize buffering for low latency
        
        # Get total frames for video files
        if self.source_type == "file":
            self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = self.cap.get(cv2.CAP_PROP_FPS)
            duration = self.total_frames / fps if fps > 0 else 0
            print(f"   📊 Video info: {self.total_frames} frames, {fps:.2f} FPS, {duration:.2f}s duration")
            surveillance_state.video_total_frames = self.total_frames
        
        self.running = True
        print(f"✅ Video source started successfully")
        
        # Reset session stats
        with surveillance_state.lock:
            surveillance_state.current_session_stats = {
                "total_faces": 0,
                "unique_individuals": set(),
                "high_risk_count": 0,
                "medium_risk_count": 0,
                "low_risk_count": 0,
                "unknown_count": 0,
                "start_time": datetime.now().isoformat(),
                "end_time": None
            }
            surveillance_state.video_processing_complete = False
            surveillance_state.video_current_frame = 0
        
        return True
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduce latency
        self.running = True
        print(f"📹 Video source started: {self.source}")
        
    def stop(self):
        self.running = False
        if self.cap:
            self.cap.release()
    
    # ============= ENHANCEMENT PIPELINE =============
    
    def enhance_low_light(self, frame):
        """
        Production low-light enhancement:
        - CLAHE for adaptive contrast
        - Gamma correction
        - Noise reduction
        """
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        
        # CLAHE with optimized parameters
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        l = clahe.apply(l)
        
        enhanced = cv2.merge([l, a, b])
        enhanced = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)
        
        # Gamma correction for very dark scenes
        gamma = 1.2
        inv_gamma = 1.0 / gamma
        table = np.array([((i / 255.0) ** inv_gamma) * 255 for i in range(256)]).astype("uint8")
        enhanced = cv2.LUT(enhanced, table)
        
        # Bilateral filter for noise reduction while preserving edges
        enhanced = cv2.bilateralFilter(enhanced, 5, 50, 50)
        
        return enhanced
    
    def correct_motion_blur(self, frame):
        """
        Motion blur correction using Wiener deconvolution approximation
        For production, use deep learning models like DeblurGAN-v2
        """
        # Estimate motion kernel (simplified)
        kernel_size = 15
        kernel = np.zeros((kernel_size, kernel_size))
        kernel[int((kernel_size - 1) / 2), :] = np.ones(kernel_size)
        kernel = kernel / kernel_size
        
        # Wiener deconvolution (simplified - use proper implementation in production)
        deblurred = cv2.filter2D(frame, -1, kernel)
        
        # Sharpen
        sharpening_kernel = np.array([[-1, -1, -1],
                                     [-1,  9, -1],
                                     [-1, -1, -1]])
        deblurred = cv2.filter2D(deblurred, -1, sharpening_kernel)
        
        return cv2.addWeighted(frame, 0.5, deblurred, 0.5, 0)
    
    def super_resolve_face(self, face_img):
        """
        Super-resolution for low-resolution faces
        Uses Real-ESRGAN if available, otherwise bicubic upscaling
        """
        if ai_models.upsampler is not None and face_img.shape[0] < 128:
            try:
                output, _ = ai_models.upsampler.enhance(face_img, outscale=4)
                return output
            except Exception as e:
                print(f"ESRGAN error: {e}")
        
        # Fallback: Bicubic + sharpening
        if face_img.shape[0] < 128:
            scale = 128 / face_img.shape[0]
            upscaled = cv2.resize(face_img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            
            # Unsharp masking
            gaussian = cv2.GaussianBlur(upscaled, (0, 0), 2.0)
            upscaled = cv2.addWeighted(upscaled, 1.5, gaussian, -0.5, 0)
            
            return upscaled
        
        return face_img
    
    # ============= DETECTION PIPELINE =============
    
    def detect_faces_yolo(self, frame):
        """YOLOv11-based face detection"""
        if ai_models.yolo_model is None:
            return []
        
        try:
            results = ai_models.yolo_model(frame, conf=Config.FACE_DETECTION_CONFIDENCE, verbose=False)
            faces = []
            
            for result in results:
                boxes = result.boxes
                for box in boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    conf = float(box.conf[0])
                    faces.append((x1, y1, x2 - x1, y2 - y1, conf))
            
            return faces
        except Exception as e:
            print(f"YOLO detection error: {e}")
            return []
    
    def detect_faces_haar(self, frame):
        """Haar Cascade fallback"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = ai_models.haar_cascade.detectMultiScale(
            gray, scaleFactor=1.05, minNeighbors=5, minSize=(40, 40)
        )
        return [(x, y, w, h, 0.8) for x, y, w, h in faces]
    
    def detect_faces(self, frame):
        """Unified face detection with fallback"""
        faces = self.detect_faces_yolo(frame)
        
        if not faces:
            faces = self.detect_faces_haar(frame)
        
        return faces
    
    # ============= RECOGNITION PIPELINE =============
    
    def extract_face_embedding(self, face_img):
        """
        Extract 512-dim face embedding using DeepFace
        Returns None if face not detected or error
        """
        if not DEEPFACE_AVAILABLE:
            print("⚠️  DeepFace not available")
            return None
        
        try:
            # CRITICAL: Convert BGR to RGB (DeepFace requirement for numpy arrays)
            face_rgb = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
            
            # Debug: Check pixel ranges
            print(f"🔍 Pixel range: {face_rgb.min()} - {face_rgb.max()} (should be 0-255)")
            
            # Ensure minimum size
            if face_rgb.shape[0] < 80 or face_rgb.shape[1] < 80:
                face_rgb = cv2.resize(face_rgb, (112, 112))
            
            print(f"🔍 Extracting embedding from RGB face image {face_rgb.shape}...")
            start_time = time.time()
            
            # Save for visual debugging
            debug_id = int(time.time() * 1000)
            debug_path = Config.FACE_DATABASE_DIR / f"debug_face_{debug_id}.jpg"
            cv2.imwrite(str(debug_path), cv2.cvtColor(face_rgb, cv2.COLOR_RGB2BGR))  # Save as BGR for viewing
            print(f"💾 Debug face saved: {debug_path}")
            
            embedding = DeepFace.represent(
                face_rgb,  # Use RGB version
                model_name=ai_models.face_recognition_model,
                enforce_detection=False,
                detector_backend='skip'  # We already detected the face
            )
            
            elapsed = time.time() - start_time
            print(f"⏱️  Embedding extraction took {elapsed:.2f}s")
            
            if embedding and len(embedding) > 0:
                emb_array = np.array(embedding[0]['embedding'])
                print(f"✅ Extracted embedding with shape {emb_array.shape}")
                return emb_array
            else:
                print("⚠️  DeepFace returned empty embedding")
            
        except Exception as e:
            print(f"❌ Embedding extraction error: {e}")
        
        return None
    
    def match_face(self, embedding):
        """
        Match face embedding against database
        Returns (person_id, confidence, metadata) or (None, 0, {})
        """
        if embedding is None:
            print("⚠️  Cannot match - embedding is None")
            return None, 0.0, {}
        
        if not surveillance_state.face_embeddings_db:
            print("⚠️  Watchlist database is EMPTY! No one to match against!")
            print(f"   Add people via the 'Add to Watchlist' button in UI")
            return None, 0.0, {}
        
        print(f"📊 Matching against {len(surveillance_state.face_embeddings_db)} person(s) in database:")
        
        best_match = None
        best_distance = float('inf')
        
        with surveillance_state.lock:
            for person_id, data in surveillance_state.face_embeddings_db.items():
                db_embedding = data['embedding']
                person_name = data['metadata'].get('name', 'Unknown')
                
                # Use Cosine Similarity (more robust than L2 for face recognition)
                dot_product = np.dot(embedding, db_embedding)
                norm_a = np.linalg.norm(embedding)
                norm_b = np.linalg.norm(db_embedding)
                cosine_similarity = dot_product / (norm_a * norm_b)
                distance = 1 - cosine_similarity  # 0 = perfect match, 1 = totally different
                
                print(f"   - {person_name} ({person_id}): cosine_distance = {distance:.3f}, similarity = {cosine_similarity:.3f}")
                
                if distance < best_distance:
                    best_distance = distance
                    best_match = person_id
        
        # Convert distance to confidence (lower distance = higher confidence)
        # For cosine: distance < 0.4 is typically same person
        confidence = max(0, 1 - (best_distance / 0.8))
        
        # Debug logging
        print(f"🔍 Match: cosine_distance={best_distance:.3f}, confidence={confidence:.2%}, threshold={Config.CONFIDENCE_THRESHOLD}")
        
        if confidence > Config.CONFIDENCE_THRESHOLD:
            metadata = surveillance_state.face_embeddings_db[best_match]['metadata']
            name = metadata.get('name', 'Unknown')
            print(f"✅ MATCHED: {name} (confidence: {confidence:.2%})")
            return best_match, confidence, metadata
        
        print(f"❌ No match - confidence too low ({confidence:.2%} < {Config.CONFIDENCE_THRESHOLD})")
        print(f"💡 TIP: For same person, cosine distance should be < 0.4. Your distance is {best_distance:.2f}")
        print(f"   This suggests: Different person OR poor image quality OR different angle/lighting")
        return None, confidence, {}
    
    # ============= MAIN PROCESSING =============
    
    def process_frame(self, frame):
        """Complete processing pipeline"""
        processed = frame.copy()
        
        # Step 1: Enhancement
        if surveillance_state.enhancement_enabled:
            processed = self.enhance_low_light(processed)
            processed = self.correct_motion_blur(processed)
        
        # Step 2: Face Detection
        faces = self.detect_faces(processed)
        
        if faces:
            print(f"\n👤 Detected {len(faces)} face(s) in frame")
        
        detections = []
        timestamp = datetime.now()
        
        # Frame skipping for performance - only do face recognition every N frames
        self.frame_skip_counter += 1
        skip_face_recognition = self.frame_skip_counter % self.face_recognition_interval != 0
        
        if skip_face_recognition and faces:
            print(f"⏭️  Skipping face recognition (frame {self.frame_skip_counter})")
        
        for idx, (x, y, w, h, det_conf) in enumerate(faces):
            # Extract and enhance face
            face_crop = processed[y:y+h, x:x+w]
            
            if face_crop.size == 0:
                continue
            
            # Super-resolve if small
            if w < 128 or h < 128:
                face_crop = self.super_resolve_face(face_crop)
            
            # Face recognition (expensive - skip most frames)
            embedding = None
            person_id = None
            match_conf = 0.0
            metadata = {}
            
            if not skip_face_recognition:
                print(f"🔬 Processing face {idx+1}/{len(faces)} for recognition...")
                embedding = self.extract_face_embedding(face_crop)
                person_id, match_conf, metadata = self.match_face(embedding)
            else:
                print(f"📸 Face {idx+1} detected but skipping recognition for performance")
            
            # Determine identity
            if person_id:
                name = surveillance_state.face_embeddings_db[person_id]['metadata'].get('name', 'Unknown')
                risk_level = surveillance_state.face_embeddings_db[person_id]['metadata'].get('risk_level', 'UNKNOWN')
                display_conf = match_conf
                print(f"✅ Identified: {name} with {match_conf:.0%} confidence (Risk: {risk_level})")
            else:
                name = "Unknown"
                risk_level = "UNKNOWN"
                person_id = f"unknown_{int(time.time()*1000)}_{idx}"
                # Use detection confidence when no face match
                display_conf = det_conf if skip_face_recognition else match_conf
                if not skip_face_recognition:
                    print(f"❓ Unknown person (match confidence: {match_conf:.0%}, detection: {det_conf:.0%})")
            
            # Draw visualization
            color = self._get_risk_color(risk_level)
            cv2.rectangle(processed, (x, y), (x+w, y+h), color, 2)
            
            label = f"{name} ({display_conf:.0%})"
            (label_w, label_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(processed, (x, y - label_h - 10), (x + label_w, y), color, -1)
            cv2.putText(processed, label, (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
            # Encode face crop
            _, buffer = cv2.imencode('.jpg', face_crop)
            face_b64 = base64.b64encode(buffer).decode('utf-8')
            
            # Create detection record
            detection = {
                "id": f"{self.camera_id}_{int(timestamp.timestamp()*1000)}_{idx}",
                "timestamp": timestamp.isoformat(),
                "camera_id": self.camera_id,
                "location": self.location,
                "person_id": person_id,
                "name": name,
                "confidence": float(display_conf),  # Use display_conf which handles both cases
                "detection_confidence": float(det_conf),
                "risk_level": risk_level,
                "bbox": {"x": int(x), "y": int(y), "w": int(w), "h": int(h)},
                "face_crop": face_b64,
                "metadata": metadata,
                "vehicle_speed": None  # Can be integrated with speed sensors
            }
            
            detections.append(detection)
        
        # Update session statistics
        with surveillance_state.lock:
            surveillance_state.current_session_stats['total_faces'] += len(faces)
            for det in detections:
                if det['person_id'] and not det['person_id'].startswith('unknown_'):
                    surveillance_state.current_session_stats['unique_individuals'].add(det['person_id'])
                
                risk = det['risk_level']
                if risk == 'HIGH':
                    surveillance_state.current_session_stats['high_risk_count'] += 1
                elif risk == 'MEDIUM':
                    surveillance_state.current_session_stats['medium_risk_count'] += 1
                elif risk == 'LOW':
                    surveillance_state.current_session_stats['low_risk_count'] += 1
                else:
                    surveillance_state.current_session_stats['unknown_count'] += 1
            
            # Update video progress for file sources
            if self.source_type == "file":
                self.current_frame_number += 1
                surveillance_state.video_current_frame = self.current_frame_number
                
                # Check if video is complete
                if self.total_frames > 0 and self.current_frame_number >= self.total_frames:
                    surveillance_state.video_processing_complete = True
                    surveillance_state.current_session_stats['end_time'] = datetime.now().isoformat()
                    print(f"\n🎬 Video processing complete!")
                    print(f"   Total frames: {self.total_frames}")
                    print(f"   Total faces detected: {surveillance_state.current_session_stats['total_faces']}")
                    print(f"   Unique individuals: {len(surveillance_state.current_session_stats['unique_individuals'])}")
        
        # Add HUD overlay
        processed = self.add_hud_overlay(processed, len(faces), timestamp)
        
        return processed, detections
    
    def _get_risk_color(self, risk_level):
        """BGR color for risk levels"""
        colors = {
            "HIGH": (0, 0, 255),      # Red
            "MEDIUM": (0, 165, 255),  # Orange
            "LOW": (0, 255, 0),       # Green
            "UNKNOWN": (128, 128, 128) # Gray
        }
        return colors.get(risk_level, (255, 255, 255))
    
    def add_hud_overlay(self, frame, face_count, timestamp):
        """Mission Control HUD"""
        overlay = frame.copy()
        h, w = frame.shape[:2]
        color = (59, 130, 246)
        
        # Corner brackets
        bracket_len = 40
        thickness = 2
        
        # Top-left
        cv2.line(overlay, (20, 20), (20+bracket_len, 20), color, thickness)
        cv2.line(overlay, (20, 20), (20, 20+bracket_len), color, thickness)
        
        # Top-right
        cv2.line(overlay, (w-20, 20), (w-20-bracket_len, 20), color, thickness)
        cv2.line(overlay, (w-20, 20), (w-20, 20+bracket_len), color, thickness)
        
        # Bottom-left
        cv2.line(overlay, (20, h-20), (20+bracket_len, h-20), color, thickness)
        cv2.line(overlay, (20, h-20), (20, h-20-bracket_len), color, thickness)
        
        # Bottom-right
        cv2.line(overlay, (w-20, h-20), (w-20-bracket_len, h-20), color, thickness)
        cv2.line(overlay, (w-20, h-20), (w-20, h-20-bracket_len), color, thickness)
        
        # Status info
        time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        cv2.putText(overlay, f"AEGIS-VISION | {time_str}", (30, 50),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        
        cv2.putText(overlay, f"{self.camera_id} | {self.location}", (30, 80),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        
        cv2.putText(overlay, f"TARGETS: {face_count} | FPS: {surveillance_state.fps:.1f}", 
                   (30, h-30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        
        # Scanning line
        scan_y = int((time.time() % 2) * h / 2)
        cv2.line(overlay, (0, scan_y), (w, scan_y), color, 1)
        
        return cv2.addWeighted(overlay, 0.85, frame, 0.15, 0)


# Global processor
video_processor = VideoProcessor(source=0, camera_id="CAM-001", location="Main Entrance")


async def generate_frames():
    """Stream generator with FPS tracking"""
    # Start video processor only if not already running
    if not video_processor.running:
        if not video_processor.start():
            print("❌ Failed to start video processor")
            return
    
    frame_times = deque(maxlen=30)
    
    while video_processor.running:
        start_time = time.time()
        
        success, frame = video_processor.cap.read()
        if not success:
            print("⚠️ Failed to read frame from camera")
            await asyncio.sleep(0.1)
            continue
        
        # Process frame
        processed_frame, detections = video_processor.process_frame(frame)
        
        # Store detections
        with surveillance_state.lock:
            for det in detections:
                surveillance_state.detections.append(det)
        
        # Broadcast
        if detections:
            asyncio.create_task(broadcast_detections(detections))
        
        # FPS calculation
        frame_times.append(time.time() - start_time)
        if len(frame_times) > 0:
            surveillance_state.fps = 1.0 / (sum(frame_times) / len(frame_times))
        
        # Encode
        _, buffer = cv2.imencode('.jpg', processed_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        frame_bytes = buffer.tobytes()
        
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
        await asyncio.sleep(0.001)


async def broadcast_detections(detections):
    """Broadcast to WebSocket clients"""
    if surveillance_state.active_connections:
        message = json.dumps({"type": "detection", "data": detections})
        
        # Check for high-risk alerts
        high_risk = [d for d in detections if d.get('risk_level') == 'HIGH']
        if high_risk:
            alert_message = json.dumps({
                "type": "alert",
                "severity": "high",
                "data": high_risk
            })
            await broadcast_message(alert_message)
        
        disconnected = []
        for conn in surveillance_state.active_connections:
            try:
                await conn.send_text(message)
            except:
                disconnected.append(conn)
        
        for conn in disconnected:
            surveillance_state.active_connections.remove(conn)


async def broadcast_message(message):
    """Send message to all connected WebSocket clients"""
    disconnected = []
    for conn in surveillance_state.active_connections:
        try:
            await conn.send_text(message)
        except:
            disconnected.append(conn)
    
    for conn in disconnected:
        surveillance_state.active_connections.remove(conn)


# ============= API ENDPOINTS =============

@app.get("/api/stream")
async def video_stream():
    return StreamingResponse(generate_frames(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.websocket("/api/logs")
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


@app.post("/api/watchlist/add")
async def add_to_watchlist(file: UploadFile = File(...), 
                          name: str = Form("Unknown"), 
                          risk_level: str = Form("LOW"),
                          notes: str = Form("")):
    """
    Add person to watchlist database
    Accepts image file and extracts face embedding
    Saves both image and embedding to disk for persistence
    """
    print(f"\n📥 Watchlist upload received:")
    print(f"   - File: {file.filename}")
    print(f"   - Name: {name}")
    print(f"   - Risk Level: {risk_level}")
    print(f"   - Notes: {notes}")
    try:
        # Read image
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        print(f"   - Original image shape: {img.shape}")
        
        # ===== CRITICAL: APPLY SAME PREPROCESSING AS LIVE FEED =====
        # This ensures embeddings are comparable!
        
        # 1. Apply same enhancement (if enabled in live feed)
        if surveillance_state.enhancement_enabled:
            img = video_processor.enhance_low_light(img)
            img = video_processor.correct_motion_blur(img)
            print(f"   - Applied enhancement pipeline")
        
        # 2. Detect face in uploaded image (CRITICAL!)
        faces = video_processor.detect_faces(img)
        
        if not faces or len(faces) == 0:
            return {"success": False, "error": "No face detected in uploaded image. Please upload a clear frontal face photo."}
        
        # 3. Use the largest face (assuming main person)
        faces_sorted = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
        x, y, w, h, conf = faces_sorted[0]
        
        print(f"   - Detected face at ({x}, {y}, {w}, {h}) with confidence {conf:.0%}")
        
        # 4. Crop face (SAME as live feed processing)
        face_crop = img[y:y+h, x:x+w]
        
        if face_crop.size == 0:
            return {"success": False, "error": "Failed to crop face from image"}
        
        # 5. Apply super-resolution if needed (SAME as live feed)
        if w < 128 or h < 128:
            face_crop = video_processor.super_resolve_face(face_crop)
            print(f"   - Applied super-resolution")
        
        print(f"   - Final face crop shape: {face_crop.shape}")
        
        # 6. Extract embedding from preprocessed face crop
        embedding = video_processor.extract_face_embedding(face_crop)
        
        if embedding is None:
            return {"success": False, "error": "Failed to extract face embedding. Please try a different photo."}
        
        print(f"   - Embedding vector (first 10 values): {embedding[:10]}")
        print(f"   - Embedding L2 norm: {np.linalg.norm(embedding):.3f}")
        
        # Generate person ID
        person_id = f"person_{int(time.time()*1000)}"
        
        # Save to disk for persistence
        person_dir = Config.FACE_DATABASE_DIR / person_id
        person_dir.mkdir(exist_ok=True)
        
        # Save the PREPROCESSED face crop (not original image!)
        # This ensures consistency when loading from disk
        image_path = person_dir / "face.jpg"
        cv2.imwrite(str(image_path), face_crop)
        
        # Also save original for reference
        original_path = person_dir / "original.jpg"
        cv2.imwrite(str(original_path), img)
        
        # Save embedding as numpy file
        embedding_path = person_dir / "embedding.npy"
        np.save(str(embedding_path), embedding)
        
        # Save metadata as JSON
        metadata = {
            "name": name,
            "risk_level": risk_level,
            "notes": notes,
            "added_at": datetime.now().isoformat()
        }
        metadata_path = person_dir / "metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # Store in memory database
        with surveillance_state.lock:
            surveillance_state.face_embeddings_db[person_id] = {
                "embedding": embedding,
                "metadata": metadata
            }
        
        print(f"✅ Added to watchlist: {name} (ID: {person_id}, Risk: {risk_level})")
        print(f"💾 Saved to: {person_dir}")
        print(f"📊 Total in database: {len(surveillance_state.face_embeddings_db)}")
        
        return {
            "success": True,
            "person_id": person_id,
            "name": name,
            "database_size": len(surveillance_state.face_embeddings_db)
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/watchlist")
async def get_watchlist():
    """Get all watchlist entries"""
    with surveillance_state.lock:
        watchlist = []
        for person_id, data in surveillance_state.face_embeddings_db.items():
            watchlist.append({
                "person_id": person_id,
                **data['metadata']
            })
    return {"watchlist": watchlist, "total": len(watchlist)}


@app.delete("/api/watchlist/{person_id}")
async def remove_from_watchlist(person_id: str):
    """Remove person from watchlist"""
    with surveillance_state.lock:
        if person_id in surveillance_state.face_embeddings_db:
            del surveillance_state.face_embeddings_db[person_id]
            return {"success": True, "message": f"Removed {person_id}"}
    return {"success": False, "error": "Person not found"}


@app.post("/api/toggle-enhancement")
async def toggle_enhancement():
    surveillance_state.enhancement_enabled = not surveillance_state.enhancement_enabled
    return {"enabled": surveillance_state.enhancement_enabled}


@app.get("/api/detections")
async def get_detections(limit: int = 50):
    with surveillance_state.lock:
        recent = list(surveillance_state.detections)[-limit:]
    return {"detections": recent, "total": len(surveillance_state.detections)}


@app.get("/api/export-log")
async def export_log():
    with surveillance_state.lock:
        return {
            "export_time": datetime.now().isoformat(),
            "camera_id": video_processor.camera_id,
            "location": video_processor.location,
            "total_detections": len(surveillance_state.detections),
            "detections": list(surveillance_state.detections)
        }


# ============= VIDEO SOURCE MANAGEMENT =============

@app.post("/api/video/upload")
async def upload_video(file: UploadFile = File(...)):
    """
    Upload video file for processing
    Supports: MP4, AVI, MOV, MKV, FLV, WMV
    """
    print(f"\n📹 Video upload received: {file.filename}")
    
    # Validate file format
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in Config.SUPPORTED_VIDEO_FORMATS:
        return {
            "success": False,
            "error": f"Unsupported format. Supported: {', '.join(Config.SUPPORTED_VIDEO_FORMATS)}"
        }
    
    try:
        # Save uploaded file
        timestamp = int(time.time() * 1000)
        filename = f"video_{timestamp}{file_ext}"
        file_path = Config.VIDEO_UPLOADS_DIR / filename
        
        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)
        
        print(f"✅ Video saved: {file_path}")
        print(f"   Size: {len(contents) / (1024*1024):.2f} MB")
        
        return {
            "success": True,
            "filename": filename,
            "filepath": str(file_path),
            "size_mb": len(contents) / (1024*1024)
        }
    except Exception as e:
        print(f"❌ Video upload error: {e}")
        return {"success": False, "error": str(e)}


@app.post("/api/video/set-source")
async def set_video_source(
    source_type: str = Form(...),  # webcam, file, rtsp
    source_path: str = Form(None),  # file path or RTSP URL
    camera_id: str = Form("CAM-001"),
    location: str = Form("Unknown")
):
    """
    Switch video source
    - webcam: Use laptop camera (source_path not needed)
    - file: Process uploaded video file (source_path = filename)
    - rtsp: Connect to IP camera/stream (source_path = rtsp://...)
    """
    global video_processor
    
    print(f"\n🔄 Switching video source:")
    print(f"   Type: {source_type}")
    print(f"   Path: {source_path}")
    print(f"   Camera ID: {camera_id}")
    print(f"   Location: {location}")
    
    try:
        # Stop current processor
        if video_processor and video_processor.running:
            video_processor.stop()
            print("   ✅ Stopped previous video source")
        
        # Determine source
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
        
        # Create new processor
        video_processor = VideoProcessor(
            source=source,
            camera_id=camera_id,
            location=location,
            source_type=source_type
        )
        
        # Update global state
        with surveillance_state.lock:
            surveillance_state.video_source_type = source_type
            surveillance_state.video_source_path = source_path
            surveillance_state.detections.clear()  # Clear previous detections
        
        success = video_processor.start()
        
        if not success:
            return {"success": False, "error": "Failed to start video source"}
        
        print("   ✅ Video source switched successfully")
        
        return {
            "success": True,
            "source_type": source_type,
            "source_path": source_path,
            "camera_id": camera_id,
            "location": location,
            "total_frames": video_processor.total_frames if source_type == "file" else None
        }
        
    except Exception as e:
        print(f"❌ Error switching video source: {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/video/progress")
async def get_video_progress():
    """
    Get current video processing progress
    For video files, returns frame count and completion percentage
    """
    with surveillance_state.lock:
        return {
            "source_type": surveillance_state.video_source_type,
            "current_frame": surveillance_state.video_current_frame,
            "total_frames": surveillance_state.video_total_frames,
            "progress_percentage": (
                (surveillance_state.video_current_frame / surveillance_state.video_total_frames * 100)
                if surveillance_state.video_total_frames > 0 else 0
            ),
            "processing_complete": surveillance_state.video_processing_complete
        }


@app.get("/api/video/session-stats")
async def get_session_stats():
    """
    Get current session statistics
    Shows aggregated stats for the current video source
    """
    with surveillance_state.lock:
        stats = surveillance_state.current_session_stats.copy()
        stats['unique_individuals'] = len(stats['unique_individuals'])
        return stats


@app.get("/api/stats")
async def get_stats():
    with surveillance_state.lock:
        detections = list(surveillance_state.detections)
    
    high_risk = sum(1 for d in detections if d.get('risk_level') == 'HIGH')
    medium_risk = sum(1 for d in detections if d.get('risk_level') == 'MEDIUM')
    known = sum(1 for d in detections if not d.get('person_id', '').startswith('unknown'))
    
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
            "yolo": YOLO_AVAILABLE and ai_models.yolo_model is not None,
            "deepface": DEEPFACE_AVAILABLE,
            "esrgan": ESRGAN_AVAILABLE and ai_models.upsampler is not None
        }
    }


@app.on_event("startup")
async def startup_event():
    print("\n" + "="*60)
    print("🔷 AEGIS-VISION SURVEILLANCE SYSTEM - COMPETITION EDITION")
    print("="*60)
    print(f"✅ Backend ready at http://localhost:8000")
    print(f"✅ Models: YOLO={YOLO_AVAILABLE}, DeepFace={DEEPFACE_AVAILABLE}, ESRGAN={ESRGAN_AVAILABLE}")
    print(f"✅ Face recognition: {ai_models.face_recognition_model}")
    
    # Load watchlist from disk
    load_watchlist_from_disk()
    
    print("="*60 + "\n")


def load_watchlist_from_disk():
    """Load all saved watchlist entries from face_database folder"""
    if not Config.FACE_DATABASE_DIR.exists():
        print("📁 No face database found - starting fresh")
        return
    
    loaded_count = 0
    with surveillance_state.lock:
        for person_dir in Config.FACE_DATABASE_DIR.iterdir():
            if not person_dir.is_dir():
                continue
            
            person_id = person_dir.name
            embedding_path = person_dir / "embedding.npy"
            metadata_path = person_dir / "metadata.json"
            
            # Check if all required files exist
            if not embedding_path.exists() or not metadata_path.exists():
                print(f"⚠️  Skipping {person_id} - missing files")
                continue
            
            try:
                # Load embedding
                embedding = np.load(str(embedding_path))
                
                # Load metadata
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                
                # Add to memory database
                surveillance_state.face_embeddings_db[person_id] = {
                    "embedding": embedding,
                    "metadata": metadata
                }
                
                loaded_count += 1
                print(f"✅ Loaded: {metadata.get('name', 'Unknown')} ({person_id})")
                
            except Exception as e:
                print(f"⚠️  Error loading {person_id}: {e}")
    
    if loaded_count > 0:
        print(f"📊 Loaded {loaded_count} person(s) from watchlist database")
    else:
        print("📁 Watchlist database is empty - add people via /api/watchlist/add")


@app.on_event("shutdown")
async def shutdown_event():
    video_processor.stop()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)