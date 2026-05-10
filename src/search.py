import os
import faiss
import numpy as np
import pickle
import logging
from pathlib import Path
from typing import List, Dict, Tuple
from rich.progress import Progress

from src.llm import extract_text
from src.utils import collect_files

class SemanticSearch:
    def __init__(self, index_dir: str = "models/search_index"):
        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.index_dir / "faiss.index"
        self.metadata_path = self.index_dir / "metadata.pkl"
        
        try:
            from sentence_transformers import SentenceTransformer
            # We use a fast, lightweight embedding model
            logging.info("Loading SentenceTransformer model...")
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
            self.dimension = self.model.get_sentence_embedding_dimension()
        except ImportError:
            logging.error("sentence-transformers not installed.")
            self.model = None
            self.dimension = 384 # default for all-MiniLM-L6-v2
            
        self.index = None
        self.metadata: Dict[int, Dict[str, str]] = {}
        self.load_index()

    def load_index(self):
        if self.index_path.exists() and self.metadata_path.exists():
            try:
                self.index = faiss.read_index(str(self.index_path))
                with open(self.metadata_path, 'rb') as f:
                    self.metadata = pickle.load(f)
            except Exception as e:
                logging.error(f"Failed to load search index: {e}")
                self.index = faiss.IndexFlatL2(self.dimension)
        else:
            self.index = faiss.IndexFlatL2(self.dimension)

    def save_index(self):
        faiss.write_index(self.index, str(self.index_path))
        with open(self.metadata_path, 'wb') as f:
            pickle.dump(self.metadata, f)

    def build_index(self, target_dir: Path, progress: Progress):
        if self.model is None:
            logging.error("Cannot build index without sentence-transformers.")
            return

        files = collect_files(target_dir, recursive=True)
        if not files:
            return

        task = progress.add_task("[cyan]Indexing files for semantic search...", total=len(files))
        
        new_embeddings = []
        new_metadata = {}
        current_id = self.index.ntotal

        for file in files:
            progress.advance(task)
            
            # Skip hidden files
            if file.name.startswith("."):
                continue
                
            # Extract text using our existing LLM extraction pipeline (OCR + PyPDF2 + TXT)
            text = extract_text(file)
            if not text:
                continue
                
            # Convert the text into a mathematical vector
            embedding = self.model.encode([text])[0]
            new_embeddings.append(embedding)
            
            # Save the human-readable metadata so we can map the vector back to the file
            new_metadata[current_id] = {
                "path": str(file.resolve()),
                "name": file.name,
                "snippet": text[:200].replace("\n", " ") + "..."
            }
            current_id += 1
            
        if new_embeddings:
            embeddings_array = np.array(new_embeddings).astype('float32')
            self.index.add(embeddings_array)
            self.metadata.update(new_metadata)
            self.save_index()

    def search(self, query: str, top_k: int = 3) -> List[Tuple[Dict[str, str], float]]:
        """Searches the vector database using natural language."""
        if self.index is None or self.index.ntotal == 0 or self.model is None:
            return []
            
        query_embedding = self.model.encode([query]).astype('float32')
        # L2 distance (lower is better)
        distances, indices = self.index.search(query_embedding, top_k)
        
        results = []
        for i in range(len(indices[0])):
            idx = indices[0][i]
            if idx != -1 and idx in self.metadata:
                results.append((self.metadata[idx], float(distances[0][i])))
                
        return results
