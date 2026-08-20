"""The evidence-pointer gate lives IN pytest so it cannot go dark.

`tools.doctrine_audit` spent a day asserting nothing because it is offline-only
and nothing went red (2026-08-20). This check is fast and hermetic, so it has no
excuse to live outside the suite.
"""
import os

from tools import pointer_audit


def test_every_markdown_link_resolves():
    """EC-16: a committed pointer is a promise the evidence is readable now.

    This fails when some OTHER file moves - which is exactly the case no author
    can catch by reviewing their own diff.
    """
    dangling = pointer_audit.dangling_links()
    assert not dangling, (
        "dangling evidence pointer(s):\n"
        + "\n".join(f"  {rel} -> {target}" for rel, target in dangling)
        + "\nRepoint at where the evidence MOVED; archiving a doc keeps its"
          " value, deleting the pointer destroys it."
    )


def test_the_audit_actually_reads_the_repo():
    """Guard the guard: an empty scan would pass the test above vacuously."""
    docs = pointer_audit._tracked("*.md")
    assert len(docs) > 50, f"expected the repo's docs, scanned {len(docs)}"
    assert "docs/decisions.md" in docs


def test_a_broken_link_is_detected(tmp_path, monkeypatch):
    """The detector's own bite-proof - a real miss must be reported."""
    repo = tmp_path
    (repo / "docs").mkdir()
    (repo / "docs" / "real.md").write_text("# real", encoding="utf-8")
    (repo / "docs" / "carrier.md").write_text(
        "[alive](real.md) and [anchored](real.md#heading) and [gone](missing.md)",
        encoding="utf-8")

    monkeypatch.setattr(pointer_audit, "_REPO_ROOT", str(repo))
    monkeypatch.setattr(pointer_audit, "_tracked",
                        lambda *patterns: ["docs/carrier.md", "docs/real.md"])

    dangling = pointer_audit.dangling_links()
    assert dangling == [("docs/carrier.md", "missing.md")], (
        "expected exactly the missing target - a live link and an anchored link "
        f"into a real file must both resolve, got {dangling}"
    )


def test_external_and_anchor_only_links_are_skipped(tmp_path, monkeypatch):
    """A URL is not ours to resolve, and a bare #anchor points inside itself."""
    repo = tmp_path
    (repo / "docs").mkdir()
    (repo / "docs" / "c.md").write_text(
        "[web](https://example.com/x.md) [mail](mailto:a@b.c) [own](#section)",
        encoding="utf-8")
    monkeypatch.setattr(pointer_audit, "_REPO_ROOT", str(repo))
    monkeypatch.setattr(pointer_audit, "_tracked", lambda *p: ["docs/c.md"])

    assert pointer_audit.dangling_links() == []


def test_module_paths_are_not_mistaken_for_files(tmp_path, monkeypatch):
    """`tools.shadow_diff` is an import, not a path - the advisory must not bite."""
    repo = tmp_path
    (repo / "docs").mkdir()
    (repo / "docs" / "c.md").write_text(
        "run `tools.shadow_diff --check`, see `manifest.ENGINE_SETTINGS_KEYS`, "
        "and note core/structure/gone.py moved",
        encoding="utf-8")
    monkeypatch.setattr(pointer_audit, "_REPO_ROOT", str(repo))
    monkeypatch.setattr(pointer_audit, "_tracked", lambda *p: ["docs/c.md"])

    hits = [path for _, path in pointer_audit.dangling_paths()]
    assert hits == ["core/structure/gone.py"], (
        f"only the real path mention should be reported, got {hits}")


def test_generated_output_is_never_a_citation(tmp_path, monkeypatch):
    """A tool naming the file it writes is not a dangling pointer."""
    repo = tmp_path
    (repo / "tools").mkdir()
    (repo / "tools" / "t.py").write_text(
        "# writes output/census.json when run\n", encoding="utf-8")
    monkeypatch.setattr(pointer_audit, "_REPO_ROOT", str(repo))
    monkeypatch.setattr(pointer_audit, "_tracked", lambda *p: ["tools/t.py"])

    assert pointer_audit.dangling_paths() == []


def test_the_tool_is_where_the_docs_say_it_is():
    """AGENTS.md hands an agent this exact command; keep the module path true."""
    assert os.path.exists(os.path.join(
        pointer_audit._REPO_ROOT, "tools", "pointer_audit.py"))
