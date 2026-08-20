# Cockpit Teardown — Home Command-Center

*Competitive analysis + information architecture for Chrollo's first cockpit surface.*
*Phase: pre-spec. This is the checkpoint artifact that feeds `spec-writer`.*

---

## 0. The ruler

Every pattern below is scored against **our own North Star**, not generic dashboard
taste. From `PRODUCT.md` / `DESIGN.md`:

- **"The Instrument Panel."** Calm, precise, decisive. Stared at for hours; never shouts.
- **Confident hierarchy.** Every screen commits to the one reading that matters most.
  Flat, egalitarian layouts are a *defect*.
- **Signal over chrome. Earn every element.** Dense where density informs, empty where it doesn't.
- **Honest instrument, never a salesman.** Reports; never nudges, celebrates, or inflates.
- **The three anti-references** (hard rejects): gamified retail broker (Robinhood),
  generic SaaS dashboard (hero-metric tiles, identical card grids, eyebrow kickers),
  over-design (glassmorphism, showy motion, ornamental gradients).
- **Explicitly NOT:** an autonomous trader, a brokerage, a TradingView clone.

The user: one discretionary Minervini-VCP + Qullamaggie trader reading through a Wyckoff
lens. Sits down after a daily scan. Job = **fast, trustworthy triage**, then bridge
survivors to TWS / TradingView. Increasingly wants to know *what edge the engine actually has.*

---

## 1. Current-state gap

| | Today | Implication |
|---|---|---|
| **Landing surface** | `/` redirects to `/screener` | No "orient" surface — you land mid-task, in the grid |
| **"Dashboard" route** | A **trade-journal analytics** page (equity curve + win/open/loss/wash KPI tiles + avg W/L + total P&L) | Backward-looking. Answers "how have I done", not "what's the state of my world right now" |
| **Regime** | `MarketRegimeBanner` exists, lives atop the screener | The "weather" exists but isn't the spine of an orient surface |
| **Open book** | `PortfolioStatusBar` / `usePortfolioSnapshot` / `useTradeLivePrices` / `TradeRiskAlerts` | Live P&L / R / distance-to-stop machinery exists, scattered across Portfolio |
| **Watchlist** | `ScreenerWatchlistPanel` / `useWatchlist` | Curated names exist as a screener side-panel, not a first-class status zone |
| **Fresh setups** | `ScreenerCard` / `ScreenerMiniChart` / `useScreenerData` | The triage unit exists; no "today's scan at a glance" summary |
| **Engine edge** | `core/backtest/edge_report.py` (just productized: elapsed-window MFE) | The "second brain" number exists in the backend, surfaced nowhere |

**Verdict:** the Home command-center is ~70% an **assembly + IA** problem (compose existing,
well-built components into one curated orient surface) and ~30% net-new (the Home route +
layout, a "today's scan" aggregation, an honest engine-edge tile, the composition glue).
That is the cheapest, highest-leverage shape this effort could have taken.

---

## 2. Competitive teardown

Four references, chosen because each is strong at one thing our cockpit needs:
Finviz (density), TradingView (chart-first + watchlist), Koyfin (composed dashboard),
Trade Ideas (fresh-signal stream). Verdicts: **KEEP** (steal it), **ADAPT** (steal the
idea, not the execution), **REJECT** (violates our North Star).

### 2.1 Finviz — *the density benchmark*

| Pattern | Verdict | Reasoning |
|---|---|---|
| Screener table: ~70 rows × 10+ columns, still legible | **KEEP** | Pure tabular discipline — exactly our "Tabular Rule." Proof that density ≠ clutter when columns align |
| Home overview = single-pane orient (futures bar, sentiment, gainers/losers, signals, news) | **ADAPT** | The *shape* is right (one screen = whole-market state). But it's a firehose of generic data. Ours is **curated**: regime + *our* scan + *my* watchlist + *my* book |
| Sector/group **heatmap** (treemap) as instant breadth read | **ADAPT** | The instant-breadth idea is gold. Adapt to a small **tier/sector breadth mini-viz of OUR scan**, not the whole market |
| Visual style: cramped, ad-heavy, blue-link soup, everything equal weight | **REJECT** | The textbook violation of "Confident hierarchy" + "Signal over chrome." This is the *anti-* of our brand |
| Tiny dense charts as primary | **REJECT** | Our `ScreenerMiniChart` already does this better and on-brand |

