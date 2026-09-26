// Chart-framing census — reproduces every figure in docs/chart_framing_2026-09.md.
//
// The operator's 2026-09-02 complaint was that the screener cards draw a wide
// choppy consolidation and a tight coil at the same width, so the choppy one
// reads as the cute tight one. This measures the claim, and the fix, on the live
// screener artifact rather than on fixtures.
//
// It imports the SHIPPED framing math (webapp/frontend/src/shared/charts/chartGeometry.js)
// so the "after" column can never drift from what the app actually draws; the
// "before" column is a self-contained transcription of the retired model, kept
// here because the code it describes was deleted. The two are checked against
// each other only through the numbers this file prints.
//
//   node tools/research/chart_framing_census.mjs                # the live US-stocks artifact
//   node tools/research/chart_framing_census.mjs path/to.json   # any screener artifact
//
// ~2 s. Read-only: it opens no database, boots nothing, and writes nothing.
// It needs an artifact — output/*.json is gitignored (EC-53), so on a fresh
// clone run a scan first, or the printed doc figures stand as the record.

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, '..', '..'); // tools/research/ -> the repo root
const GEOMETRY = pathToFileURL(
  path.join(REPO, 'webapp', 'frontend', 'src', 'shared', 'charts', 'chartGeometry.js'),
).href;
const { miniFocusLogicalRange, modalFocusLogicalRange, CHART_FRAMING } = await import(GEOMETRY);

// The real plot widths (card/modal/glance minus the right price scale), measured
// in the running app at the operator's 1536x864-effective viewport, scale 1.00.
const PLOT = { mini: 435, modal: 1050, popover: 330 };

// --- the RETIRED model, transcribed (the code itself is deleted) -------------
// CHART_FRAMING.mini/modal as shipped up to 2026-09-02, plus proportionTrimmedFrom.
const RETIRED = {
  mini: { maxVisibleBars: 130, minVisibleBars: 90, trimFloorBars: 55, minContextBars: 18, minBaseHeightFrac: 0.4 },
  modal: { contextBars: 90, minVisibleBars: 120, trimFloorBars: 80, minContextBars: 25, minBaseHeightFrac: 0.4 },
  popover: { maxVisibleBars: 85, minVisibleBars: 60, trimFloorBars: 45, minContextBars: 14, minBaseHeightFrac: 0.4 },
};

const num = (v) => {
  if (v == null || v === '') return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
};
const count = (v) => {
  const n = Number(v);
  return Number.isFinite(n) && n >= 0 ? Math.trunc(n) : null;
};

function retiredTrim(candles, from, to, boxHeight, trimFloor, minFrac) {
  const ceiling = Math.min(trimFloor, to);
  if (!(boxHeight > 0) || !(minFrac > 0) || ceiling <= from) return { from, fired: false, futile: false };
  let high = -Infinity;
  let low = Infinity;
  const widen = (i) => {
    const c = candles[i];
    if (!c) return;
    if (Number.isFinite(+c.high) && +c.high > high) high = +c.high;
    if (Number.isFinite(+c.low) && +c.low < low) low = +c.low;
  };
  for (let i = ceiling; i <= to; i += 1) widen(i);
  if (!(high > low)) return { from, fired: false, futile: false };
  // THE DEFECT: "target unreachable -> trim maximally anyway".
  if (boxHeight / (high - low) < minFrac) return { from: ceiling, fired: ceiling !== from, futile: true };
  let best = ceiling;
  for (let i = ceiling - 1; i >= from; i -= 1) {
    widen(i);
    if (boxHeight / (high - low) < minFrac) break;
    best = i;
  }
  return { from: best, fired: best !== from, futile: false };
}

