"""Watchlist API: add, list, remove, bulk upload."""

import asyncio
import io
import json
import time
import zipfile
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from fastapi import APIRouter, File, Form, UploadFile

from config import Config
from state import surveillance_state
import processor_instance as proc_inst

router = APIRouter()


def _ensure_processor():
    """Use global video_processor for face ops; it is set at startup."""
    return proc_inst.video_processor


@router.post("/api/watchlist/add")
async def add_to_watchlist(
    file: UploadFile = File(...),
    name: str = Form("Unknown"),
    risk_level: str = Form("LOW"),
    notes: str = Form(""),
):
    proc = _ensure_processor()
    if not proc:
        return {"success": False, "error": "Video processor not initialized"}
    try:
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return {"success": False, "error": "Failed to decode image"}
        if surveillance_state.enhancement_enabled:
            img = proc.enhance_low_light(img)
            img = proc.correct_motion_blur(img)
        faces = proc.detect_faces(img)
        if not faces:
            return {"success": False, "error": "No face detected. Please upload a clear frontal face photo."}
        faces_sorted = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
        x, y, w, h, conf = faces_sorted[0]
        face_crop = img[y : y + h, x : x + w]
        if face_crop.size == 0:
            return {"success": False, "error": "Failed to crop face"}
        if w < 128 or h < 128:
            face_crop = proc.super_resolve_face(face_crop)
        embedding = proc.extract_face_embedding(face_crop)
        if embedding is None:
            return {"success": False, "error": "Failed to extract face embedding. Try a different photo."}
        person_id = f"person_{int(time.time() * 1000)}"
        person_dir = Config.FACE_DATABASE_DIR / person_id
        person_dir.mkdir(exist_ok=True)
        cv2.imwrite(str(person_dir / "face.jpg"), face_crop)
        cv2.imwrite(str(person_dir / "original.jpg"), img)
        np.save(str(person_dir / "embedding.npy"), embedding)
        metadata = {
            "name": name,
            "risk_level": risk_level,
            "notes": notes,
            "added_at": datetime.now().isoformat(),
        }
        with open(person_dir / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)
        with surveillance_state.lock:
            surveillance_state.face_embeddings_db[person_id] = {"embedding": embedding, "metadata": metadata}
        return {
            "success": True,
            "person_id": person_id,
            "name": name,
            "database_size": len(surveillance_state.face_embeddings_db),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/api/watchlist")
async def get_watchlist():
    with surveillance_state.lock:
        watchlist = [
            {"person_id": pid, **data["metadata"]}
            for pid, data in surveillance_state.face_embeddings_db.items()
        ]
    return {"watchlist": watchlist, "total": len(watchlist)}


@router.delete("/api/watchlist/{person_id}")
async def remove_from_watchlist(person_id: str):
    with surveillance_state.lock:
        if person_id in surveillance_state.face_embeddings_db:
            del surveillance_state.face_embeddings_db[person_id]
            return {"success": True, "message": f"Removed {person_id}"}
    return {"success": False, "error": "Person not found"}


@router.post("/api/watchlist/bulk-upload")
async def bulk_upload_watchlist(
    excel_file: UploadFile = File(...),
    images_zip: UploadFile = File(...),
):
    proc = _ensure_processor()
    if not proc:
        return {"success": False, "error": "Video processor not initialized"}
    results = {"success": True, "total": 0, "processed": 0, "failed": 0, "entries": []}
    try:
        excel_content = await excel_file.read()
        try:
            df = pd.read_excel(io.BytesIO(excel_content))
        except Exception:
            try:
                df = pd.read_csv(io.BytesIO(excel_content))
            except Exception as e:
                return {"success": False, "error": f"Failed to parse Excel/CSV: {str(e)}"}
        if "name" not in df.columns or "image_filename" not in df.columns:
            return {"success": False, "error": "Missing columns: name, image_filename"}
        results["total"] = len(df)
        zip_content = await images_zip.read()
        try:
            zf = zipfile.ZipFile(io.BytesIO(zip_content))
            image_files = {
                name: zf.read(name)
                for name in zf.namelist()
                if name.lower().endswith((".jpg", ".jpeg", ".png", ".bmp"))
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to read ZIP: {str(e)}"}
        for idx, row in df.iterrows():
            entry = {
                "index": idx + 1,
                "name": row["name"],
                "image_filename": row["image_filename"],
                "success": False,
                "error": None,
                "person_id": None,
            }
            try:
                name = str(row["name"])
                image_filename = str(row["image_filename"])
                risk_level = str(row.get("risk_level", "LOW")).upper()
                if risk_level not in ("LOW", "MEDIUM", "HIGH"):
                    risk_level = "LOW"
                notes = str(row.get("notes", ""))
                image_data = None
                for zip_name, data in image_files.items():
                    if Path(zip_name).name.lower() == image_filename.lower() or zip_name.lower().endswith(image_filename.lower()):
                        image_data = data
                        break
                if image_data is None:
                    entry["error"] = f"Image not found in ZIP: {image_filename}"
                    results["failed"] += 1
                    results["entries"].append(entry)
                    continue
                nparr = np.frombuffer(image_data, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if img is None:
                    entry["error"] = "Failed to decode image"
                    results["failed"] += 1
                    results["entries"].append(entry)
                    continue
                if surveillance_state.enhancement_enabled:
                    img = proc.enhance_low_light(img)
                faces = proc.detect_faces(img)
                if not faces:
                    entry["error"] = "No face detected"
                    results["failed"] += 1
                    results["entries"].append(entry)
                    continue
                x, y, w, h, _ = max(faces, key=lambda f: f[2] * f[3])
                face_crop = img[y : y + h, x : x + w]
                if face_crop.size == 0:
                    entry["error"] = "Failed to crop face"
                    results["failed"] += 1
                    results["entries"].append(entry)
                    continue
                if w < 128 or h < 128:
                    face_crop = proc.super_resolve_face(face_crop)
                embedding = proc.extract_face_embedding(face_crop)
                if embedding is None:
                    entry["error"] = "Failed to extract embedding"
                    results["failed"] += 1
                    results["entries"].append(entry)
                    continue
                person_id = f"person_{int(time.time() * 1000)}_{idx}"
                person_dir = Config.FACE_DATABASE_DIR / person_id
                person_dir.mkdir(exist_ok=True)
                cv2.imwrite(str(person_dir / "face.jpg"), face_crop)
                cv2.imwrite(str(person_dir / "original.jpg"), img)
                np.save(str(person_dir / "embedding.npy"), embedding)
                metadata = {
                    "name": name,
                    "risk_level": risk_level,
                    "notes": notes,
                    "added_at": datetime.now().isoformat(),
                    "source": "bulk_upload",
                }
                with open(person_dir / "metadata.json", "w") as f:
                    json.dump(metadata, f, indent=2)
                with surveillance_state.lock:
                    surveillance_state.face_embeddings_db[person_id] = {"embedding": embedding, "metadata": metadata}
                entry["success"] = True
                entry["person_id"] = person_id
                results["processed"] += 1
            except Exception as e:
                entry["error"] = str(e)
                results["failed"] += 1
            results["entries"].append(entry)
            await asyncio.sleep(0.01)
        return results
    except Exception as e:
        return {"success": False, "error": str(e)}