### 2.2 TradingView — *chart-first + the watchlist interaction*

| Pattern | Verdict | Reasoning |
|---|---|---|
| Watchlist → focus-chart pairing (click a name, the chart follows) | **KEEP (adapted)** | The core interaction for a watchlist zone. But we *bridge out* for deep charting, so ours is a quick **peek**, not a workspace |
| Symbol "overview" mini-summary (price, change, key levels, sparkline) | **KEEP** | A compact per-name status row is exactly what the watchlist + book zones need |
| Calm dark theme, restrained chrome | **KEEP** | Closest big-app aesthetic to ours; validates the dark-slate direction |
| Right-hand **details panel** (selection drives a detail pane) | **ADAPT** | Useful master/detail pattern for "click a setup → see why it ranked" without leaving Home |
| Heavy charting toolbar / drawing tools | **REJECT** | We are "not a TradingView clone." We bridge to TV for this on purpose |
| Social "ideas" feed | **REJECT** | Noise; violates "honest instrument, never a salesman" |

### 2.3 Koyfin — *the composed dashboard (closest to our taste)*

| Pattern | Verdict | Reasoning |
|---|---|---|
| "MyDashboard": composed grid of watchlist + market overview + movers tiles | **ADAPT** | The composition model is exactly a command-center. We **hard-curate the regions** rather than ship a tile-config builder |
| Clean, calm, data-dense aesthetic | **KEEP** | This is the reference whose *restraint* matches our brand best |
| Full user customization of tiles | **REJECT (for v1)** | Single user. Building a dashboard-builder violates "Earn every element." Curate, don't configure |
| Broad asset classes (FX, macro, fundamentals everywhere) | **REJECT** | Not our job; dilutes the equities/structure focus |

### 2.4 Trade Ideas — *the fresh-signal stream*

| Pattern | Verdict | Reasoning |
|---|---|---|
| Prominent **fresh-signal** surfacing (new alerts up top) | **KEEP (adapted)** | Our engine's fresh scan results are our version of this — the "new ideas" pulse zone |
| Chronological alert/event stream ("what just happened") | **ADAPT (defer)** | Right idea for the future alerts layer. Leave a *slot* in the IA, build later |
| "Holly AI" auto-picks / OddsMaker | **REJECT** | Gambling-adjacent, auto-trade framing. Direct violation of "honest instrument" + "not an autonomous trader" |

**Honorable mentions:** Thinkorswim — reject the pro-cluttered aesthetic (over-dense, no
hierarchy). Atlas / Stock Unlock — **keep** the calm fundamentals-card restraint as a
reference for any future fundamentals surface.

---

## 3. Synthesis — the Home command-center IA

**One sentence:** a *curated orient surface* that answers "what is the state of my world
right now?" the moment the trader sits down — regime weather, today's scan pulse, my
watchlist status, my open book — with an honest engine-edge footnote. **Not** a
configurable dashboard, **not** a market firehose, **not** a charting workspace.

### Layout (confident hierarchy, top → down)

```
┌─────────────────────────────────────────────────────────────────────┐
│  REGIME STRIP  (full width)                                          │  ← the weather, FIRST
│  Risk-on/off · trend · breadth · "should I be taking setups today?"  │     (Qullamaggie/Minervini: don't fight the tape)
├──────────────────────┬──────────────────────┬───────────────────────┤
│  FRESH SETUPS         │  WATCHLIST            │  OPEN BOOK            │
│  Last scan: when,     │  My curated names:    │  Live positions:     │
│  tier counts (S/A/B/C)│  price, %chg, near-   │  P&L, R, dist-to-stop│
│  + top N cards        │  trigger flags        │  + risk alerts       │
│  → "Open the grid"    │  → peek / bridge out  │  → "Open portfolio"  │
├──────────────────────┴──────────────────────┴───────────────────────┤
│  ENGINE EDGE PULSE  (honest footnote, secondary)                     │  ← the "second brain"
│  Measured elapsed-window MFE / win-rate by tier · unbiased · n=…      │     reports, never flatters
└─────────────────────────────────────────────────────────────────────┘
```

