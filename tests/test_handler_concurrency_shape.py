"""Route handlers are sync ``def`` on purpose — pinned, not just documented.

The house rule (AGENTS.md, "Backend rules") is that handlers are sync ``def``
so FastAPI runs them in its threadpool and one slow request cannot stall the
others. A handler opts OUT of that protection simply by being written
``async def``, and nothing said so out loud: ``/ibkr/import-csv`` did the whole
IBKR statement parse and trade-log rebuild on the event loop, stalling the
portfolio pane, the health tick and the broker-status pill for the duration of
an import (council 2026-09-07, finding 12).

The check is AST-only — no imports, no app boot, no DB — so it walks every
backend domain file (the routers live in ``webapp/backend/domains/<domain>/``),
including ones that do not exist yet.
"""
import ast
from pathlib import Path

DOMAINS = Path(__file__).resolve().parents[1] / "webapp" / "backend" / "domains"
# The 21 router modules that lived flat in routers/ before the domain split; a
# scan that finds fewer files than that is looking in the wrong place.
_MIN_DOMAIN_FILES = 21

# The ONLY handlers that may be async: they return a StreamingResponse over an
# async generator that awaits an asyncio queue. There is no blocking work to
# move off the loop — awaiting IS the work — so the threadpool would buy
# nothing and would break the streaming. Anything else added to this set needs
# the same argument written next to it.
_ALLOWED_ASYNC = {
    ("portfolio/streams.py", "stream_portfolio"),
    ("portfolio/streams.py", "stream_executions"),
}

_HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}


def _is_route_decorator(node: ast.expr) -> bool:
    """Matches ``@router.post(...)`` / ``@router.get(...)`` and friends."""
    func = node.func if isinstance(node, ast.Call) else node
    return (isinstance(func, ast.Attribute)
            and func.attr in _HTTP_METHODS
            and isinstance(func.value, ast.Name)
            and func.value.id == "router")


def _async_handlers() -> list[tuple[str, str]]:
    paths = sorted(DOMAINS.rglob("*.py"))
    assert len(paths) >= _MIN_DOMAIN_FILES, f"scanned only {len(paths)} files under {DOMAINS}"
    found = []
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.AsyncFunctionDef):
                continue
            if any(_is_route_decorator(d) for d in node.decorator_list):
                found.append((path.relative_to(DOMAINS).as_posix(), node.name))
    return found


def test_no_route_handler_is_async_without_an_argument_for_it():
    unexpected = sorted(set(_async_handlers()) - _ALLOWED_ASYNC)
    assert not unexpected, (
        "these handlers run ON the event loop, so any blocking work in them "
        "stalls every other request; write them as sync def and FastAPI puts "
        f"them in the threadpool: {unexpected}"
    )


def test_the_ibkr_statement_import_is_a_threadpool_handler():
    """The named regression: a 5 MB statement parse plus a full trade-log
    rebuild, inline on the loop."""
    assert ("portfolio/router.py", "import_ibkr_csv") not in _async_handlers()


def test_the_allowlist_still_describes_real_handlers():
    """A stale exemption is how this guard would quietly stop guarding.

    ``AsyncFunctionDef`` ONLY: an allowlist entry that has since been converted
    to sync ``def`` is exactly the drift this test is named for, and matching
    plain ``FunctionDef`` too would let it pass (fix review 2026-09-07,
    finding 5)."""
    for entry in sorted(_ALLOWED_ASYNC):
        module = DOMAINS / entry[0]
        assert module.exists(), f"allowlisted module is gone: {entry[0]}"
        names = {n.name for n in ast.walk(ast.parse(module.read_text(encoding="utf-8")))
                 if isinstance(n, ast.AsyncFunctionDef)}
        assert entry[1] in names, (
            f"allowlisted handler is gone or is no longer async: {entry}")
