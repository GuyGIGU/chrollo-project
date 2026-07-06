# Hunt (security) — sample.py review

**Lane: security — untrusted input, injection, path/deserialization trust, secrets.**

## Verdict: CLEAN — no security surface.

`sample.py` is two pure, in-memory arithmetic functions (`average`, `last_or_none`) that operate
only on values passed by a trusted in-process caller. Reviewed against every attack vector in
`references/security.md` and none is present:

- **No injection (Principle 1):** no SQL, no `text()`/`execute()`, no `subprocess`/`os.system`/`eval`/
  `exec`/`pd.eval`. Nothing is built from a string.
- **No deserialization trust (Principle 1):** no `pickle`/`joblib`/`pd.read_pickle`; no artifact is loaded.
- **No boundary to validate (Principles 2 & 4):** no FastAPI route, no request/query/path param, no
  Pydantic edge. Inputs are already trusted in-process values.
- **No filesystem/path construction (Principle 5):** no ticker/date becomes a filename or `os.path.join`
  component; no path-traversal surface. No dependency imported, so no supply-chain surface either.
- **No secrets or logging (Principle 3):** no IBKR/broker config, no credentials, no `error.log`, no
  `print`/logging of anything.
- **No network/broker/mode surface (Principles 6 & 7):** no binding, no CORS, no paper/live mode.

The empty-input `ZeroDivisionError` in `average` (line 8) is a real defect but it is a **numerical-
correctness / robustness** issue, not a security one — no untrusted input, no injection, no
exploitable class. It belongs to McKinney's lane, not mine; I do not double-count it here.

Per the brief, this empty lane is the correct finding, not a skip. No finding manufactured.

**Items: 0**
