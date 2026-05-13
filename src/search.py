import numpy as np
import pickle
import logging
import re
import math
from collections import Counter
from pathlib import Path
from typing import Any, List, Dict, Tuple, Optional
from rich.progress import Progress

from src.llm import extract_text
from src.utils import collect_files

try:
    import faiss
except ImportError:
    faiss = None

try:
    from rank_bm25 import BM25Okapi
except ImportError:
    BM25Okapi = None

def clean_text_for_search(text: str) -> str:
    # Removes underscores, dashes, and extra whitespace that create noise for the ML model.
    text = re.sub(r'[_]{3,}', ' ', text)
    text = re.sub(r'[-]{3,}', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def tokenize_for_search(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]{2,}", text.lower())

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
        self.metadata: Dict[int, Dict[str, Any]] = {}
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

    def _normalize_embedding(self, embedding) -> np.ndarray:
        embedding_array = np.array(embedding).astype('float32')
        norm = np.linalg.norm(embedding_array)
        if norm == 0:
            return embedding_array
        return embedding_array / norm

    def _bm25_scores(self, query: str, ordered_items: List[Tuple[int, Dict[str, Any]]]) -> Dict[int, float]:
        query_tokens = tokenize_for_search(query)
        if not query_tokens or not ordered_items:
            return {}

        corpus = [
            meta.get("tokens") or tokenize_for_search(meta.get("snippet", ""))
            for _idx, meta in ordered_items
        ]
        if BM25Okapi is not None:
            scores = BM25Okapi(corpus).get_scores(query_tokens)
            max_score = max(scores) if len(scores) else 0
            if max_score <= 0:
                return {}
            return {
                idx: float(score / max_score)
                for (idx, _meta), score in zip(ordered_items, scores)
                if score > 0
            }

        doc_count = len(corpus)
        doc_freq: Counter[str] = Counter()
        for tokens in corpus:
            doc_freq.update(set(tokens))

        raw_scores: Dict[int, float] = {}
        avg_len = sum(len(tokens) for tokens in corpus) / max(doc_count, 1)
        k1 = 1.5
        b = 0.75
        for (idx, _meta), tokens in zip(ordered_items, corpus):
            token_counts = Counter(tokens)
            doc_len = len(tokens) or 1
            score = 0.0
            for token in query_tokens:
                if token not in token_counts:
                    continue
                idf = math.log(1 + (doc_count - doc_freq[token] + 0.5) / (doc_freq[token] + 0.5))
                freq = token_counts[token]
                denom = freq + k1 * (1 - b + b * doc_len / max(avg_len, 1))
                score += idf * (freq * (k1 + 1)) / denom
            if score > 0:
                raw_scores[idx] = score

        max_score = max(raw_scores.values(), default=0)
        if max_score <= 0:
            return {}
        return {idx: score / max_score for idx, score in raw_scores.items()}

    def _rebuild_clean_index(self):
        """Remove stale entries and rebuild FAISS index from clean metadata."""
        if faiss is None:
            return
        valid_metadata = {}
        valid_embeddings = []
        
        # Collect only valid files
        for meta in self.metadata.values():
            path = Path(meta["path"])
            if path.exists() and self._file_hash(path) == meta.get("hash"):
                embedding = meta.get("embedding")
                if embedding is None:
                    if self.model is None:
                        continue
                    # Backward compatibility for old indexes created before
                    # embeddings were persisted in metadata.
                    embedding = self.model.encode([meta["snippet"]])[0]
                    embedding = self._normalize_embedding(embedding)
                    meta["embedding"] = embedding.tolist()
                else:
                    embedding = self._normalize_embedding(embedding)
                    meta["embedding"] = embedding.tolist()
                valid_metadata[len(valid_embeddings)] = meta
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
            embedding = self._normalize_embedding(embedding)
            new_embeddings.append(embedding)
            
            # Vector stores only save IDs; we must persist our own metadata 
            # to map IDs back to human-readable file paths and snippets.
            new_metadata[current_id] = {
                "path": str(file.resolve()),
                "name": file.name,
                "snippet": text[:500].replace("\n", " ") + "...",
                "hash": self._file_hash(file),
                "embedding": embedding.tolist(),
                "tokens": tokenize_for_search(text)
            }
            current_id += 1
            
        if new_embeddings:
            # FAISS expects float32 arrays for IndexFlatL2 distance calculations.
            embeddings_array = np.array(new_embeddings).astype('float32')
            self.index.add(embeddings_array)
            self.metadata.update(new_metadata)
            self.save_index()

    def search(self, query: str, top_k: int = 3) -> List[Tuple[Dict[str, Any], float]]:
        # Fuse dense vector retrieval with lightweight lexical BM25 scoring.
        if self.index is None or self.index.ntotal == 0 or self.model is None:
            return []
            
        query_embedding = self.model.encode([query])[0]
        query_embedding = self._normalize_embedding(query_embedding).reshape(1, -1)
        candidate_count = min(max(top_k * 4, top_k), self.index.ntotal)
        distances, indices = self.index.search(query_embedding, candidate_count)

        dense_scores: Dict[int, float] = {}
        for i in range(len(indices[0])):
            idx = indices[0][i]
            if idx != -1 and idx in self.metadata:
                distance = float(distances[0][i])
                dense_scores[idx] = max(0.0, 1 - (distance ** 2) / 2)

        ordered_items = sorted(self.metadata.items(), key=lambda item: item[0])
        bm25_scores = self._bm25_scores(query, ordered_items)
        candidate_ids = set(dense_scores) | set(bm25_scores)

        fused = []
        for idx in candidate_ids:
            dense = dense_scores.get(idx, 0.0)
            lexical = bm25_scores.get(idx, 0.0)
            score = (0.65 * dense) + (0.35 * lexical)
            meta = dict(self.metadata[idx])
            meta["_score_type"] = "hybrid"
            meta["_score"] = score
            meta["_dense_score"] = dense
            meta["_bm25_score"] = lexical
            fused.append((meta, score))

        results = sorted(fused, key=lambda item: item[1], reverse=True)[:top_k]
        return results
