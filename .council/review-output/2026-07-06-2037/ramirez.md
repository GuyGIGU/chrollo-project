# Ramírez — backend/async lane · Yahoo 429 backoff-jitter review

Lane: concurrency/runtime correctness — `_cooldown_until`/token-bucket thread-safety under
their locks, the module-level-vs-lazy `settings` asymmetry, operational-vs-programmer error
discipline. NOT tests, NOT the float formula's numerics, NOT pure structure.

Verdict: the shared-state locking is correct and the change is safe at THIS scale (one scan
subprocess, a bounded download ThreadPoolExecutor). The findings below are P2/P3 — no P1. The
core token-bucket/cooldown mutual exclusion is sound; I found no data race on `_cooldown_until`.

---

FINDING: Cooldown-exit jitter does not re-check a cooldown that was re-armed while it slept
File: core/pipeline/rate_limit.py:99-111
Principle: Programmer errors are assertion failures / operational-vs-programmer error discipline (Principle 1)
Severity: P2
What's wrong: `_respect_cooldown` drains the shared window in the `while` loop, then — once
`remaining <= 0` — drops out of the loop and sleeps a random 0..jitter seconds OUTSIDE any
re-check of `_cooldown_until`. During that unguarded sleep another worker can call
`note_rate_limit()` (a fresh 429 arrives on a batch that raced ahead), pushing `_cooldown_until`
back into the future. The jittering worker has already left the loop, so it wakes from its
stagger sleep and proceeds straight to `yahoo_rate_limiter().acquire()` — it does NOT observe the
newly-armed cooldown. The stagger sleep is meant to keep workers off Yahoo right after a cooldown;
here it becomes the exact window in which a worker ignores a just-armed one.
Consequence: on a sustained-429 day (the failure this whole change exists to fix) a subset of
workers slip past a live cooldown and hit Yahoo during the backoff, which is what re-trips the
next 429 — the thundering-herd guard partially defeats itself under the load it targets.
Fix: make the cooldown-exit stagger part of the guarded loop rather than a tail sleep — after the
random stagger, re-enter the same check of `_cooldown_until` (under `_cooldown_lock`) and only
return when it is still clear, so a cooldown re-armed during the stagger is honoured. Keep the
stagger a one-time thing per drain so it can't livelock. This is a `rate_limit.py`-only change.

---

FINDING: Settings-source asymmetry — `_retry_wait_seconds` and `_respect_cooldown` disagree on
which `settings` object they read for the same 429 event
File: core/pipeline/downloads.py:14,104 vs core/pipeline/rate_limit.py:108-109
Principle: Configuration & dependency lifecycle — the config-vs-cwd trap (Principle 5)
Severity: P3
What's wrong: `downloads.py` binds `settings` once at module import (line 14, `from config import
settings`), while `rate_limit.py` re-imports `from config import settings` lazily inside each
function (the AP-3 pattern I am NOT flagging as wrong). The consequence I AM flagging is the
asymmetry it creates for one logical operation: on a 429, `_retry_wait_seconds` reads
`YAHOO_RATE_LIMIT_BACKOFF_SECONDS` off `downloads.py`'s import-time-bound `settings` to size the
wait it hands to `note_rate_limit()`, while the paired `YAHOO_COOLDOWN_JITTER_SECONDS` /
`YAHOO_BACKOFF_JITTER` are read off a freshly-imported module elsewhere. In normal operation both
resolve to the same singleton, so this is latency-free today. But it means the two halves of the
backoff can be sourced from two different `settings` module objects if anything ever reloads or
monkeypatches config on only one side — the reason AP-3 exists is precisely that these two import
styles can resolve to DIFFERENT modules under the backend cwd. Nothing here is broken; the
asymmetry is a documented hazard sitting one refactor away from a silent split.
Consequence: no live defect. Latent: a future config-reload or a test that patches `config.settings`
on one path patches only half the 429 backoff, and the mismatch is invisible (no error) — a
plausible-wrong-timing, not a crash.
Fix: not a code change to force now — record the asymmetry as a known/accepted seam (it is the AP-3
tradeoff) OR, if a single source is wanted, have `_retry_wait_seconds` read the backoff constant
through the same lazy accessor the cooldown code uses. Documentation-level; do not module-hoist
`rate_limit.py` (that would reintroduce the boot crash AP-3 guards).

---

FINDING: `note_rate_limit` receives the un-jittered wait but the retry `time.sleep` uses the
jittered one — the two clocks can disagree by design, worth an explicit invariant note
File: core/pipeline/downloads.py:105-106,217-219 vs core/pipeline/rate_limit.py:114-120
Principle: Operational-vs-programmer error discipline / lifecycle transparency (Principle 1)
Severity: P3
What's wrong: `_retry_wait_seconds` arms the shared cooldown with the FULL un-jittered wait
(line 105, correct — the shared window must be the conservative bound) but returns the JITTERED
(shorter, in `[wait*(1-j), wait]`) value that the caller then `time.sleep`s on before its own
retry. So a worker's local retry-sleep can end BEFORE the shared cooldown it just armed expires;
that worker then calls `throttle()` → `_respect_cooldown()` and is correctly re-parked by the
shared window. The behaviour is correct, but it is non-obvious that the local sleep is
deliberately allowed to under-run the shared window, relying on `_respect_cooldown` as the real
gate. There is no comment at the call site stating this ordering invariant, and a future edit that
"optimizes away" the second `throttle`/cooldown check (thinking the local sleep already covered it)
would let workers back onto Yahoo early.
Consequence: no defect now; the shared cooldown is the backstop. Risk is a future well-meaning
edit removing the redundant-looking cooldown wait and reintroducing lockstep bursts.
Fix: add a one-line invariant comment at `_retry_wait_seconds` / the retry sleep site stating that
the local jittered sleep may under-run the shared cooldown and that `_respect_cooldown()` is the
authoritative gate — so the redundancy reads as intentional, not removable. Comment-only, in
`downloads.py`.

---

Out-of-lane, logged not dispatched (belongs to other seats — noted for the lead, not my finding):
the retry loop in `downloads.py` still uses `print()` (lines 218/227/230) rather than a
`chrollo.*` logger; that is pre-existing code untouched by the jitter change and is a
logging/structure concern (Principle 7 / Fowler), not a concurrency-correctness issue in this diff.
