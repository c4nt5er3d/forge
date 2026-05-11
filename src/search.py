import os
import numpy as np
import pickle
import logging
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from rich.progress import Progress

from src.llm import extract_text
from src.utils import collect_files

try:
    import faiss
except ImportError:
    faiss = None

def clean_text_for_search(text: str) -> str:
    # Removes underscores, dashes, and extra whitespace that create noise for the ML model.
    text = re.sub(r'[_]{3,}', ' ', text)
    text = re.sub(r'[-]{3,}', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

class SemanticSearch:
    def __init__(self, index_dir: str = "models/search_index"):
        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.index_dir / "faiss.index"
        self.metadata_path = self.index_dir / "metadata.pkl"
        
        try:
            from sentence_transformers import SentenceTransformer
            # 'all-MiniLM-L6-v2' is chosen for its excellent balance between 
            # encoding speed and semantic accuracy on local hardware.
            logging.info("Loading SentenceTransformer model...")
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
            self.dimension = self.model.get_sentence_embedding_dimension()
        except ImportError:
            logging.error("sentence-transformers not installed.")
            self.model = None
            self.dimension = 384 # Standard dimension for the MiniLM model series.
            
        self.index = None
        self.metadata: Dict[int, Dict[str, str]] = {}
        self.load_index()

    def load_index(self):
        if faiss is None:
            logging.error("faiss-cpu not installed.")
            self.index = None
            return
        if self.index_path.exists() and self.metadata_path.exists():
            try:
                self.index = faiss.read_index(str(self.index_path))
                with open(self.metadata_path, 'rb') as f:
                    self.metadata = pickle.load(f)
                if self.model is not None:
                    self._rebuild_clean_index()
            except Exception as e:
                logging.error(f"Failed to load search index: {e}")
                self.index = faiss.IndexFlatL2(self.dimension)
        else:
            self.index = faiss.IndexFlatL2(self.dimension)

    def _file_hash(self, file: Path) -> str:
        stat = file.stat()
        return f"{stat.st_mtime}_{stat.st_size}"

    def _rebuild_clean_index(self):
        """Remove stale entries and rebuild FAISS index from clean metadata."""
        if faiss is None or self.model is None:
            return
        valid_metadata = {}
        valid_embeddings = []
        
        # Collect only valid files
        for idx, meta in self.metadata.items():
            path = Path(meta["path"])
            if path.exists() and self._file_hash(path) == meta.get("hash"):
                valid_metadata[len(valid_embeddings)] = meta
                # We need to re-encode because we don't store raw embeddings.
                embedding = self.model.encode([meta["snippet"]])[0]
                valid_embeddings.append(embedding)
        
        self.index = faiss.IndexFlatL2(self.dimension)
        if valid_embeddings:
            embeddings_array = np.array(valid_embeddings).astype('float32')
            self.index.add(embeddings_array)
        
        self.metadata = valid_metadata
        self.save_index()

    def save_index(self):
        if faiss is None or self.index is None:
            return
        faiss.write_index(self.index, str(self.index_path))
        with open(self.metadata_path, 'wb') as f:
            pickle.dump(self.metadata, f)

    def build_index(self, target_dir: Path, progress: Optional[Progress] = None, recursive: bool = True, exclude: Optional[List[str]] = None):
        if self.model is None or faiss is None or self.index is None:
            logging.error("Cannot build index without sentence-transformers and faiss-cpu.")
            return

        excluded = {f".{e.lstrip('.').lower()}" for e in (exclude or [])}
        files = collect_files(target_dir, recursive=recursive)
        if not files:
            return

        task = progress.add_task("[cyan]Indexing files for semantic search...", total=len(files)) if progress else None
        
        new_embeddings = []
        new_metadata = {}
        current_id = self.index.ntotal

        for file in files:
            if progress and task is not None:
                progress.advance(task)
            
            # Explicitly ignore git internals and hidden files
            if ".git" in file.parts or file.name.startswith("."):
                continue
            if file.suffix.lower() in excluded:
                continue
                
            # We reuse the LLM extraction pipeline to ensure search and 
            # categorization see the exact same content representation.
            raw_text = extract_text(file)
            if not raw_text:
                continue

            # Clean text to remove OCR/Formatting artifacts before embedding
            text = clean_text_for_search(raw_text)
                
            # Embeddings turn human language into a vector space where 
            # 'meaning' is represented by spatial proximity.
            embedding = self.model.encode([text])[0]
            # Normalize for cosine similarity calculation
            embedding = embedding / np.linalg.norm(embedding)
            new_embeddings.append(embedding)
            
            # Vector stores only save IDs; we must persist our own metadata 
            # to map IDs back to human-readable file paths and snippets.
            new_metadata[current_id] = {
                "path": str(file.resolve()),
                "name": file.name,
                "snippet": text[:500].replace("\n", " ") + "...",
                "hash": self._file_hash(file)
            }
            current_id += 1
            
        if new_embeddings:
            # FAISS expects float32 arrays for IndexFlatL2 distance calculations.
            embeddings_array = np.array(new_embeddings).astype('float32')
            self.index.add(embeddings_array)
            self.metadata.update(new_metadata)
            self.save_index()

    def search(self, query: str, top_k: int = 3) -> List[Tuple[Dict[str, str], float]]:
        # Natural language query is embedded into the same vector space as the files.
        # We then find the 'k' nearest neighbors using Euclidean (L2) distance.
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
