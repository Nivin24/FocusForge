# backend/app/routes.py
import os
import uuid
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from .rag.pipeline import FocusForgeRAG
from app import user_rags

api_bp = Blueprint('api', __name__)
UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@api_bp.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    user_id = request.args.get('user_id') or (request.get_json(silent=True) or {}).get('user_id', 'demo')

    # Initialize user session if not exists
    if user_id not in user_rags:
        user_rags[user_id] = FocusForgeRAG(user_id)

    original_filename = secure_filename(file.filename)
    temp_path = os.path.join(UPLOAD_FOLDER, f"{user_id}_{uuid.uuid4()}_{original_filename}")
    file.save(temp_path)

    try:
        # This now replaces duplicate + returns metadata
        result = user_rags[user_id].add_or_replace_file(temp_path, original_filename)
        os.remove(temp_path)

        return jsonify({
            "message": result["message"],
            "filename": result["filename"],
            "uploaded_at": result["uploaded_at"],
            "chunks": result["chunks"],
            "action": result["action"]  # "added" or "replaced"
        })

    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return jsonify({"error": f"Processing failed: {str(e)}"}), 500


@api_bp.route('/files', methods=['GET'])
def get_uploaded_files():
    """Return list of uploaded files with latest upload time (for sidebar)"""
    user_id = request.args.get('user_id') or (request.get_json(silent=True) or {}).get('user_id', 'demo')

    if user_id not in user_rags:
        user_rags[user_id] = FocusForgeRAG(user_id)

    files = user_rags[user_id].get_file_history()
    return jsonify({"files": files})


@api_bp.route('/ask', methods=['POST'])
def ask_question():
    try:
        data = request.get_json() or {}
        question = data.get('question', '').strip()
        mode = data.get('mode', 'study')                    # ← THIS LINE WAS MISSING!
        user_id = data.get('user_id', 'demo')               # ← BETTER: read from JSON body

        if not question:
            return jsonify({
                "answer": "Please type a question!",
                "sources": [], 
                "used_web": False
            })

        # Initialize user if not exists
        if user_id not in user_rags:
            user_rags[user_id] = FocusForgeRAG(user_id=user_id)
            return jsonify({
                "answer": "No notes uploaded yet. Upload a PDF or text file first!",
                "sources": [],
                "used_web": False
            })

        # ← PASS THE MODE HERE!
        result = user_rags[user_id].ask(question, mode=mode)

        # Hide sources if nothing found
        if "not in notes yet" in result["answer"].lower():
            result["sources"] = []

        return jsonify(result)

    except Exception as e:
        print(f"Ask route error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "answer": "Sorry, something went wrong. Please try again.",
            "sources": [],
            "used_web": False
        }), 500
        
@api_bp.route('/delete_file', methods=['POST'])
def delete_file():
    try:
        data = request.get_json() or {}
        user_id = data.get('user_id', 'demo')
        filename = data.get('filename')

        if not filename:
            return jsonify({"error": "Filename required"}), 400

        # Get or create user session
        if user_id not in user_rags:
            user_rags[user_id] = FocusForgeRAG(user_id=user_id)

        result = user_rags[user_id].collection.get(
            where={"source": filename},
            include=["metadatas"]  # Only need metadatas to get IDs
        )

        ids_to_delete = result.get("ids", [])
        if ids_to_delete:
            user_rags[user_id].collection.delete(ids=ids_to_delete)
            print(f"DELETED: {filename} ({len(ids_to_delete)} chunks) for user {user_id}")
            return jsonify({"success": True, "message": "File deleted"}), 200

        return jsonify({"message": "File not found"}), 404

    except Exception as e:
        print(f"DELETE ERROR: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500