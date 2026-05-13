from pathlib import Path
from typing import Any, Iterable, Optional

from src.server import ForgeService


class ForgeMCPTools:
    """Thin MCP-facing wrapper around ForgeService.

    Keeping these methods independent from the MCP SDK makes the integration
    easy to test and keeps the actual protocol adapter small.
    """

    def __init__(self, service: ForgeService):
        self.service = service

    def health(self) -> dict[str, Any]:
        return self.service.health()

    def search(
        self,
        query: str,
        limit: int = 5,
        index_dir: str = "models/search_index",
        rerank: bool = False,
        compress: bool = False,
    ) -> dict[str, Any]:
        return self.service.search(
            query=query,
            limit=limit,
            index_dir=index_dir,
            rerank=rerank,
            compress=compress,
        )

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
        return self.service.pack(
            target=target,
            from_jsonl=from_jsonl,
            recursive=recursive,
            chunk_strategy=chunk_strategy,
            token_budget=token_budget,
            reserve_tokens=reserve_tokens,
            query=query,
            include_markdown=include_markdown,
        )

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
        return self.service.dataset(
            target=target,
            from_jsonl=from_jsonl,
            recursive=recursive,
            chunk_strategy=chunk_strategy,
            dedup=dedup,
            semantic=semantic,
            threshold=threshold,
        )

    def evaluate(
        self,
        cases: str,
        limit: int = 5,
        index_dir: str = "models/search_index",
        rerank: bool = False,
        compress: bool = False,
    ) -> dict[str, Any]:
        return self.service.evaluate(
            cases=cases,
            limit=limit,
            index_dir=index_dir,
            rerank=rerank,
            compress=compress,
        )


def create_mcp_server(service: Optional[ForgeService] = None):
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise ImportError("mcp is required for forge mcp. Install with the file-organizer mcp extra.") from exc

    tools = ForgeMCPTools(service or ForgeService())
    mcp = FastMCP("forge")

    @mcp.tool()
    def forge_health() -> dict[str, Any]:
        """Return Forge service status and allowed roots."""
        return tools.health()

    @mcp.tool()
    def forge_search(
        query: str,
        limit: int = 5,
        index_dir: str = "models/search_index",
        rerank: bool = False,
        compress: bool = False,
    ) -> dict[str, Any]:
        """Search the local Forge index."""
        return tools.search(
            query=query,
            limit=limit,
            index_dir=index_dir,
            rerank=rerank,
            compress=compress,
        )

    @mcp.tool()
    def forge_pack(
        target: Optional[str] = None,
        from_jsonl: Optional[str] = None,
        recursive: bool = False,
        chunk_strategy: str = "recursive",
        token_budget: int = 8000,
        reserve_tokens: int = 500,
        query: Optional[str] = None,
        include_markdown: bool = False,
    ) -> dict[str, Any]:
        """Build a token-aware context pack from local files or Document JSONL."""
        return tools.pack(
            target=target,
            from_jsonl=from_jsonl,
            recursive=recursive,
            chunk_strategy=chunk_strategy,
            token_budget=token_budget,
            reserve_tokens=reserve_tokens,
            query=query,
            include_markdown=include_markdown,
        )

    @mcp.tool()
    def forge_dataset(
        target: Optional[str] = None,
        from_jsonl: Optional[str] = None,
        recursive: bool = False,
        chunk_strategy: str = "recursive",
        dedup: bool = True,
        semantic: bool = False,
        threshold: float = 0.97,
    ) -> dict[str, Any]:
        """Build a cleaned local dataset preview from files or Document JSONL."""
        return tools.dataset(
            target=target,
            from_jsonl=from_jsonl,
            recursive=recursive,
            chunk_strategy=chunk_strategy,
            dedup=dedup,
            semantic=semantic,
            threshold=threshold,
        )

    @mcp.tool()
    def forge_evaluate(
        cases: str,
        limit: int = 5,
        index_dir: str = "models/search_index",
        rerank: bool = False,
        compress: bool = False,
    ) -> dict[str, Any]:
        """Evaluate local search quality against JSON or JSONL cases."""
        return tools.evaluate(
            cases=cases,
            limit=limit,
            index_dir=index_dir,
            rerank=rerank,
            compress=compress,
        )

    return mcp


def run_mcp_server(allowed_roots: Optional[Iterable[Path]] = None) -> None:
    service = ForgeService(allowed_roots=allowed_roots)
    create_mcp_server(service).run()
