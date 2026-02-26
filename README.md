# Aegis-Vision | AI-Powered Surveillance System

> Competition-grade real-time surveillance with face detection, recognition, and enhancement — built for the Pakistan AI Challenge 2026.

## Features

### Core AI Pipeline
- **YOLOv11 Face Detection** with Haar Cascade fallback for reliability
- **FaceNet512 Face Recognition** via DeepFace — real-time watchlist matching with cosine similarity
- **Real-ESRGAN Super-Resolution** — upscales low-res faces (< 128px) up to 4x for motorway/CCTV footage
- **Adaptive Low-Light Enhancement** — Multi-Scale Retinex + CLAHE, auto-adjusts based on scene brightness
- **Motion Deblur** — unsharp masking for moving subjects

### Surveillance Dashboard
- **Live MJPEG Video Stream** — webcam, video file upload, or RTSP/IP camera input
- **Real-Time Detection Feed** — face bounding boxes, identity labels, confidence scores, risk-level color coding
- **HUD Overlay** — camera ID, timestamp, target count, FPS, vehicle speed estimation
- **WebSocket Alerts** — instant high-risk person notifications pushed to the browser

### Watchlist Management
- **Add/Remove Persons** — upload a photo, set name and risk level (LOW / MEDIUM / HIGH)
- **Bulk Upload** — Excel spreadsheet + ZIP of images for batch watchlist import
- **Persistent Storage** — face embeddings and metadata saved to disk, auto-loaded on restart

### Analytics & Export
- **Session Statistics** — total faces detected, unique individuals, risk breakdown
- **Detection Log Export** — download full JSON log of all detections
- **Video Progress Tracking** — frame-by-frame progress for uploaded video files

### Multi-Source Video Input
- **Webcam** — laptop or external USB camera (auto-skips DroidCam virtual camera)
- **Video File** — upload MP4/AVI/MOV/MKV/FLV/WMV for offline analysis
- **RTSP Stream** — connect to IP cameras and NVRs

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 19, TypeScript, Tailwind CSS 4, Framer Motion, Vite 7 |
| **Backend** | FastAPI, Uvicorn, Python 3.10 |
| **Detection** | YOLOv11 (ultralytics), OpenCV Haar Cascade |
| **Recognition** | DeepFace (FaceNet512), NumPy |
| **Enhancement** | Real-ESRGAN, OpenCV CLAHE, Multi-Scale Retinex |
| **Data** | Pandas (bulk upload), NumPy (embeddings), JSON (metadata) |

## Project Structure

```
Aegis-Vision/
├── backend/
│   ├── main.py                 # FastAPI app entrypoint
│   ├── config.py               # Configuration and paths
│   ├── state.py                # Global surveillance state
│   ├── ai_models.py            # YOLO, DeepFace, ESRGAN model loading
│   ├── video_processor.py      # Full AI pipeline (enhance → detect → recognize → HUD)
│   ├── watchlist_disk.py       # Watchlist persistence
│   ├── processor_instance.py   # Global processor reference
│   ├── routes/
│   │   ├── stream.py           # /api/stream, /api/logs (WebSocket)
│   │   ├── watchlist.py        # /api/watchlist CRUD + bulk upload
│   │   ├── video.py            # /api/video upload, source switching, webcam control
│   │   └── misc.py             # /api/stats, /api/detections, /api/export-log
│   ├── requirements.txt        # Full local dependencies
│   └── requirements-cloud.txt  # Lightweight cloud dependencies
├── frontend/
│   ├── src/
│   │   ├── dashboard.tsx       # Main surveillance dashboard
│   │   ├── main.tsx            # React entry point
│   │   └── style.css           # Tailwind styles
│   ├── vite.config.ts          # Vite config with API proxy
│   ├── vercel.json             # Vercel deployment config
│   └── package.json
├── render.yaml                 # Render backend deployment config
├── .gitignore
└── README.md
```

## Local Setup

### Prerequisites
- Python 3.10+
- Node.js 18+
- Webcam (for live demo)

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`, click **Start Camera**, and the live feed with face detection begins.

## Deployment

| Service | Platform | Config |
|---------|----------|--------|
| Backend | [Render](https://render.com) (free) | `render.yaml` — Python, `requirements-cloud.txt` |
| Frontend | [Vercel](https://vercel.com) (free) | `vercel.json` — Vite, env vars for API URL |

### Environment Variables

**Backend (Render):**
| Variable | Value |
|----------|-------|
| `ENVIRONMENT` | `cloud` |
| `ALLOWED_ORIGINS` | `https://your-app.vercel.app` |

**Frontend (Vercel):**
| Variable | Value |
|----------|-------|
| `VITE_API_BASE` | `https://your-api.onrender.com/api` |
| `VITE_WS_URL` | `wss://your-api.onrender.com/api/logs` |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/stream` | MJPEG video stream |
| WS | `/api/logs` | Real-time detection WebSocket |
| GET | `/api/stats` | System statistics |
| GET | `/api/detections` | Recent detections |
| GET | `/api/export-log` | Full detection log export |
| POST | `/api/start-webcam/{index}` | Start webcam by index |
| POST | `/api/stop-stream` | Stop current stream |
| POST | `/api/video/upload` | Upload video file |
| POST | `/api/video/set-source` | Switch video source |
| GET | `/api/video/progress` | Video processing progress |
| GET | `/api/video/session-stats` | Session statistics |
| POST | `/api/watchlist/add` | Add person to watchlist |
| GET | `/api/watchlist` | List watchlist entries |
| DELETE | `/api/watchlist/{id}` | Remove person |
| POST | `/api/watchlist/bulk-upload` | Bulk import (Excel + ZIP) |
| POST | `/api/toggle-enhancement` | Toggle image enhancement |

## Privacy & Security

- Face embeddings and images are stored **locally only** (`face_database/`) — never pushed to git or cloud
- `.gitignore` blocks all sensitive data: `.env`, `face_database/`, model weights, video uploads
- Cloud mode restricts CORS to your frontend domain only
- `/docs` endpoint disabled in production
