import json

from typer.testing import CliRunner

from src.main import app
from src.pack import build_context_pack, estimate_tokens, render_markdown_pack, write_context_pack
from src.schema.document import Document


def _document(tmp_path, name, chunks, tags=None, quality=0.6):
    file_path = tmp_path / name
    file_path.write_text("\n\n".join(chunks), encoding="utf-8")
    return Document.from_file(
        file_path,
        content="\n\n".join(chunks),
        chunks=chunks,
        metadata={"tags": tags or []},
        quality_score=quality,
    )


def test_build_context_pack_respects_token_budget(tmp_path):
    doc = _document(
        tmp_path,
        "notes.txt",
        [
            "alpha " * 80,
            "beta " * 80,
            "gamma " * 80,
        ],
    )

    pack = build_context_pack([doc], token_budget=90, reserve_tokens=10)

    assert pack.estimated_tokens <= pack.available_tokens
    assert pack.entries
    assert pack.skipped_chunks > 0


def test_build_context_pack_prioritizes_query_matches(tmp_path):
    doc = _document(
        tmp_path,
        "planning.txt",
        [
            "This chunk is about lunch notes and unrelated chores.",
            "Budget approval timeline with procurement and planning details.",
        ],
        tags=["budget"],
    )

    pack = build_context_pack([doc], token_budget=500, reserve_tokens=50, query="budget approval")

    assert pack.entries[0].chunk_index == 1
    assert "Budget approval" in pack.entries[0].text


def test_render_markdown_pack_includes_manifest_and_sources(tmp_path):
    doc = _document(tmp_path, "source.txt", ["Useful local context."])
    pack = build_context_pack([doc], token_budget=500, reserve_tokens=50)

    markdown = render_markdown_pack(pack)

    assert "# Forge Context Pack" in markdown
    assert '"format": "forge-context-pack"' in markdown
    assert "source.txt" in markdown
    assert "Useful local context." in markdown


def test_write_context_pack_jsonl(tmp_path):
    doc = _document(tmp_path, "source.txt", ["Useful local context."])
    pack = build_context_pack([doc], token_budget=500, reserve_tokens=50)
    output = tmp_path / "pack.jsonl"

    write_context_pack(pack, output, "jsonl")

    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["type"] == "manifest"
    assert rows[1]["type"] == "context"
    assert rows[1]["filename"] == "source.txt"


def test_estimate_tokens_is_deterministic():
    assert estimate_tokens("one two three four") == estimate_tokens("one two three four")
    assert estimate_tokens("") == 0


def test_pack_cli_from_folder(tmp_path):
    runner = CliRunner()
    source = tmp_path / "source"
    source.mkdir()
    (source / "notes.txt").write_text(
        "Budget planning notes for approvals and delivery tracking.",
        encoding="utf-8",
    )
    output = tmp_path / "context.md"

    result = runner.invoke(
        app,
        [
            "pack",
            str(source),
            "--output",
            str(output),
            "--token-budget",
            "1000",
            "--reserve-tokens",
            "100",
            "--query",
            "budget approvals",
        ],
    )

    assert result.exit_code == 0
    assert output.exists()
    assert "Forge Context Pack" in output.read_text(encoding="utf-8")
    assert "Pack complete" in result.output
