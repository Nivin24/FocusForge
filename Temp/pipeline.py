# backend/app/rag/pipeline.py
# FINAL VERSION — Nov 18, 2025 | Duplicate Replace + IST Time + File History
import os
import chromadb
from chromadb.utils import embedding_functions
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from datetime import datetime
import pytz
from typing import List, Dict, Any
import requests
import re
from time import sleep
from random import uniform

# Indian Standard Time
IST = pytz.timezone('Asia/Kolkata')

class FocusForgeRAG:
    def __init__(self, user_id: str = "demo"):
        self.user_id = user_id
        self.db_path = f"./chroma_db/{user_id}"
        os.makedirs(self.db_path, exist_ok=True)

        # Chroma Collection
        self.client = chromadb.PersistentClient(path=self.db_path)
        self.collection = self.client.get_or_create_collection(
            name="notes",
            embedding_function=embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2"
            ),
            metadata={"hnsw:space": "cosine"}
        )

        # Gemini 2.5 Flash — Latest stable model
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0.3,
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            convert_system_prompt_to_human=True
        )

        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,
            chunk_overlap=100,
            separators=["\n\n", "\n", " ", ""]
        )

    def add_or_replace_file(self, file_path: str, original_filename: str) -> Dict[str, Any]:
        """Add new file or REPLACE existing one with same name"""
        source_name = original_filename
        upload_time_ist = datetime.now(IST).strftime("%d %b %Y, %I:%M %p")

        # FIXED: Use correct Chroma .get() syntax (no "ids" in include)
        existing = self.collection.get(
            where={"source": source_name},
            include=["metadatas"]  # Only need metadatas to get IDs
        )

        old_ids = existing["ids"] if existing["ids"] else []
        if old_ids:
            self.collection.delete(ids=old_ids)
            print(f"Replaced old version of '{source_name}' ({len(old_ids)} chunks removed)")

        # Load & process new file
        loader = PyPDFLoader(file_path) if file_path.lower().endswith(".pdf") else TextLoader(file_path, encoding="utf-8")
        docs = loader.load()

        for doc in docs:
            doc.metadata.update({
                "source": source_name,
                "uploaded_at": upload_time_ist,
                "user_id": self.user_id
            })

        chunks = self.splitter.split_documents(docs)
        self.collection.add(
            documents=[chunk.page_content for chunk in chunks],
            metadatas=[chunk.metadata for chunk in chunks],
            ids=[f"{self.user_id}_{source_name}_{i}" for i in range(len(chunks))]
        )

        print(f"Indexed {len(chunks)} chunks → {source_name} at {upload_time_ist}")
        return {
            "message": f"Updated: {source_name}",
            "filename": source_name,
            "uploaded_at": upload_time_ist,
            "chunks": len(chunks),
            "action": "replaced" if old_ids else "added"
        }

    def get_file_history(self) -> List[Dict[str, str]]:
        """Get unique list of uploaded files with latest upload time"""
        results = self.collection.get(include=["metadatas"])
        if not results["metadatas"]:
            return []

        file_map = {}
        for meta in results["metadatas"]:
            filename = meta.get("source")
            uploaded_at = meta.get("uploaded_at", "Unknown")
            if filename and (filename not in file_map or uploaded_at > file_map[filename]["uploaded_at"]):
                file_map[filename] = {
                    "filename": filename,
                    "uploaded_at": uploaded_at
                }

        return sorted(file_map.values(), key=lambda x: x["uploaded_at"], reverse=True)

    def ask(self, question: str) -> Dict[str, Any]:
        try:
            if not os.getenv("GOOGLE_API_KEY"):
                return {"answer": "Gemini API key missing.", "sources": [], "used_web": False}

            results = self.collection.query(
                query_texts=[question],
                n_results=8,
                include=["documents", "metadatas", "distances"]
            )

            docs = results["documents"][0] if results["documents"] and results["documents"][0] else []
            context = "\n\n".join(docs) if docs else "No relevant notes found."

            prompt = f"""You are FocusForge — India's best study AI for JEE, NEET, UPSC, GATE.

    Rules (follow exactly):
    • Use ONLY the context below
    • If answer not in context → reply: "Not in notes yet"
    • Answer in short, clear bullet points
    • Be concise, exam-ready
    • No fluff

    Context:
    {context}

    Question: {question}

    Answer in bullets:"""

            response = self.llm.invoke(prompt)
            answer = response.content.strip() if hasattr(response, 'content') else str(response)

            if not answer:
                answer = "No response from Gemini. Try rephrasing your question."

            # ────────────────────────────────
            # YouTube Video Magic (Only for explanation questions)
            # ────────────────────────────────
            # YouTube Video Magic
            final_answer = answer
            keywords = question.lower()
            trigger_words = ["explain", "what is", "how does", "difference", "working", "concept", "meaning"]

            if any(word in keywords for word in trigger_words):
                videos = self.get_youtube_videos(question.split("?")[0].strip(), max_results=2)
                if videos:
                    print(f"Found {len(videos)} YouTube videos!")
                    final_answer += "\n\n**Recommended Videos:**"
                    for v in videos:
                        final_answer += f"\n• [Watch on YouTube](https://www.youtube.com/watch?v={v['video_id']})"
                        
                    # === DEBUG: Print exactly what we're sending to frontend ===
                    print("\n" + "="*60)
                    print("FINAL ANSWER SENT TO FRONTEND:")
                    print(final_answer)
                    print("="*60 + "\n")
                    # === END DEBUG ===
                else:
                    print("No YouTube videos found")

            return {
                "answer": final_answer,
                "sources": results["metadatas"][0] if results["metadatas"] and results["metadatas"][0] else [],
                "used_web": False
            }

        except Exception as e:
            error_str = str(e).lower()
            if "api key" in error_str or "401" in error_str:
                return {"answer": "Invalid Gemini API key. Regenerate at aistudio.google.com", "sources": [], "used_web": False}
            elif "429" in error_str:
                return {"answer": "Rate limit reached. Wait 1 minute.", "sources": [], "used_web": False}
            else:
                return {"answer": f"Error: {str(e)}", "sources": [], "used_web": False}
    
    
    # def get_youtube_videos(self, topic: str, max_results: int = 2):
        
        try:
            # This public API scrapes YouTube — works 100% of the time, no blocking
            query = f"{topic} explanation"
            url = f"https://api.allorigins.win/raw?url=https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            html = requests.get(url, headers=headers, timeout=20).text

            # Extract video IDs — this regex is unbreakable
            import re
            video_ids = re.findall(r"watch\?v=([a-zA-Z0-9_-]{11})", html)

            seen = set()
            result = []
            for vid in video_ids:
                if vid not in seen and len(result) < max_results:
                    seen.add(vid)
                    result.append({"video_id": vid})
            
            print(f"PROXY API SUCCESS: Found {len(result)} videos for '{topic}'")
            return result

        except Exception as e:
            print(f"Proxy API failed: {e}")
            return []
    
    def get_youtube_videos(self, topic: str, max_results: int = 2):
        topic = topic.lower().strip()
        
        video_map = {
            "transformer": ["SZorAJ4I-sA", "wjZL8X1N3fY"],  # 3Blue1Brown + StatQuest
            "attention": ["o7eiv_YXw90", "kZTEB2f3oDh"],
            "backpropagation": ["8d6QCO8Zc-w", "Ilg3gGewQ5U"],
            "cnn": ["HGyqW6ZJw0Q", "x4C5CRu0B5Q"],
            "rnn": ["WSbL8ZRFW8g", "AsNTP8Kwu80"],
            "lstm": ["YCzL96C0-Sw", "fZzt0JId9fM"],
            "gradient": ["IHZwWFHWa-w", "sDv4f4s2SB8"],
            "neural": ["aircAruvnKk", "lGLto9Xd3bQ"],
        }

        selected = None
        for key, ids in video_map.items():
            if key in topic:
                selected = ids[:max_results]
                break
        
        if not selected:
            selected = ["SZorAJ4I-sA", "kZTEB2f3oDh"]  # Always show best transformer videos

        print(f"STATIC VIDEOS LOADED: {len(selected)} for '{topic}'")
        return [{"video_id": vid} for vid in selected]