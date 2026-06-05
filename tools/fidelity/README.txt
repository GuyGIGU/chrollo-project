FIDELITY LABELS — verdict key
=============================

Open each chart in tools/fidelity/charts/, compare the engine's drawn bands to
where YOUR eye places the right-most region, then fill two columns in labels.csv.

What the chart shows:
  - grey band   = Phase A (climax / lead-in)
  - purple band = Phase B (equilibrium body)
  - blue band   = Phase D (the right-most launchpad)   <-- the one that matters
  - yellow box  = the exact LPS candidate bars (tight in time AND price)
  - pink dashed = Phase C spring (only on undercut-support setups)
  - dashed lines = R (resistance) and S (support)

phase_d_verdict  -> is the BLUE band's LEFT edge where the launchpad begins?
    ok     the blue band starts about where you'd start the right-most region
    early  the blue band starts too far LEFT (it grabbed body that isn't launchpad)
    late   the blue band starts too far RIGHT (it missed the start of the launchpad)

lps_zone_verdict -> does the YELLOW box wrap the bars you'd call the LPS?
    ok     the box sits on the right bars / the support price is holding
    high   the box sits above the real LPS
    low    the box sits below the real LPS
    wrong  not the LPS bars at all / no LPS here / unusable

Optional:
    your_phase_d_date  YYYY-MM-DD where YOU would start Phase D (for day-error stats)
    notes              anything worth remembering about this chart

Leave a row's verdict columns blank to skip it; --grade ignores unscored rows.
