# backend/main.py
from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
import uuid
from werkzeug.utils import secure_filename
from app.rag.pipeline import FocusForgeRAG
from typing import Dict, List
import shutil

# Global user cache (same as before)
user_rags: Dict[str, FocusForgeRAG] = {}

app = FastAPI(title="FocusForge API", version="2.0")

# CORS — FINALLY FIXED FOREVER
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://focusforgeai.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

UPLOAD_FOLDER = "./uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def get_rag(user_id: str) -> FocusForgeRAG:
    if user_id not in user_rags:
        user_rags[user_id] = FocusForgeRAG(user_id)
    return user_rags[user_id]

@app.get("/")
async def home():
    return {"message": "FocusForge API LIVE", "version": "2.0", "active_users": len(user_rags)}

@app.get("/health")
async def health():
    return {"status": "healthy", "users_online": len(user_rags)}

@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    user_id: str = Query("demo")
):
    if not file.filename:
        raise HTTPException(400, detail="No file selected")

    rag = get_rag(user_id)
    filename = secure_filename(file.filename)
    temp_path = os.path.join(UPLOAD_FOLDER, f"{user_id}_{uuid.uuid4()}_{filename}")

    with open(temp_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        result = rag.add_or_replace_file(temp_path, filename)
        os.remove(temp_path)
        return result
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(500, detail=f"Processing failed: {str(e)}")

@app.get("/api/files")
async def get_files(user_id: str = Query("demo")):
    rag = get_rag(user_id)
    files = rag.get_file_history()
    return {"files": files}

@app.post("/api/ask")
async def ask_question(data: Dict):
    user_id = data.get("user_id", "demo")
    question = data.get("question", "").strip()
    mode = data.get("mode", "study")

    if not question:
        return {"answer": "Please type a question!", "sources": [], "used_web": False}

    rag = get_rag(user_id)
    result = rag.ask(question, mode=mode)
    return result

@app.post("/api/delete_file")
async def delete_file(data: Dict):
    user_id = data.get("user_id", "demo")
    filename = data.get("filename")
    if not filename:
        raise HTTPException(400, detail="Filename required")

    rag = get_rag(user_id)
    result = rag.collection.get(where={"source": filename})
    ids = result.get("ids", [])
    
    if ids:
        rag.collection.delete(ids=ids)

    updated_files = rag.get_file_history()
    return {"success": True, "message": "Deleted", "files": updated_files}