function retiredMini(data, p = RETIRED.mini) {
  const candles = data.candles;
  const last = candles.length - 1;
  const baseLen = count(data.base_len);
  if (baseLen == null || baseLen <= 0) return { from: Math.max(0, last - p.maxVisibleBars), to: last, futile: false };
  const forward = count(data.forward_bars) ?? 0;
  const baseEnd = Math.max(0, last - forward);
  const baseStart = Math.max(0, baseEnd - baseLen + 1);
  const rightEdge = Math.min(last, baseEnd + Math.max(5, Math.min(9, forward + 5)));
  const desiredFrom = Math.max(0, baseStart - Math.max(40, baseLen));
  const contextFloor = Math.max(0, baseStart - p.minContextBars);
  const maxFrom = Math.min(Math.max(0, rightEdge - p.maxVisibleBars), contextFloor);
  const minFrom = Math.min(Math.max(0, rightEdge - p.minVisibleBars), contextFloor);
  let from = Math.min(Math.max(desiredFrom, maxFrom), minFrom);
  const trimFloor = Math.min(contextFloor, Math.max(0, rightEdge - Math.min(p.trimFloorBars, p.minVisibleBars)));
  const box = (num(data.R) ?? 0) - (num(data.S) ?? 0);
  const t = retiredTrim(candles, from, rightEdge, box, trimFloor, p.minBaseHeightFrac);
  return { from: t.from, to: rightEdge, fired: t.fired, futile: t.futile };
}

function retiredModal(data) {
  const p = RETIRED.modal;
  const candles = data.candles;
  const last = candles.length - 1;
  const forward = count(data.forward_bars) ?? 0;
  const baseLen = count(data.base_len) ?? 0;
  const baseEnd = last - forward;
  const from = Math.max(0, baseEnd - Math.max(baseLen + p.contextBars, p.minVisibleBars));
  const baseStart = Math.max(0, baseEnd - baseLen + 1);
  const contextFloor = Math.max(0, baseStart - p.minContextBars);
  const trimFloor = Math.min(contextFloor, Math.max(0, baseEnd - p.trimFloorBars));
  const box = (num(data.R) ?? 0) - (num(data.S) ?? 0);
  const t = retiredTrim(candles, from, last, box, trimFloor, p.minBaseHeightFrac);
  return { from: t.from, to: last, fired: t.fired, futile: t.futile };
}

// --- measurement -------------------------------------------------------------

const quant = (a, p) => {
  const s = [...a].sort((x, y) => x - y);
  return s[Math.min(s.length - 1, Math.floor(p * s.length))];
};
const pct = (x) => (x * 100).toFixed(1);

const boxSpan = (d) => {
  const last = d.candles.length - 1;
  const baseEnd = Math.max(0, last - (count(d.forward_bars) ?? 0));
  return { baseEnd, baseStart: Math.max(0, baseEnd - (count(d.base_len) ?? 0) + 1) };
};

function profile(label, rows, plot) {
  const wins = rows.map((r) => r.win);
  const shares = rows.map((r) => r.share);
  const cropped = rows.filter((r) => r.cropped);
  console.log(`\n${label}  (plot ${plot}px, n=${rows.length})`);
  console.log(`  window, trading days : min ${Math.min(...wins)} | med ${quant(wins, 0.5)} | p90 ${quant(wins, 0.9)} | max ${Math.max(...wins)}`);
  console.log(`  px per trading day   : ${(plot / Math.max(...wins)).toFixed(2)} .. ${(plot / quant(wins, 0.5)).toFixed(2)} .. ${(plot / Math.min(...wins)).toFixed(2)}`);
  console.log(`  base % of WIDTH      : med ${pct(quant(shares, 0.5))} | p90 ${pct(quant(shares, 0.9))} | >45%: ${shares.filter((s) => s > 0.45).length} | >60%: ${shares.filter((s) => s > 0.6).length}`);
  console.log(`  boxes cropped off-pane: ${cropped.length}${cropped.length ? ' -> ' + cropped.slice(0, 6).map((r) => r.ticker).join(' ') : ''}`);
  // The legibility cost of the monster zoom-out, named rather than buried: these
  // are the cards whose bars are thinner than the ~3 px/day the module treats as
  // the floor. The operator ruled the trade (2026-09-02, "simply zoom out").
  const thin = rows.filter((r) => plot / r.win < 3);
  console.log(`  cards under 3 px per trading day: ${thin.length}${thin.length ? ' -> ' + thin.map((r) => r.ticker).join(' ') : ''}`);
}