The three middle zones map 1:1 to the trader's three live questions: *new ideas? · my
shortlist? · my risk?* Regime is the spine above them because in this trading style it
gates whether any of the rest matters today.

### Reuse map (what we already have)

| Zone | Reuse | Net-new |
|---|---|---|
| Regime strip | `MarketRegimeBanner`, `MarketRegimeDetailModal`, `marketRegimeFormat.js` | Possibly a denser "strip" variant for the cockpit header |
| Fresh setups | `ScreenerCard`, `ScreenerMiniChart`, `useScreenerData` | A **"today's scan summary"** aggregation (count by tier, scan timestamp, top-N selection) |
| Watchlist | `ScreenerWatchlistPanel`, `useWatchlist`, `useTradeLivePrices` (for live %) | A compact **status-row** variant + "near trigger" flagging |
| Open book | `PortfolioStatusBar`, `PortfolioSummary`, `usePortfolioSnapshot`, `useTradeLivePrices`, `TradeRiskAlerts` | A condensed positions-summary card |
| Edge pulse | backend `core/backtest/edge_report.py` | A small read-only tile + (likely) a backend endpoint to serve the headline edge |
| Performance | `EquityCurve` (currently on Dashboard) | Decide: keep on Journal, or a sparkline echo on Home |

### What we deliberately do NOT build (anti-references applied)

- ❌ No hero-metric tile (big number + gradient) for P&L — that's the SaaS cliché *and* the
  gamified-broker dopamine move at once.
- ❌ No celebratory color on wins. P&L reports in the status palette, calm, never oversized.
- ❌ No identical card grid of generic market widgets. Each zone earns its place; empty where
  it doesn't inform (e.g., no positions → a quiet "no open trades", not a filler tile).
- ❌ No tile-configuration builder. Curated, not configurable (v1).
- ❌ No drawing/charting workspace. Charts are peeks; deep work bridges to TV/TWS.
- ❌ No eyebrow kickers above every zone; zone identity via one confident label each.

---

## 4. Open questions for the spec

These are the decisions `spec-writer` needs settled (recommendations in **bold**):

1. **Landing & nav:** Does Home become the new index (replacing the `/screener` redirect),
   with Screener one click away? **Recommend: yes — Home is the index.**
2. **The "Dashboard" name collision:** the current trade-journal page is called "Dashboard."
   Rename it (e.g., **"Journal"** or "Performance") so "Home" owns the orient slot? **Recommend: rename to Journal.**
3. **Fresh-setups depth:** inline top-N cards, or tier-count summary + "open grid" link only?
   **Recommend: tier-count summary + top 3–4 cards, link for the rest.**
4. **Engine-edge pulse in v1?** It's the "second brain" hook but needs a backend endpoint.
   **Recommend: include a minimal read-only tile; full edge explorer is a later phase.**
5. **Watchlist click:** chart peek (modal) vs. bridge-out to TWS/TV only? **Recommend: peek
   modal (reuse `ScreenerModal`/`TimeframeMainChart`), with a bridge-out action.**
6. **Live cadence:** does Home poll live prices (positions/watchlist) on an interval like
   Portfolio does? **Recommend: yes, reuse the existing poll cadence; pause when tab hidden.**
7. **Alerts slot:** leave a designed-but-empty slot for the future event stream, or omit
   entirely for now? **Recommend: omit from v1 layout; note as a future zone.**

---

## 5. Next step

Checkpoint here. On sign-off, `spec-writer` (Feature tier) turns Section 3 + the resolved
Section 4 answers into `specs/home-command-center.md` — job stories, Gherkin ACs, three-tier
boundaries — then `council-plan` → `council-implement` + `impeccable` craft.
