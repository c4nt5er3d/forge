from pathlib import Path
from typing import Any, Callable, Iterable, Optional, Union

from src.dataset import prepare_dataset_documents
from src.exporters import load_documents
from src.evaluate import evaluate_cases, load_evaluation_cases
from src.pack import build_context_pack, render_markdown_pack


class ForgeService:
    def __init__(
        self,
        allowed_roots: Optional[Iterable[Path]] = None,
        searcher_factory: Optional[Callable[[str], Any]] = None,
    ):
        roots = list(allowed_roots or [Path.cwd()])
        self.allowed_roots = [root.resolve() for root in roots]
        self.searcher_factory = searcher_factory

    def _resolve_allowed_path(self, value: Union[str, Path]) -> Path:
        path = Path(value).expanduser().resolve()
        if not any(path == root or root in path.parents for root in self.allowed_roots):
            roots = ", ".join(str(root) for root in self.allowed_roots)
            raise ValueError(f"Path is outside allowed roots: {path}. Allowed roots: {roots}")
        return path

    def _load_documents(
        self,
        target: Optional[str] = None,
        from_jsonl: Optional[str] = None,
        recursive: bool = False,
        chunk_strategy: str = "recursive",
    ):
        target_path = self._resolve_allowed_path(target) if target else None
        jsonl_path = self._resolve_allowed_path(from_jsonl) if from_jsonl else None
        return load_documents(
            target=target_path,
            from_jsonl=jsonl_path,
            recursive=recursive,
            chunk_strategy=chunk_strategy,
        )

    def _searcher(self, index_dir: str = "models/search_index"):
        resolved_index_dir = self._resolve_allowed_path(index_dir)
        if self.searcher_factory is not None:
            return self.searcher_factory(str(resolved_index_dir))
        from src.search import SemanticSearch

        return SemanticSearch(index_dir=str(resolved_index_dir))

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "forge",
            "allowed_roots": [str(root) for root in self.allowed_roots],
        }

    def search(
        self,
        query: str,
        limit: int = 5,
        index_dir: str = "models/search_index",
        rerank: bool = False,
        compress: bool = False,
    ) -> dict[str, Any]:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        results = self._searcher(index_dir).search(query, limit, rerank=rerank, compress=compress)
        return {
            "query": query,
            "count": len(results),
            "results": [_summarize_search_result(metadata, score) for metadata, score in results],
        }

    def pack(
        self,
        target: Optional[str] = None,
        from_jsonl: Optional[str] = None,
        recursive: bool = False,
        chunk_strategy: str = "recursive",
        token_budget: int = 8000,
        reserve_tokens: int = 500,
        query: Optional[str] = None,
        include_markdown: bool = False,
    ) -> dict[str, Any]:
        documents = self._load_documents(
            target=target,
            from_jsonl=from_jsonl,
            recursive=recursive,
            chunk_strategy=chunk_strategy,
        )
        pack = build_context_pack(
            documents,
            token_budget=token_budget,
            reserve_tokens=reserve_tokens,
            query=query,
        )
        response = {
            "manifest": pack.manifest(),
            "entries": [entry.__dict__ for entry in pack.entries],
        }
        if include_markdown:
            response["markdown"] = render_markdown_pack(pack)
        return response

    def dataset(
        self,
        target: Optional[str] = None,
        from_jsonl: Optional[str] = None,
        recursive: bool = False,
        chunk_strategy: str = "recursive",
        dedup: bool = True,
        semantic: bool = False,
        threshold: float = 0.97,
    ) -> dict[str, Any]:
        if semantic and not dedup:
            raise ValueError("semantic dedup requires deduplication")
        documents = self._load_documents(
            target=target,
            from_jsonl=from_jsonl,
            recursive=recursive,
            chunk_strategy=chunk_strategy,
        )
        output_documents, result = prepare_dataset_documents(
            documents,
            dedup=dedup,
            semantic=semantic,
            threshold=threshold,
        )
        return {
            "manifest": result.manifest(),
            "documents": [_document_to_dict(document) for document in output_documents],
        }

    def evaluate(
        self,
        cases: str,
        limit: int = 5,
        index_dir: str = "models/search_index",
        rerank: bool = False,
        compress: bool = False,
    ) -> dict[str, Any]:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        cases_path = self._resolve_allowed_path(cases)
        report = evaluate_cases(
            load_evaluation_cases(cases_path),
            self._searcher(index_dir),
            top_k=limit,
            rerank=rerank,
            compress=compress,
        )
        return report.to_dict()


def create_app(service: Optional[ForgeService] = None):
    try:
        from fastapi import FastAPI, HTTPException
        from pydantic import BaseModel
    except ImportError as exc:
        raise ImportError("fastapi is required for forge serve. Install with file-organizer[server].") from exc

    service = service or ForgeService()
    app = FastAPI(title="FORGE Local API", version="0.1.0")

    class SearchRequest(BaseModel):
        query: str
        limit: int = 5
        index_dir: str = "models/search_index"
        rerank: bool = False
        compress: bool = False

    class PackRequest(BaseModel):
        target: Optional[str] = None
        from_jsonl: Optional[str] = None
        recursive: bool = False
        chunk_strategy: str = "recursive"
        token_budget: int = 8000
        reserve_tokens: int = 500
        query: Optional[str] = None
        include_markdown: bool = False

    class DatasetRequest(BaseModel):
        target: Optional[str] = None
        from_jsonl: Optional[str] = None
        recursive: bool = False
        chunk_strategy: str = "recursive"
        dedup: bool = True
        semantic: bool = False
        threshold: float = 0.97

    class EvaluateRequest(BaseModel):
        cases: str
        limit: int = 5
        index_dir: str = "models/search_index"
        rerank: bool = False
        compress: bool = False

    def handle(call):
        try:
            return call()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/health")
    def health():
        return service.health()

    @app.post("/search")
    def search(request: SearchRequest):
        return handle(lambda: service.search(**request.dict()))

    @app.post("/pack")
    def pack(request: PackRequest):
        return handle(lambda: service.pack(**request.dict()))

    @app.post("/dataset")
    def dataset(request: DatasetRequest):
        return handle(lambda: service.dataset(**request.dict()))

    @app.post("/evaluate")
    def evaluate(request: EvaluateRequest):
        return handle(lambda: service.evaluate(**request.dict()))

    return app


def _summarize_search_result(metadata: dict[str, Any], score: float) -> dict[str, Any]:
    return {
        "name": metadata.get("name") or metadata.get("filename", ""),
        "path": metadata.get("path") or metadata.get("source_path", ""),
        "document_id": metadata.get("document_id", ""),
        "chunk_id": metadata.get("chunk_id", ""),
        "chunk_index": metadata.get("chunk_index"),
        "score": metadata.get("_score", score),
        "dense_score": metadata.get("_dense_score"),
        "bm25_score": metadata.get("_bm25_score"),
        "matched_terms": metadata.get("_matched_terms", []),
        "snippet": metadata.get("_compressed_snippet") or metadata.get("snippet", ""),
    }


def _document_to_dict(document) -> dict[str, Any]:
    if hasattr(document, "model_dump"):
        return document.model_dump()
    return document.dict()