function measure(tickers, chart, range) {
  return tickers.map((ticker) => {
    const d = chart[ticker];
    const r = range(d);
    const { baseStart, baseEnd } = boxSpan(d);
    const win = r.to - r.from + 1;
    const visible = Math.max(0, Math.min(r.to, baseEnd) - Math.max(r.from, baseStart) + 1);
    return { ticker, win, share: visible / win, cropped: r.from > baseStart, futile: !!r.futile, fired: !!r.fired };
  });
}

// A longer rest drawn NARROWER than a shorter one is the operator's complaint,
// stated as a number: it is the fraction of side-by-side pairs that lie about
// which consolidation lasted longer.
function inversions(rows, chart) {
  let bad = 0;
  let pairs = 0;
  for (let i = 0; i < rows.length; i += 1) {
    for (let j = i + 1; j < rows.length; j += 1) {
      const a = count(chart[rows[i].ticker].base_len) ?? 0;
      const b = count(chart[rows[j].ticker].base_len) ?? 0;
      if (a === b) continue;
      pairs += 1;
      const wider = a > b ? rows[i].share : rows[j].share;
      const narrower = a > b ? rows[j].share : rows[i].share;
      if (wider < narrower) bad += 1;
    }
  }
  return { bad, pairs };
}

const artifact = process.argv[2] || path.join(REPO, 'output', 'screener_data.json');
if (!fs.existsSync(artifact)) {
  console.error(`no artifact at ${artifact} — run a scan first (see AGENTS.md), or pass a path.`);
  process.exit(2);
}
const payload = JSON.parse(fs.readFileSync(artifact, 'utf8'));
const chart = payload.chart_data || {};
const tickers = (payload.ordered_tickers || Object.keys(chart)).filter((t) => chart[t]?.candles?.length);

console.log(`chart-framing census — ${path.relative(REPO, artifact)} — ${tickers.length} setups`);
const lens = tickers.map((t) => chart[t].candles.length);
console.log(`daily candles carried: min ${Math.min(...lens)} | med ${quant(lens, 0.5)} | max ${Math.max(...lens)}`);

console.log('\n================ BEFORE — the retired model ================');
const beforeMini = measure(tickers, chart, retiredMini);
profile('MINI CARD @480px card', beforeMini, 435);
const fired = beforeMini.filter((r) => r.fired);
const futile = beforeMini.filter((r) => r.futile && r.fired);
console.log(`  the vertical trim fired on ${fired.length}/${beforeMini.length} cards`);
console.log(`  ... of which FUTILE (target proved unreachable, trimmed maximally anyway): ${futile.length}`);
const invBefore = inversions(beforeMini, chart);
console.log(`  ORDER INVERSION: ${invBefore.bad}/${invBefore.pairs} pairs = ${pct(invBefore.bad / invBefore.pairs)}%`);
const beforeGlance = measure(tickers, chart, (d) => retiredMini(d, RETIRED.popover));
profile('HOVER GLANCE @330px', beforeGlance, PLOT.popover);
const beforeModal = measure(tickers, chart, retiredModal);
profile('MODAL @1050px', beforeModal, PLOT.modal);
console.log(`  modal windows pinned at the 81-day floor: ${beforeModal.filter((r) => r.win === 81).length}`);
console.log(`  modal futile trims: ${beforeModal.filter((r) => r.futile && r.fired).length}`);

