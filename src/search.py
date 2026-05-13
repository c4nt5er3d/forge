import numpy as np
import pickle
import logging
import re
import math
import json
from collections import Counter
from pathlib import Path
from typing import Any, List, Dict, Tuple, Optional
from rich.progress import Progress

from src.pipeline.ingest import Ingestor
from src.schema.document import Document

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

def inspect_index_dir(index_dir: str = "models/search_index") -> Dict[str, Any]:
    index_path = Path(index_dir) / "faiss.index"
    metadata_path = Path(index_dir) / "metadata.pkl"
    metadata: Dict[int, Dict[str, Any]] = {}
    vector_count = 0

    if metadata_path.exists():
        try:
            with open(metadata_path, 'rb') as f:
                metadata = pickle.load(f)
        except Exception:
            metadata = {}

    if faiss is not None and index_path.exists():
        try:
            vector_count = faiss.read_index(str(index_path)).ntotal
        except Exception:
            vector_count = 0

    metadata_count = len(metadata)
    chunk_count = sum(1 for meta in metadata.values() if meta.get("index_level") == "chunk")
    old_count = metadata_count - chunk_count
    missing_embeddings = sum(1 for meta in metadata.values() if "embedding" not in meta)
    return {
        "index_exists": index_path.exists(),
        "metadata_exists": metadata_path.exists(),
        "vector_count": vector_count,
        "metadata_count": metadata_count,
        "counts_match": vector_count == metadata_count,
        "chunk_records": chunk_count,
        "legacy_records": old_count,
        "missing_embeddings": missing_embeddings,
    }

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

    def _make_chunk_metadata(self, document: Document, chunk: str, chunk_index: int) -> Dict[str, Any]:
        path = Path(document.source_path)
        return {
            "document_id": document.id,
            "chunk_id": f"{document.id}:{chunk_index}",
            "chunk_index": chunk_index,
            "path": document.source_path,
            "name": document.filename,
            "extension": document.extension,
            "snippet": chunk[:500].replace("\n", " ") + ("..." if len(chunk) > 500 else ""),
            "hash": self._file_hash(path) if path.exists() else document.id,
            "quality_score": document.quality_score,
            "tags": document.metadata.get("tags", []),
            "word_count": document.metadata.get("word_count", 0),
            "chunk_count": len(document.chunks),
            "chunk_strategy": document.metadata.get("chunk_strategy"),
            "tokens": tokenize_for_search(chunk),
            "index_level": "chunk",
        }

    def _add_documents_to_index(self, documents: List[Document]) -> int:
        if self.model is None or faiss is None or self.index is None:
            logging.error("Cannot build index without sentence-transformers and faiss-cpu.")
            return 0

        new_embeddings = []
        new_metadata: Dict[int, Dict[str, Any]] = {}
        current_id = self.index.ntotal
        indexed = 0

        for document in documents:
            if document.extraction_error or not document.content:
                continue
            chunks = document.chunks or [document.content]
            for chunk_index, chunk in enumerate(chunks):
                text = clean_text_for_search(chunk)
                if not text:
                    continue
                embedding = self.model.encode([text])[0]
                embedding = self._normalize_embedding(embedding)
                metadata = self._make_chunk_metadata(document, text, chunk_index)
                metadata["embedding"] = embedding.tolist()
                new_embeddings.append(embedding)
                new_metadata[current_id] = metadata
                current_id += 1
                indexed += 1

        if new_embeddings:
            embeddings_array = np.array(new_embeddings).astype('float32')
            self.index.add(embeddings_array)
            self.metadata.update(new_metadata)
            self.save_index()
        return indexed

    def save_index(self):
        if faiss is None or self.index is None:
            return
        faiss.write_index(self.index, str(self.index_path))
        with open(self.metadata_path, 'wb') as f:
            pickle.dump(self.metadata, f)

    def build_index(
        self,
        target_dir: Path,
        progress: Optional[Progress] = None,
        recursive: bool = True,
        exclude: Optional[List[str]] = None,
        chunk_strategy: str = "recursive",
    ):
        if self.model is None or faiss is None or self.index is None:
            logging.error("Cannot build index without sentence-transformers and faiss-cpu.")
            return

        excluded = {f".{e.lstrip('.').lower()}" for e in (exclude or [])}
        ingestor = Ingestor(use_state=False, chunk_strategy=chunk_strategy)
        documents = list(ingestor.run(target_dir, recursive=recursive))
        task = progress.add_task("[cyan]Indexing chunks for semantic search...", total=len(documents)) if progress else None
        indexable_documents = []
        for document in documents:
            if progress and task is not None:
                progress.advance(task)
            if document.extension in excluded:
                continue
            indexable_documents.append(document)
        return self._add_documents_to_index(indexable_documents)

    def build_index_from_jsonl(self, jsonl_path: Path, progress: Optional[Progress] = None) -> int:
        if self.model is None or faiss is None or self.index is None:
            logging.error("Cannot build index without sentence-transformers and faiss-cpu.")
            return 0
        documents = []
        lines = jsonl_path.read_text(encoding="utf-8").splitlines()
        task = progress.add_task("[cyan]Indexing JSONL chunks...", total=len(lines)) if progress else None
        for line in lines:
            if progress and task is not None:
                progress.advance(task)
            if not line.strip():
                continue
            documents.append(Document(**json.loads(line)))
        return self._add_documents_to_index(documents)

    def index_status(self) -> Dict[str, Any]:
        status = inspect_index_dir(str(self.index_dir))
        if self.index is not None:
            status["vector_count"] = self.index.ntotal
            status["counts_match"] = self.index.ntotal == status["metadata_count"]
        return status

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
            meta["_matched_terms"] = [
                token for token in tokenize_for_search(query)
                if token in (self.metadata[idx].get("tokens") or [])
            ]
            fused.append((meta, score))

        results = sorted(fused, key=lambda item: item[1], reverse=True)[:top_k]
        return results
