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


def test_a_link_into_an_untracked_file_is_dangling(tmp_path, monkeypatch):
    """Clone safety: the basis is what git CARRIES, not what sits on this disk.

    Found 2026-08-20, in this gate's own first day: four links in
    flag_ledger.md pointed at root PLAN-*.md files that .gitignore excludes.
    They opened fine on the author's machine and were dead in a fresh clone -
    precisely the breakage the gate exists to catch, passed by the gate itself
    because it asked the filesystem instead of git.
    """
    repo = tmp_path
    (repo / "docs").mkdir()
    (repo / "scratch.md").write_text("here but untracked", encoding="utf-8")
    (repo / "docs" / "c.md").write_text("[local](../scratch.md)",
                                        encoding="utf-8")
    monkeypatch.setattr(pointer_audit, "_REPO_ROOT", str(repo))
    monkeypatch.setattr(pointer_audit, "_tracked", lambda *p: ["docs/c.md"])

    assert pointer_audit.dangling_links() == [("docs/c.md", "../scratch.md")], (
        "a link into a file git does not carry must be reported: it resolves "
        "on this disk and not in a clone")


def test_a_link_to_a_tracked_directory_resolves(tmp_path, monkeypatch):
    """`[the archive](archive/)` is a legitimate pointer at a real place."""
    repo = tmp_path
    (repo / "docs" / "archive").mkdir(parents=True)
    (repo / "docs" / "archive" / "old.md").write_text("archived",
                                                      encoding="utf-8")
    (repo / "docs" / "c.md").write_text(
        "[archive](archive/) and [nowhere](ghost/)", encoding="utf-8")
    monkeypatch.setattr(pointer_audit, "_REPO_ROOT", str(repo))
    monkeypatch.setattr(pointer_audit, "_tracked",
                        lambda *p: ["docs/c.md", "docs/archive/old.md"])

    assert pointer_audit.dangling_links() == [("docs/c.md", "ghost/")]


def test_a_link_that_escapes_the_repo_is_dangling(tmp_path, monkeypatch):
    """`../../elsewhere` is never something a clone can open."""
    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    (repo / "docs" / "c.md").write_text("[out](../../outside.md)",
                                        encoding="utf-8")
    (tmp_path / "outside.md").write_text("real, but not ours", encoding="utf-8")
    monkeypatch.setattr(pointer_audit, "_REPO_ROOT", str(repo))
    monkeypatch.setattr(pointer_audit, "_tracked", lambda *p: ["docs/c.md"])

    assert pointer_audit.dangling_links() == [("docs/c.md", "../../outside.md")]


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


def test_an_archived_carrier_is_exempt_from_the_advisory(tmp_path, monkeypatch):
    """A sealed record names its own era's files, and those are SUPPOSED to be
    gone. Counting them buried ~30 live-doc hits under 77 archived ones until
    the advisory was split. The link gate above still covers archived docs."""
    repo = tmp_path
    (repo / "docs" / "archive").mkdir(parents=True)
    (repo / "docs" / "archive" / "old.md").write_text(
        "that program ran core/structure/gone.py", encoding="utf-8")
    (repo / "docs" / "live.md").write_text(
        "see tools/missing.py", encoding="utf-8")
    monkeypatch.setattr(pointer_audit, "_REPO_ROOT", str(repo))
    monkeypatch.setattr(pointer_audit, "_tracked",
                        lambda *p: ["docs/archive/old.md", "docs/live.md"])

    assert [h for _, h in pointer_audit.dangling_paths()] == [
        "tools/missing.py"], "an archived carrier must not reach the advisory"
    assert [h for _, h in pointer_audit.dangling_paths(include_archive=True)] == [
        "core/structure/gone.py", "tools/missing.py"
    ], "include_archive=True must still show everything - no silent cap"