console.log('\n================ AFTER — the shipped model =================');
console.log(`mini  minWindow ${CHART_FRAMING.mini.minWindowBars} ceiling ${CHART_FRAMING.mini.legibilityCeilingBars} cap ${CHART_FRAMING.mini.baseWidthCap} yield ${CHART_FRAMING.mini.ceilingYieldShare}`);
console.log(`modal minWindow ${CHART_FRAMING.modal.minWindowBars} ceiling ${CHART_FRAMING.modal.legibilityCeilingBars} cap ${CHART_FRAMING.modal.baseWidthCap} yield ${CHART_FRAMING.modal.ceilingYieldShare}`);
const afterMini = measure(tickers, chart, (d) => miniFocusLogicalRange(d));
profile('MINI CARD @490px card', afterMini, PLOT.mini);
const invAfter = inversions(afterMini, chart);
console.log(`  ORDER INVERSION: ${invAfter.bad}/${invAfter.pairs} pairs = ${pct(invAfter.bad / invAfter.pairs)}%`);
profile('MODAL @1050px', measure(tickers, chart, (d) => modalFocusLogicalRange(d)), PLOT.modal);
profile('HOVER GLANCE @330px', measure(tickers, chart, (d) => miniFocusLogicalRange(d, CHART_FRAMING.popover)), PLOT.popover);

console.log('\n---- named cards (the two the operator screenshotted, plus the cap-bound case) ----');
for (const t of ['MSEX', 'NP', 'SBUX', 'TECH']) {
  const b = beforeMini.find((r) => r.ticker === t);
  const a = afterMini.find((r) => r.ticker === t);
  if (!b || !a) continue;
  console.log(`  ${t.padEnd(5)} base ${String(count(chart[t].base_len)).padStart(3)}d  |  before ${String(b.win).padStart(3)}d ${pct(b.share).padStart(5)}% of width  ->  after ${String(a.win).padStart(3)}d ${pct(a.share).padStart(5)}% of width`);
}

// --- the two Tested-DEAD levers, reproduced ---------------------------------
console.log('\n---- Tested-DEAD 1: a log price scale instead of the vertical trim ----');
const lin = [];
const log = [];
for (const t of tickers) {
  const d = chart[t];
  const r = miniFocusLogicalRange(d);
  let hi = -Infinity;
  let lo = Infinity;
  for (let i = r.from; i <= r.to; i += 1) {
    const c = d.candles[i];
    if (!c) continue;
    hi = Math.max(hi, +c.high);
    lo = Math.min(lo, +c.low);
  }
  const R = num(d.R);
  const S = num(d.S);
  if (!(hi > lo) || R == null || S == null || !(R > S) || lo <= 0 || S <= 0) continue;
  lin.push((R - S) / (hi - lo));
  log.push((Math.log(R) - Math.log(S)) / (Math.log(hi) - Math.log(lo)));
}
console.log(`  box % of visible price range — linear med ${quant(lin, 0.5).toFixed(3)} p10 ${quant(lin, 0.1).toFixed(3)}`);
console.log(`                                    log med ${quant(log, 0.5).toFixed(3)} p10 ${quant(log, 0.1).toFixed(3)}`);
console.log(`  log is BETTER on ${log.filter((v, i) => v > lin[i]).length}/${lin.length} charts`);

console.log('\n---- Tested-DEAD 2: "just match his TradingView density" (fixed px per day) ----');
for (const pxbar of [7.0, 5.0]) {
  const win = Math.round(PLOT.mini / pxbar);
  const shares = tickers.map((t) => {
    const d = chart[t];
    const last = d.candles.length - 1;
    const { baseStart, baseEnd } = boxSpan(d);
    const to = Math.min(last, baseEnd + Math.max(5, Math.min(9, (count(d.forward_bars) ?? 0) + 5)));
    const from = Math.max(0, to - win + 1);
    return (Math.min(to, baseEnd) - Math.max(from, baseStart) + 1) / (to - from + 1);
  });
  console.log(`  ${pxbar.toFixed(1)} px/day -> ${win}-day window: base % of width med ${pct(quant(shares, 0.5))} | >45%: ${shares.filter((s) => s > 0.45).length}/${shares.length} | >60%: ${shares.filter((s) => s > 0.6).length}`);
}
