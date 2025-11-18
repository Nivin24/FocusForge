# backend/app/rag/indexer.py
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
import os

class DocumentIndexer:
    def __init__(self, collection):
        self.collection = collection  # This is the Chroma collection
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,
            chunk_overlap=100,
            separators=["\n\n", "\n", " ", ""],
            keep_separator=True
        )

    def index_file(self, file_path: str, source_name: str = None) -> str:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        # Load PDF or Text
        loader = PyPDFLoader(file_path) if file_path.lower().endswith(".pdf") \
                 else TextLoader(file_path, encoding="utf-8")
        docs = loader.load()

        source = source_name or os.path.basename(file_path)
        for doc in docs:
            doc.metadata["source"] = source

        # Split → chunks
        chunks = self.splitter.split_documents(docs)

        # Add to Chroma (auto-embeds)
        self.collection.add(
            documents=[c.page_content for c in chunks],
            metadatas=[c.metadata for c in chunks],
            ids=[f"{source}_{i}" for i in range(len(chunks))]
        )

        print(f"Indexed {len(chunks)} chunks from {source}")
        return f"Indexed {len(chunks)} chunks from {source}"