```

========================================================================
  CHROLLO ARCHIVE ANALYSIS
========================================================================
DB: C:\Users\User\Documents\Projects\Chrollo Project\webapp\backend\trading_journal.db
Filtered to source = 'screener'

========================================================================
  1. SAMPLE COMPOSITION & BIAS DETECTION
========================================================================
Total rows: 2122
By source:     {'screener': 2122}
By tier:       {'S': 1560, 'A': 481, 'B': 78, 'C': 3}
By setup_type: {'LPS': 2000, 'REBOUND': 122}
Date range:    2026-05-31 -> 2026-06-22
With fwd_return_20d: 0 / 2122

-- Validity verdict ----------------------------------------------------
OK  Sample looks adequate for outcome + correlation analysis.

-- Data-quality flags --------------------------------------------------
!  9 setup(s) with base_length > 250 bars (~1yr+): CACC(325), MSCI(429), MSCI(433), BMRN(296), MSCI(433), BMRN(296), CWT(274), CWT(276), CWT(276)
   Almost certainly anchor mis-detection picking an over-long window.

========================================================================
  2. WINNER STRUCTURAL FINGERPRINT
========================================================================
The structural profile of setups in the archive. On seed/winners data this
is the 'what a clean tight setup looks like' template to bias toward.

-- All setups ----------------------------------------------------------
feature                n    median       q25       q75       min       max
--------------------------------------------------------------------------
box_width           2122      0.10      0.06      0.15      0.01      0.25
base_length         2122     32.00     24.00     45.00     11.00    433.00
touches             2122     16.00     12.00     23.00      4.00    114.00
r_touches           2122      8.00      5.00     12.00      2.00     61.00
s_touches           2122      8.00      5.00     12.00      2.00     70.00
atr_ratio           2122      1.03      0.96      1.12      0.24      2.01
lps_length          2122      3.00      2.00      4.00      2.00      7.00
breach_days         2122      2.00      1.00      5.00      0.00     64.00
vol_contraction     2122      0.35      0.24      0.52      0.15      1.00
tightness_ratio     2122      0.53      0.41      0.66      0.09      1.18
lps_descent_frac    2122      1.00      0.67      1.00      0.00      1.00
r_touch_vol_z       2122      0.04     -0.16      0.27     -1.08      2.21
s_touch_vol_z       2122      0.10     -0.10      0.38     -1.34      3.00
dist_52w_high_pct   2122     -0.08     -0.12     -0.05     -0.62     -0.01
excess_return_6m    2122      0.05     -0.03      0.19     -0.28      3.67
rs_vs_sector_pct    1758      0.01     -0.02      0.05     -0.39      0.25
breadth_pct         2122      0.54      0.52      0.55      0.47      0.58
bars_since_bc       2122     92.50     42.00    463.00     14.00    480.00
descent_length      2122     16.00      8.00    427.00      1.00    464.00
inner_reaction_pct     4      0.08      0.06      0.09      0.06      0.10
inner_reaction_bars    4      5.00      4.00      6.25      4.00      7.00
contraction_count   2122      5.00      4.00      7.00      1.00     43.00
contraction_quality 2122      0.73      0.58      0.82      0.24      1.00
final_contraction_depth2122      0.05      0.03      0.08      0.00      0.26
contraction_vol_trend 792      0.69      0.47      0.82      0.00      1.00
base_median_spread_atr1425      0.85      0.79      0.92      0.41      1.11
base_p80_spread_atr 1425      1.15      1.07      1.22      0.69      1.62
base_median_spread_pct_box1425      0.30      0.23      0.38      0.09      0.86
base_tight_bar_pct  1425      0.67      0.60      0.74      0.37      0.94
support_slope_atr   2117      0.02     -0.01      0.06     -0.51      0.39
ascending_support_quality2122      0.34      0.20      0.60      0.00      1.00
eq_r_touches         737     12.00      8.00     17.00      3.00     64.00
eq_s_touches         737      9.00      6.00     14.00      3.00     70.00
eq_r_touch_thirds    737      3.00      2.00      3.00      1.00      3.00
eq_s_touch_thirds    737      3.00      2.00      3.00      1.00      3.00
eq_lower_dwell       737      0.42      0.32      0.53      0.12      0.92
eq_mid_dwell         737      0.59      0.42      0.72      0.14      1.00
eq_upper_dwell       737      0.56      0.42      0.67      0.11      1.00
eq_coverage          737      1.00      1.00      1.00      0.83      1.00
trav_n_full_traversals 627      5.00      3.00      6.00      1.00     19.00
trav_n_swings        627     15.00     10.00     26.00      5.00    141.00
trav_top_dead_space  627      0.00      0.00      0.01      0.00      0.21
trav_bottom_dead_space 627      0.00      0.00      0.09      0.00      0.57
trav_rail_reaches_high 627      6.00      4.00      9.00      2.00     34.00
trav_rail_reaches_low 627      4.00      3.00      7.00      1.00     45.00
trav_max_swing_frac  627      1.32      1.09      1.66      0.80      5.93
trav_last_support_frac 241      0.79      0.62      0.90      0.26      1.00
trav_coil_floor_pos  205      0.32      0.23      0.45      0.12      0.76
adr_pct             2122      2.92      2.12      3.92      0.36     12.89
bin_a_bars           983      5.00      3.00      9.00      1.00    455.00
bin_a_range_pct      983      0.08      0.05      0.13      0.01      9.45
bin_a_volume_ratio   983      1.02      0.84      1.25      0.05      5.49
bin_b_range_pct      985      0.17      0.12      0.24      0.02      0.85
bin_b_volume_ratio   985      0.99      0.93      1.05      0.02      1.59
bin_b_cog_end        737      0.70      0.47      0.85      0.00      1.00
bin_b_cog_crossings  737      2.00      1.00      3.00      0.00      6.00
bin_b_cog_rng        737      0.62      0.52      0.73      0.12      0.99
bin_b_cog_corr       737      0.28     -0.06      0.52     -0.85      0.90
bin_c_present        711      0.00      0.00      1.00      0.00      1.00
bin_c_undercut_atr   194      0.67      0.44      0.88      0.00      2.05
bin_c_recovery_bars  194      1.00      0.00      1.00      0.00      5.00
bin_c_time_loc       194      0.70      0.57      0.82      0.50      1.00
bin_c_spring_vol_z   194     -0.04     -0.29      0.71     -1.19      5.17
bin_d_bars           985     12.00      8.00     22.00      2.00    143.00
bin_d_range_pct      985      0.11      0.07      0.17      0.01      0.84
bin_d_volume_ratio   985      0.90      0.76      1.01      0.01      1.70
bin_d_support_slope_atr 423      0.07      0.02      0.14     -0.41      0.80
bin_d_higher_low_frac 656      0.43      0.00      0.67      0.00      1.00
bin_d_ascending_support_quality 656      0.31      0.00      0.80      0.00      1.00
bin_lps_bars         985      3.00      2.00      3.00      2.00      7.00
lps_position_in_box  985      0.61      0.37      0.79     -0.52      1.48
bin_d_vs_b_range_ratio 985      0.76      0.50      0.97      0.11      1.00
bin_d_vs_b_volume_ratio 985      0.91      0.79      1.00      0.40      1.68
bin_d_vs_b_support_quality_delta 423      0.12     -0.13      0.41     -0.80      0.90
lps_stretch_atr      985     -1.04     -1.69     -0.54     -5.05      1.44
lps_stretch_box      985     -0.39     -0.63     -0.21     -1.52      0.48
stage2_ma_stack_pass 985      1.00      0.00      1.00      0.00      1.00
stage2_ma200_slope_1m_pct 983      2.32      0.94      4.38     -3.61     41.51
stage2_52w_low_pct   985      0.49      0.30      0.90      0.05     12.71
stage2_trend_pass_count 985      7.00      6.00      7.00      3.00      7.00
stage2_trend_pass    985      1.00      0.00      1.00      0.00      1.00
htf_w_stage2         237      1.00      1.00      1.00      0.00      1.00
htf_w_in_consol      237      0.00      0.00      1.00      0.00      1.00
htf_w_reaccum        237      0.00      0.00      0.00      0.00      1.00
htf_w_daily_nested    65      0.00      0.00      1.00      0.00      1.00
htf_w_box_width       65      0.12      0.08      0.16      0.03      0.17
htf_m_stage2         237      1.00      1.00      1.00      0.00      1.00
htf_m_in_consol      237      0.00      0.00      0.00      0.00      1.00
htf_m_reaccum        237      0.00      0.00      0.00      0.00      1.00
htf_m_daily_nested     4      0.00      0.00      0.00      0.00      0.00
htf_m_box_width        4      0.13      0.12      0.14      0.12      0.14

-- Horizontal axis - time structure (duration, rail tests, traversal) --
feature                n    median       q25       q75       min       max
--------------------------------------------------------------------------
base_length         2122     32.00     24.00     45.00     11.00    433.00
r_touches           2122      8.00      5.00     12.00      2.00     61.00
s_touches           2122      8.00      5.00     12.00      2.00     70.00
eq_r_touches         737     12.00      8.00     17.00      3.00     64.00
eq_s_touches         737      9.00      6.00     14.00      3.00     70.00
eq_r_touch_thirds    737      3.00      2.00      3.00      1.00      3.00
eq_s_touch_thirds    737      3.00      2.00      3.00      1.00      3.00
breach_days         2122      2.00      1.00      5.00      0.00     64.00
lps_length          2122      3.00      2.00      4.00      2.00      7.00
bin_lps_bars         985      3.00      2.00      3.00      2.00      7.00
lps_position_in_box  985      0.61      0.37      0.79     -0.52      1.48
trav_n_full_traversals 627      5.00      3.00      6.00      1.00     19.00
trav_n_swings        627     15.00     10.00     26.00      5.00    141.00
trav_rail_reaches_high 627      6.00      4.00      9.00      2.00     34.00
trav_rail_reaches_low 627      4.00      3.00      7.00      1.00     45.00
trav_last_support_frac 241      0.79      0.62      0.90      0.26      1.00
bin_c_time_loc       194      0.70      0.57      0.82      0.50      1.00
bin_d_bars           985     12.00      8.00     22.00      2.00    143.00

-- Vertical axis - price magnitude (rails/height, undercut, thrust) ----
feature                n    median       q25       q75       min       max
--------------------------------------------------------------------------
box_width           2122      0.10      0.06      0.15      0.01      0.25
tightness_ratio     2122      0.53      0.41      0.66      0.09      1.18
atr_ratio           2122      1.03      0.96      1.12      0.24      2.01
lps_descent_frac    2122      1.00      0.67      1.00      0.00      1.00
bin_c_undercut_atr   194      0.67      0.44      0.88      0.00      2.05
lps_stretch_atr      985     -1.04     -1.69     -0.54     -5.05      1.44
lps_stretch_box      985     -0.39     -0.63     -0.21     -1.52      0.48
trav_top_dead_space  627      0.00      0.00      0.01      0.00      0.21
trav_bottom_dead_space 627      0.00      0.00      0.09      0.00      0.57
trav_max_swing_frac  627      1.32      1.09      1.66      0.80      5.93
trav_coil_floor_pos  205      0.32      0.23      0.45      0.12      0.76
final_contraction_depth2122      0.05      0.03      0.08      0.00      0.26
bin_d_vs_b_range_ratio 985      0.76      0.50      0.97      0.11      1.00

-- setup_type = LPS  (n=2000) ------------------------------------------
feature                n    median       q25       q75       min       max
--------------------------------------------------------------------------
box_width           2000      0.10      0.06      0.15      0.01      0.25
atr_ratio           2000      1.03      0.95      1.12      0.24      1.69
tightness_ratio     2000      0.53      0.42      0.66      0.09      1.18
lps_descent_frac    2000      1.00      0.67      1.00      0.00      1.00
contraction_quality 2000      0.72      0.58      0.82      0.24      1.00
base_median_spread_atr1346      0.85      0.79      0.91      0.41      1.11
base_tight_bar_pct  1346      0.68      0.60      0.74      0.37      0.94
bin_d_vs_b_range_ratio 936      0.77      0.51      0.97      0.11      1.00
bin_d_ascending_support_quality 623      0.34      0.00      0.80      0.00      1.00
trav_n_full_traversals 597      5.00      3.00      6.00      1.00     19.00
trav_top_dead_space  597      0.00      0.00      0.00      0.00      0.21
base_length         2000     33.00     25.00     46.00     11.00    433.00
touches             2000     16.00     12.00     23.00      4.00    114.00
vol_contraction     2000      0.35      0.24      0.52      0.15      1.00
dist_52w_high_pct   2000     -0.07     -0.12     -0.04     -0.62     -0.01

-- setup_type = REBOUND  (n=122) ---------------------------------------
feature                n    median       q25       q75       min       max
--------------------------------------------------------------------------
box_width            122      0.09      0.06      0.12      0.02      0.21
atr_ratio            122      1.07      1.00      1.19      0.76      2.01
tightness_ratio      122      0.51      0.40      0.63      0.26      0.92
lps_descent_frac     122      0.87      0.67      1.00      0.50      1.00
contraction_quality  122      0.73      0.61      0.84      0.34      0.96
base_median_spread_atr  79      0.89      0.81      0.93      0.56      1.03
base_tight_bar_pct    79      0.67      0.59      0.72      0.43      0.94
bin_d_vs_b_range_ratio  49      0.57      0.38      0.93      0.23      1.00
bin_d_ascending_support_quality  33      0.00      0.00      0.00      0.00      0.41
trav_n_full_traversals  30      4.00      3.00      5.00      2.00     11.00
trav_top_dead_space   30      0.01      0.00      0.05      0.00      0.10
base_length          122     22.00     19.00     26.00     11.00     68.00
touches              122     14.00     11.00     18.00      6.00     29.00
vol_contraction      122      0.35      0.23      0.51      0.16      0.90
dist_52w_high_pct    122     -0.10     -0.14     -0.08     -0.57     -0.01

-- tier = S  (n=1560) --------------------------------------------------
feature                n    median       q25       q75       min       max
--------------------------------------------------------------------------
box_width           1560      0.09      0.06      0.14      0.01      0.25
atr_ratio           1560      1.03      0.96      1.13      0.24      2.01
tightness_ratio     1560      0.50      0.39      0.60      0.09      1.17
lps_descent_frac    1560      1.00      0.67      1.00      0.00      1.00
contraction_quality 1560      0.73      0.60      0.82      0.24      1.00
base_median_spread_atr 989      0.85      0.78      0.91      0.41      1.11
base_tight_bar_pct   989      0.68      0.61      0.74      0.37      0.94
bin_d_vs_b_range_ratio 578      0.77      0.51      0.97      0.11      1.00
bin_d_ascending_support_quality 327      0.20      0.00      0.80      0.00      1.00
trav_n_full_traversals 310      5.00      4.00      7.00      1.00     14.00
trav_top_dead_space  310      0.00      0.00      0.00      0.00      0.19
base_length         1560     31.00     24.00     42.00     11.00    433.00
touches             1560     16.00     12.00     23.00      4.00    106.00
score               1560    124.20    118.00    133.20    110.00    160.60

-- tier = A  (n=481) ---------------------------------------------------
feature                n    median       q25       q75       min       max
--------------------------------------------------------------------------
box_width            481      0.11      0.07      0.16      0.02      0.25
atr_ratio            481      1.04      0.95      1.11      0.79      1.68
tightness_ratio      481      0.66      0.51      0.76      0.20      1.18
lps_descent_frac     481      1.00      0.67      1.00      0.00      1.00
contraction_quality  481      0.71      0.56      0.82      0.24      1.00
base_median_spread_atr 365      0.85      0.80      0.91      0.64      1.05
base_tight_bar_pct   365      0.68      0.60      0.74      0.45      0.90
bin_d_vs_b_range_ratio 339      0.77      0.45      0.96      0.13      1.00
bin_d_ascending_support_quality 272      0.38      0.00      0.81      0.00      1.00
trav_n_full_traversals 260      4.00      3.00      6.00      2.00     19.00
trav_top_dead_space  260      0.00      0.00      0.00      0.00      0.20
base_length          481     33.00     24.00     54.00     11.00    296.00
touches              481     16.00     11.00     23.00      4.00    114.00
score                481    105.70    100.90    108.80     95.20    141.50

-- tier = B  (n=78) ----------------------------------------------------
feature                n    median       q25       q75       min       max
--------------------------------------------------------------------------
box_width             78      0.12      0.09      0.15      0.03      0.24
atr_ratio             78      1.01      0.94      1.10      0.78      1.43
tightness_ratio       78      0.80      0.71      0.92      0.34      1.14
lps_descent_frac      78      1.00      0.67      1.00      0.33      1.00
contraction_quality   78      0.68      0.52      0.79      0.25      0.93
base_median_spread_atr  68      0.90      0.80      0.97      0.67      1.02
base_tight_bar_pct    68      0.61      0.55      0.71      0.44      0.88
bin_d_vs_b_range_ratio  65      0.71      0.54      0.97      0.16      1.00
bin_d_ascending_support_quality  54      0.31      0.00      0.76      0.00      1.00
trav_n_full_traversals  54      3.00      2.00      5.00      2.00     19.00
trav_top_dead_space   54      0.00      0.00      0.04      0.00      0.21
base_length           78     28.50     19.00     60.00     13.00    276.00
touches               78     14.00     10.25     21.00      5.00     97.00
score                 78     90.40     86.72     91.97     75.00     94.90

-- tier = C  (n=3) -----------------------------------------------------
feature                n    median       q25       q75       min       max
--------------------------------------------------------------------------
box_width              3      0.17      0.12      0.17      0.06      0.17
atr_ratio              3      0.97      0.97      1.03      0.97      1.08
tightness_ratio        3      1.06      0.99      1.06      0.92      1.06
lps_descent_frac       3      0.19      0.19      0.50      0.19      0.80
contraction_quality    3      0.55      0.55      0.64      0.55      0.73
base_median_spread_atr   3      0.95      0.95      0.96      0.95      0.97
base_tight_bar_pct     3      0.58      0.58      0.59      0.58      0.60
bin_d_vs_b_range_ratio   3      1.00      0.74      1.00      0.48      1.00
bin_d_ascending_support_quality   3      0.40      0.20      0.40      0.00      0.40
trav_n_full_traversals   3      3.00      3.00      3.00      3.00      3.00
trav_top_dead_space    3      0.17      0.13      0.17      0.10      0.17
base_length            3     97.00     56.00     97.00     15.00     97.00
touches                3     19.00     15.00     19.00     11.00     19.00
score                  3     70.20     70.05     72.45     69.90     74.70

========================================================================
  3. SEGMENTED PERFORMANCE
========================================================================

-- By tier -------------------------------------------------------------
tier               n   med20d   avg20d   med60d   win%  trig%   avgR   expR
----------------------------------------------------------------------------
S               1560        -        -        -      - +84.9%      -      -
A                481        -        -        -      - +72.1%      -      -
B                 78        -        -        -      - +74.4%      -      -
C                  3        -        -        -      -      -      -      -

-- By setup_type -------------------------------------------------------
setup_type         n   med20d   avg20d   med60d   win%  trig%   avgR   expR
----------------------------------------------------------------------------
LPS             2000        -        -        -      - +82.6%      -      -
REBOUND          122        -        -        -      - +76.0%      -      -

-- By zone -------------------------------------------------------------
zone               n   med20d   avg20d   med60d   win%  trig%   avgR   expR
----------------------------------------------------------------------------
INSIDE          1838        -        -        -      - +83.3%      -      -
OVERSHOOT_R      162        -        -        -      - +74.4%      -      -
UNDERCUT_S       122        -        -        -      - +76.0%      -      -

-- By inner_exists(0/1) ------------------------------------------------
inner_exists(0/1)   n   med20d   avg20d   med60d   win%  trig%   avgR   expR
----------------------------------------------------------------------------
0.0             1954        -        -        -      - +83.1%      -      -
1.0              168        -        -        -      - +72.3%      -      -

-- By lps_in_inner(0/1) ------------------------------------------------
lps_in_inner(0/1)   n   med20d   avg20d   med60d   win%  trig%   avgR   expR
----------------------------------------------------------------------------
0.0              755        -        -        -      - +60.4%      -      -
1.0               51        -        -        -      - +64.7%      -      -

-- By inner_source -----------------------------------------------------
inner_source       n   med20d   avg20d   med60d   win%  trig%   avgR   expR
----------------------------------------------------------------------------
inner_climax       4        -        -        -      -  +0.0%      -      -
midpoint          62        -        -        -      - +45.2%      -      -

-- By box_width --------------------------------------------------------
box_width          n   med20d   avg20d   med60d   win%  trig%   avgR   expR
----------------------------------------------------------------------------
low              708        -        -        -      - +83.5%      -      -
mid              708        -        -        -      - +78.8%      -      -
high             706        -        -        -      - +84.1%      -      -

-- By breadth ----------------------------------------------------------
breadth            n   med20d   avg20d   med60d   win%  trig%   avgR   expR
----------------------------------------------------------------------------
low              846        -        -        -      - +88.2%      -      -
mid              714        -        -        -      - +73.7%      -      -
high             562        -        -        -      - +87.5%      -      -

========================================================================
  4. PREDICTOR CORRELATIONS vs FORWARD OUTCOMES
========================================================================

========================================================================
  5. PRIME-DIRECTIVE TEST - IS TIGHTNESS PREDICTIVE?
========================================================================
The engine's core thesis: tighter, cleaner structure -> better outcomes.
This isolates the tightness features and tests that claim directly.

========================================================================
  6. SIGNAL EDGE & SUBTRACTION CANDIDATES (Stage 1)
========================================================================
Each scoring sub-score is meant to REWARD a setup. This ranks them by
rank-association with realized outcome and flags the ones that don't
earn their points: HARMFUL (negative) or INERT (near-zero). These are
subtraction CANDIDATES only — re-weighting is a separate guarded step.

-- Win quality (durable vs cash-grab) ----------------------------------
  durable wins: 241   cash-grab wins: 14 (round-trip to stop within 5 bars of target)
  median bars target->stop among round-trips: 1.00

Primary outcome: durable_win  (n=466, minority class=225, noise floor |r| < 0.15)

sub-score                    n   rank_r  verdict
--------------------------------------------------------
score_rs_bonus             466    -0.23  harmful
score_box_tightness        466    -0.15  inert
score_uptrend_bonus        466    -0.11  inert
score_adr                  466    -0.07  inert
score_contraction          466    -0.04  inert
score_touch_density        466    -0.01  inert
score_vol_contraction      466     0.01  inert
score_high_proximity       466     0.03  inert
score_breadth_bonus        466     0.06  inert
score_lps_tightness        466     0.07  inert
score_atr_squeeze          466     0.08  inert
score_ascending_support    466     0.11  inert
score_base_age             466     0.37  beneficial
score_traversal_quality      0        -  unknown

-- Subtraction shortlist -----------------------------------------------
  HARMFUL (down-weight / zero): score_rs_bonus
  INERT   (candidate to trim):  score_box_tightness, score_uptrend_bonus, score_adr, score_contraction, score_touch_density, score_vol_contraction, score_high_proximity, score_breadth_bonus, score_lps_tightness, score_atr_squeeze, score_ascending_support

========================================================================
  END OF REPORT
========================================================================
```
