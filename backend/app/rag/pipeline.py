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
    

    def format_gemini_response(self, text: str) -> str:
        """
        Converts raw Gemini output (with * bullets, ---, etc.) 
        into clean, beautiful, mobile-friendly Markdown
        """
        if not text or not isinstance(text, str):
            return text

        lines = text.split('\n')
        result = []
        in_table = False
        table_lines = []

        for line in lines:
            stripped = line.strip()

            # Convert **Heading** to proper bold heading (no bullet conflict)
            if re.match(r'^\s*\*\*.*\*\*\s*$', stripped):
                result.append(f"**{stripped.strip('* ')}**")
                continue

            # Convert * bullets → proper Markdown bullets
            if re.match(r'^\s*[\*\-•]\s', line) or re.match(r'^\s*\d+\.\s', line):
                clean = re.sub(r'^[\s\*\-•]+\s*', '', line).strip()

                # If line contains bold heading inside bullet
                if re.match(r'^\*\*(.+)\*\*$', clean):
                    clean = f"**{clean.strip('* ')}**"
                elif clean.endswith('**'):
                    clean = clean.rstrip('*').strip()

                indent = len(line) - len(line.lstrip())
                result.append(' ' * indent + '• ' + clean)

            # Convert --- or *** or ___ to <hr>
            elif re.match(r'^[-_*]{3,}\s*$', stripped):
                if in_table and table_lines:
                    result.append("\n<div class=\"overflow-x-auto -mx-4 px-4\">\n")
                    result.extend(table_lines)
                    result.append("</div>\n")
                    table_lines = []
                    in_table = False
                result.append("\n---\n")

            # Detect tables (lines with | )
            elif '|' in line and stripped.startswith('|') and stripped.endswith('|'):
                if not in_table:
                    in_table = True
                    table_lines = []
                table_lines.append(line)

            # Convert markdown heading levels (# to ######) to bold headings
            elif re.match(r'^#{1,6}\s+.*', stripped):
                heading_text = re.sub(r'^#{1,6}\s+', '', stripped).strip()
                result.append(f"**{heading_text}**")
                continue

            # Convert lines ending with ':' to bold headings (fallback)
            elif stripped.endswith(':') and len(stripped) < 80:
                heading_text = stripped.rstrip(':').strip()
                result.append(f"**{heading_text}**")
                continue

            # Code blocks (preserve)
            elif line.startswith('```'):
                if in_table and table_lines:
                    result.append("\n<div class=\"overflow-x-auto -mx-4 px-4\">\n")
                    result.extend(table_lines)
                    result.append("</div>\n")
                    table_lines = []
                    in_table = False
                result.append(line)

            else:
                if in_table:
                    table_lines.append(line)
                else:
                    result.append(line)

        # Handle table at end
        if in_table and table_lines:
            result.append("\n<div class=\"overflow-x-auto -mx-4 px-4\">\n")
            result.extend(table_lines)
            result.append("</div>\n")

        final = '\n'.join(result)

        # Final cleanup: remove excessive newlines and fix any stray markdown
        final = re.sub(r'\n{3,}', '\n\n', final)  # Collapse 3+ line breaks
        final = re.sub(r'\*\*(.*?)\*\*', r'**\1**', final)  # Ensure valid bold syntax
        final = re.sub(r'#+\s+', '', final)  # Strip any leftover hashes just in case
        final = re.sub(r'`([^`]+)`', r'<div class="glass-card">\1</div>', final)
        
        return final.strip()

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

            final_answer = self.format_gemini_response(answer)

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
    
