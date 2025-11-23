# backend/app/rag/pipeline.py
# FINAL VERSION — Nov 18, 2025 | Duplicate Replace + IST Time + File History
import os
import chromadb
from chromadb.utils import embedding_functions
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
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
        # Use persistent path in production, local fallback in dev
        # self.db_path = os.getenv("CHROMA_DB_PATH", f"./chroma_db/{user_id}")
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
        # self.llm = ChatGoogleGenerativeAI(
        #     model="gemini-2.5-flash",
        #     temperature=0.3,
        #     google_api_key=os.getenv("GOOGLE_API_KEY"),
        #     convert_system_prompt_to_human=True
        # )
        self.llms = [
            ChatGoogleGenerativeAI(
                model="gemini-2.5-flash",
                google_api_key=os.getenv("GOOGLE_API_KEY"),
                temperature=0.3
            ),
            # Groq Mixtral - Fast & Efficient
            # ChatGroq(
            #     model="mixtral-8x7b-32768",
            #     groq_api_key=os.getenv("GROQ_API_KEY"),
            #     temperature=0.3
            # ),
            # OpenRouter - Additional Backup (example: Mistral or GPT-4)
            ChatOpenAI(
                model="mistralai/mistral-7b-instruct",
                temperature=0.3
            )
            # You can add more models here...
        ]

        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,
            chunk_overlap=100,
            separators=["\n\n", "\n", " ", ""]
        )
    def run_llm(self, prompt: str) -> str:
        """Execute prompt using available LLMs with fallback."""
        for idx, llm in enumerate(self.llms):
            # Get the model name safely
            model_name = getattr(llm, "model", getattr(llm, "model_name", "Unknown Model"))

            try:
                print(f"🟢 Trying model {idx + 1}: {model_name}")

                response = llm.invoke(prompt)

                # Handle content safely
                content = getattr(response, "content", None) or getattr(response, "text", None) or str(response)

                if content:
                    print(f"✔ Success with: {model_name}")
                    return content

            except Exception as e:
                print(f"⚠ Model {model_name} failed with error: {e}")

                continue  # Try next model

        return "❌ All models failed. Please try again later."

    def add_or_replace_file(self, file_path: str, original_filename: str) -> Dict[str, Any]:
        """Add new file or REPLACE existing one with same name"""
        source_name = original_filename
        upload_time_ist = datetime.now(IST).strftime("%d %b %Y, %I:%M %p")

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
    

    import re

    def format_gemini_response(self, text: str) -> str:
        """
        UNIVERSAL MARKDOWN FORMATTER (Upgraded)
        - Supports Headings (#, ##, ###)
        - Converts lines ending with ":" into headings (##)
        - Cleans bullets, numbers, spacing
        - Preserves code blocks
        - Converts — and --- to horizontal rules
        - Supports bold (**text**)
        - Mobile-friendly output
        """

        import re

        if not text or not isinstance(text, str):
            return text or ""

        lines = text.splitlines()
        result = []
        in_code_block = False

        for line in lines:
            stripped = line.strip()

            # Handle blank lines
            if not stripped and not in_code_block:
                result.append("")
                continue

            # Preserve code blocks
            if stripped.startswith("```"):
                in_code_block = not in_code_block
                result.append(line)
                continue
            if in_code_block:
                result.append(line)
                continue

            # -------------------------------------------
            # 0. Normalize Horizontal Rules
            # -------------------------------------------
            if re.match(r'^[-]{3,}$', stripped):
                result.append("---")
                continue

            # -------------------------------------------
            # 1. True Markdown Headings (#, ##, ###)
            # -------------------------------------------
            if re.match(r'^\s*#{1,3}\s+', stripped):
                result.append(stripped)
                continue

            # -------------------------------------------
            # 2. Convert lines ending with ":" → H2 heading
            # Example: "Key Components:" → "## Key Components"
            # -------------------------------------------
            if stripped.endswith(":") and len(stripped) < 80:
                heading = stripped[:-1].strip()
                result.append(f"## {heading}")
                continue

            # -------------------------------------------
            # 3. Question Number Headings → **Chemical Bonding**
            # -------------------------------------------
            if re.match(r'^\s*\d+[\.\)]\s', stripped):
                clean = re.sub(r'^[\s\d\.\)]+\s*', '', stripped)
                result.append(f"**{clean}**")
                continue

            # -------------------------------------------
            # 4. Explicit question lines
            # -------------------------------------------
            if any(kw in stripped.lower() for kw in ["question:", "q:", "que."]):
                cleaned = re.sub(r'.*?(question|q)[:\s]+', '', stripped, flags=re.I).strip()
                if cleaned:
                    result.append(f"**{cleaned}**")
                    continue

            # -------------------------------------------
            # 5. MCQ Options (A) B) etc)
            # -------------------------------------------
            if re.match(r'^[ABCD]\)', stripped):
                opt = stripped[0:2]  # A)
                text_part = stripped[2:].strip()
                result.append(f"**{opt}** {text_part}")
                continue

            # -------------------------------------------
            # 6. Numbered lists (1. , 2) )
            # -------------------------------------------
            if re.match(r'^\s*\d+[\.\)]\s', stripped):
                num = re.findall(r'^\s*(\d+[\.\)])', stripped)[0]
                text_part = stripped.split(num, 1)[1].strip()
                result.append(f"- {text_part}")
                continue

            # -------------------------------------------
            # 7. Bullet points
            # -------------------------------------------
            if re.match(r'^\s*[-*•]\s+', stripped):
                clean = re.sub(r'^\s*[-*•]+\s+', '', stripped)
                result.append(f"- {clean}")
                continue

            # -------------------------------------------
            # 8. Standalone bold lines
            # -------------------------------------------
            if stripped.startswith("**") and stripped.endswith("**"):
                result.append(stripped)
                continue

            # -------------------------------------------
            # 9. Apply inline bold cleanup
            # -------------------------------------------
            clean = re.sub(r'\*\*(.*?)\*\*', r'**\1**', stripped)

            # Default clean line
            result.append(clean)

        # -------------------------------------------
        # POST-PROCESS CLEANUP
        # -------------------------------------------

        final = "\n".join(result)

        # Remove triple newlines → max 2
        final = re.sub(r'\n{3,}', '\n\n', final)

        # Auto space before headings
        final = re.sub(r'([^\n])(\n##)', r'\1\n\n##', final)

        # Trim trailing spaces
        final = "\n".join(line.rstrip() for line in final.splitlines())

        return final.strip()
    
    def markdown_to_readable_v2(self, text: str) -> str:
        """
        VERSION 2 — Advanced Markdown to Human Readable Converter
        - Converts tables to simple grids
        - Converts code blocks with indentation
        - Converts nested bullets and numbered lists
        - Converts headings to uppercase readable titles
        - Removes markdown symbols: #, *, -, **, >, etc.
        - Keeps clean spacing & readable formatting
        """

        import re
        from textwrap import fill

        if not text or not isinstance(text, str):
            return text or ""

        # -----------------------------
        # 1. Process code blocks first (```code```)
        # -----------------------------
        def format_code_block(match):
            code_content = match.group(1)
            # Indent code for readability
            indented = "\n".join("    " + line for line in code_content.splitlines())
            return f"\nCODE BLOCK:\n{indented}\n\n"

        text = re.sub(r"```(.*?)```", lambda m: format_code_block(m), text, flags=re.S)

        # -----------------------------
        # 2. Process Markdown tables
        # -----------------------------
        def convert_table(table_text):
            rows = [r.strip() for r in table_text.strip().split("\n") if "|" in r]
            if not rows:
                return table_text

            cleaned_rows = []
            for row in rows:
                cols = [c.strip() for c in row.strip("|").split("|")]
                cleaned_rows.append(" | ".join(cols))

            return "\n".join(cleaned_rows) + "\n"

        text = re.sub(r"((?:\|.*\n)+)", lambda m: convert_table(m.group(1)), text)

        # -----------------------------
        # 3. Convert bold/italic to text
        # -----------------------------
        text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
        text = re.sub(r"\*(.*?)\*", r"\1", text)
        text = re.sub(r"__(.*?)__", r"\1", text)
        text = re.sub(r"_(.*?)_", r"\1", text)

        # -----------------------------
        # 4. Headings (#, ##, ###) → UPPERCASE TITLES
        # -----------------------------
        def heading_to_title(match):
            title = match.group(2).strip()
            return "\n" + title.upper() + "\n"

        text = re.sub(r"^(#{1,6})(\s+)(.*)$", heading_to_title, text, flags=re.M)

        # -----------------------------
        # 5. Horizontal rules
        # -----------------------------
        text = re.sub(r"^\s*[-*_]{3,}\s*$", "\n", text, flags=re.M)

        # -----------------------------
        # 6. Nested Ordered Lists
        # -----------------------------
        text = re.sub(r"^\s*(\d+)[\.\)]\s+", r"\1. ", text, flags=re.M)

        # -----------------------------
        # 7. Nested Unordered Lists
        # -----------------------------
        def convert_bullet(match):
            indent = len(match.group(1)) // 2
            symbol = "•" if indent == 0 else "  " * indent + "◦"
            return f"{symbol} "

        text = re.sub(r"^(\s*)[-*+]\s+", convert_bullet, text, flags=re.M)

        # -----------------------------
        # 8. Remove blockquotes
        # -----------------------------
        text = re.sub(r"^\s*>\s?", "", text, flags=re.M)

        # -----------------------------
        # 9. Wrap paragraphs to readable width (50–70 chars)
        # -----------------------------
        final_lines = []
        for paragraph in text.split("\n"):
            if paragraph.strip().startswith(("•", "◦", "CODE BLOCK", "TABLE")):
                final_lines.append(paragraph)
            else:
                final_lines.append(fill(paragraph, width=70))

        final_text = "\n".join(final_lines)

        # -----------------------------
        # 10. Clean up excess spacing
        # -----------------------------
        final_text = re.sub(r"\n{3,}", "\n\n", final_text).strip()

        return final_text

    def ask(self, question: str, mode: str = "study") -> Dict[str, Any]:
        try:
            if not os.getenv("GOOGLE_API_KEY"):
                return {"answer": "Error: Gemini API key missing.", "sources": [], "used_web": False}

            results = self.collection.query(
                query_texts=[question],
                n_results=8,
                include=["documents", "metadatas", "distances"]
            )

            docs = results["documents"][0] if results["documents"] and results["documents"][0] else []
            context = "\n\n".join(docs) if docs else "No relevant notes found."

            # UNIVERSAL PROMPTS — FOR EVERY LEARNER IN THE WORLD
            MODE_PROMPTS = {
                "study": """
    You are FocusForge — a world-class personal tutor.
    Explain the topic clearly with real-world examples, key concepts, and intuition.
    Use simple language. Add analogies if helpful.
    If not in notes → say "Not in notes yet"
    """,

                "quick": """
    Give only the most important points in crisp bullet form.
    Max 10 lines. No fluff.
    If not in notes → reply "Not in notes yet"
    """,

                "quiz": """
    Generate 3 high-quality practice questions (MCQ or short answer).
    Include correct answer + brief explanation.
    Only use content from uploaded notes.
    If topic not in notes → reply "Not in notes yet"
    """,

                "roadmap": """
    Create a practical 7–14 day learning roadmap for mastering this topic.
    Include daily goals, practice tips, and recommended resources.
    You can give general advice even without notes.
    """,

                "doubt": """
    Act as a patient mentor. Clear the confusion step by step.
    Explain common misconceptions and the correct way to think.
    You can answer from general knowledge — no need for notes.
    """,

                "strategy": """
    You are an expert coach for exams AND job interviews.
    Give smart, actionable tips:
    • How to explain this concept in an interview
    • Common interview/exam questions on this topic
    • How to answer confidently and stand out
    • Time-saving tricks for revision or live coding/whiteboard
    • Red flags to avoid
    Always answer — even without notes. This is universal advice.
    """,
            }

            system_prompt = MODE_PROMPTS.get(mode, MODE_PROMPTS["study"])

            # THIS IS WHERE THE MAGIC HAPPENS
            strict_context_modes = ["study", "quick", "quiz"]

            if mode in strict_context_modes:
                rules = """
    Rules:
    • Answer using ONLY the context from uploaded notes
    • If topic not found in notes → reply exactly: "Not in notes yet"
    • Never hallucinate or make up information"""
            else:
                rules = """
    Rules:
    • Be helpful, practical, and real-world focused
    • You may use general knowledge when notes are missing or incomplete
    • Always encourage the learner"""

            # FINAL PROMPT
            prompt = f"""{system_prompt}
 
    {rules}

    Context from notes:
    {context}

    Question: {question}

    Answer:"""

            answer_raw = self.run_llm(prompt)
            if not answer_raw:
                return {"answer": "All models failed. Try again later.", "sources": [], "used_web": False}

            final_answer = self.markdown_to_readable_v2(self.format_gemini_response(answer_raw))

            response = {
                "answer": final_answer,
                "sources": results["metadatas"][0] if results["metadatas"] and results["metadatas"][0] else [],
                "used_web": False
            }

            # Hide sources only when truly not found
            if "not in notes yet" in final_answer.lower():
                response["sources"] = []

            return response

        except Exception as e:
            # Your error handling
            error_str = str(e).lower()
            if "api key" in error_str:
                return {"answer": "Invalid API key!", "sources": [], "used_web": False}
            elif "rate limit" in error_str:
                return {"answer": "Rate limit reached. Try again in 1 minute.", "sources": [], "used_web": False}
            else:
                return {"answer": f"Error: {e}", "sources": [], "used_web": False}