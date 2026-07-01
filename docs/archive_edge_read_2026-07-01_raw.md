```

========================================================================
  CHROLLO ARCHIVE ANALYSIS
========================================================================
DB: C:\Users\User\Documents\Projects\Chrollo Project\webapp\backend\trading_journal.db
Episode dedup: 2826 raw rows -> 998 episodes (1828 continuation re-flags collapsed to the first-seen anchor).
All sections below run on EPISODES (one row per logical setup) via the same
first-seen grouping the archive episode table + /calibration use — raw
continuation re-flags would inflate n and bias every correlation / edge verdict.

========================================================================
  1. SAMPLE COMPOSITION & BIAS DETECTION
========================================================================
Total setups (episodes): 998
By source:     {'screener': 971, 'seed': 26, 'manual': 1}
By tier:       {'S': 670, 'A': 263, 'B': 65}
By setup_type: {'LPS': 925, 'REBOUND': 73}
Date range:    2026-01-16 -> 2026-06-30
With fwd_return_20d: 236 / 998

-- Validity verdict ----------------------------------------------------
OK  Sample looks adequate for outcome + correlation analysis.

-- Data-quality flags --------------------------------------------------
!  5 setup(s) with base_length > 250 bars (~1yr+): CACC(325), MSCI(429), MSCI(433), BMRN(296), CWT(274)
   Almost certainly anchor mis-detection picking an over-long window.

========================================================================
  2. WINNER STRUCTURAL FINGERPRINT
========================================================================
The structural profile of setups in the archive. On seed/winners data this
is the 'what a clean tight setup looks like' template to bias toward.

-- All setups ----------------------------------------------------------
feature                n    median       q25       q75       min       max
--------------------------------------------------------------------------
box_width            998      0.10      0.06      0.14      0.01      0.25
base_length          998     31.00     23.00     46.00     11.00    433.00
touches              998     16.00     12.00     24.00      4.00    114.00
r_touches            998      8.00      5.00     12.00      2.00     61.00
s_touches            998      8.00      5.00     12.00      2.00     70.00
atr_ratio            998      1.05      0.98      1.15      0.24      2.01
lps_length           998      2.00      2.00      3.00      2.00      7.00
breach_days          998      2.00      1.00      5.00      0.00     64.00
vol_contraction      998      0.32      0.22      0.48      0.15      0.99
tightness_ratio      998      0.56      0.45      0.69      0.13      1.23
lps_descent_frac     997      1.00      0.67      1.00      0.00      1.00
r_touch_vol_z        997      0.04     -0.17      0.26     -0.76      2.21
s_touch_vol_z        997      0.10     -0.12      0.36     -1.34      3.00
dist_52w_high_pct    998     -0.08     -0.12     -0.05     -0.61     -0.01
excess_return_6m     997      0.06     -0.03      0.24     -0.28      3.67
rs_vs_sector_pct     761      0.01     -0.02      0.05     -0.39      0.25
breadth_pct          959      0.54      0.51      0.55      0.47      0.58
bars_since_bc        997     78.00     38.00    459.00     14.00    480.00
descent_length       997     14.00      8.00    412.00      1.00    464.00
inner_reaction_pct     4      0.08      0.06      0.09      0.05      0.10
inner_reaction_bars    4      5.00      3.75      6.25      3.00      7.00
contraction_count    997      5.00      3.00      7.00      1.00     43.00
contraction_quality  997      0.71      0.57      0.82      0.24      1.00
final_contraction_depth 997      0.05      0.03      0.08      0.00      0.26
contraction_vol_trend 498      0.69      0.45      0.83      0.00      1.00
base_median_spread_atr 625      0.85      0.79      0.92      0.46      1.10
base_p80_spread_atr  625      1.14      1.06      1.22      0.68      1.68
base_median_spread_pct_box 625      0.32      0.25      0.41      0.09      0.86
base_tight_bar_pct   625      0.68      0.60      0.74      0.37      0.95
support_slope_atr    995      0.02     -0.02      0.06     -0.51      0.43
ascending_support_quality 997      0.31      0.20      0.58      0.00      1.00
eq_r_touches         489     11.00      8.00     16.00      3.00     64.00
eq_s_touches         489      9.00      6.00     14.00      3.00     70.00
eq_r_touch_thirds    489      3.00      2.00      3.00      1.00      3.00
eq_s_touch_thirds    489      3.00      2.00      3.00      1.00      3.00
eq_lower_dwell       489      0.44      0.33      0.56      0.12      0.92
eq_mid_dwell         489      0.64      0.48      0.75      0.14      1.00
eq_upper_dwell       489      0.57      0.44      0.69      0.12      1.00
eq_coverage          489      1.00      1.00      1.00      0.83      1.00
trav_n_full_traversals 440      5.00      3.00      7.00      2.00     23.00
trav_n_swings        440     14.00     10.00     23.00      5.00    116.00
trav_top_dead_space  440      0.00      0.00      0.00      0.00      0.41
trav_bottom_dead_space 440      0.00      0.00      0.08      0.00      0.55
trav_rail_reaches_high 440      6.00      4.00      8.00      1.00     34.00
trav_rail_reaches_low 440      4.00      3.00      6.00      1.00     36.00
trav_max_swing_frac  440      1.35      1.13      1.66      0.80      4.98
trav_last_support_frac 260      0.76      0.56      0.91      0.17      1.00
trav_coil_floor_pos  216      0.32      0.23      0.42      0.09      0.86
adr_pct              997      3.00      2.13      4.15      0.35     12.89
bin_a_bars           510      4.00      2.00      8.00      1.00    445.00
bin_a_range_pct      510      0.08      0.04      0.13      0.01      1.50
bin_a_volume_ratio   510      1.02      0.83      1.27      0.05      7.81
bin_b_range_pct      511      0.16      0.11      0.23      0.01      0.85
bin_b_volume_ratio   511      0.99      0.92      1.05      0.03      1.68
bin_b_cog_end        489      0.66      0.47      0.84      0.00      1.00
bin_b_cog_crossings  489      2.00      1.00      3.00      0.00      6.00
bin_b_cog_rng        489      0.61      0.49      0.72      0.12      0.99
bin_b_cog_corr       489      0.24     -0.07      0.49     -0.89      0.91
bin_c_present        489      0.00      0.00      1.00      0.00      1.00
bin_c_undercut_atr   137      0.78      0.54      0.96      0.00      2.04
bin_c_recovery_bars  137      1.00      0.00      1.00      0.00      5.00
bin_c_time_loc       137      0.68      0.57      0.80      0.50      1.00
bin_c_spring_vol_z   137      0.06     -0.28      0.78     -1.33      5.17
bin_d_bars           511     12.00      7.50     22.00      2.00    143.00
bin_d_range_pct      511      0.11      0.06      0.17      0.00      0.84
bin_d_volume_ratio   511      0.91      0.78      1.01      0.03      1.70
bin_d_support_slope_atr 283      0.06      0.01      0.12     -0.41      0.80
bin_d_higher_low_frac 469      0.33      0.00      0.67      0.00      1.00
bin_d_ascending_support_quality 469      0.20      0.00      0.73      0.00      1.00
bin_lps_bars         511      2.00      2.00      3.00      2.00      7.00
lps_position_in_box  511      0.57      0.29      0.81     -0.52      1.48
bin_d_vs_b_range_ratio 511      0.84      0.51      1.00      0.09      1.00
bin_d_vs_b_volume_ratio 511      0.93      0.83      1.01      0.41      1.81
bin_d_vs_b_support_quality_delta 283      0.12     -0.14      0.39     -0.90      0.90
lps_stretch_atr      511     -1.06     -1.63     -0.51     -3.81      1.58
lps_stretch_box      511     -0.43     -0.71     -0.19     -1.52      0.48
lps_anchor_bar        12    502.00    499.50    503.00    497.00    503.00
lps_low_bar           12    503.50    501.50    504.00    499.00    504.00
lps_swing_depth_pct   12      0.03      0.02      0.04      0.00      0.08
lps_swing_depth_atr   12      1.20      0.83      1.46      0.60      2.28
lps_swing_depth_box   12      0.54      0.30      0.60      0.18      0.74
last_supper_pullback_from_extension_pct  12      0.03      0.02      0.04      0.00      0.08
last_supper_source_box_age   1      8.00      8.00      8.00      8.00      8.00
last_supper_reclaim_quality  12      0.63      0.55      0.85      0.50      1.00
stage2_ma_stack_pass 511      1.00      0.00      1.00      0.00      1.00
stage2_ma200_slope_1m_pct 510      2.32      0.78      4.70     -3.61     24.94
stage2_52w_low_pct   511      0.49      0.30      0.92      0.05      8.49
stage2_trend_pass_count 511      7.00      6.00      7.00      2.00      7.00
stage2_trend_pass    511      1.00      0.00      1.00      0.00      1.00
htf_w_stage2         231      1.00      1.00      1.00      0.00      1.00
htf_w_in_consol      231      0.00      0.00      1.00      0.00      1.00
htf_w_reaccum        231      0.00      0.00      1.00      0.00      1.00
htf_w_daily_nested    70      0.00      0.00      1.00      0.00      1.00
htf_w_box_width       70      0.13      0.09      0.15      0.04      0.18
htf_m_stage2         231      1.00      0.50      1.00      0.00      1.00
htf_m_in_consol      231      0.00      0.00      0.00      0.00      1.00
htf_m_reaccum        231      0.00      0.00      0.00      0.00      1.00
htf_m_daily_nested     4      0.50      0.00      1.00      0.00      1.00
htf_m_box_width        4      0.10      0.10      0.12      0.10      0.17

-- Horizontal axis - time structure (duration, rail tests, traversal) --
feature                n    median       q25       q75       min       max
--------------------------------------------------------------------------
base_length          998     31.00     23.00     46.00     11.00    433.00
r_touches            998      8.00      5.00     12.00      2.00     61.00
s_touches            998      8.00      5.00     12.00      2.00     70.00
eq_r_touches         489     11.00      8.00     16.00      3.00     64.00
eq_s_touches         489      9.00      6.00     14.00      3.00     70.00
eq_r_touch_thirds    489      3.00      2.00      3.00      1.00      3.00
eq_s_touch_thirds    489      3.00      2.00      3.00      1.00      3.00
breach_days          998      2.00      1.00      5.00      0.00     64.00
lps_length           998      2.00      2.00      3.00      2.00      7.00
bin_lps_bars         511      2.00      2.00      3.00      2.00      7.00
lps_position_in_box  511      0.57      0.29      0.81     -0.52      1.48
lps_anchor_bar        12    502.00    499.50    503.00    497.00    503.00
lps_low_bar           12    503.50    501.50    504.00    499.00    504.00
last_supper_source_box_age   1      8.00      8.00      8.00      8.00      8.00
trav_n_full_traversals 440      5.00      3.00      7.00      2.00     23.00
trav_n_swings        440     14.00     10.00     23.00      5.00    116.00
trav_rail_reaches_high 440      6.00      4.00      8.00      1.00     34.00
trav_rail_reaches_low 440      4.00      3.00      6.00      1.00     36.00
trav_last_support_frac 260      0.76      0.56      0.91      0.17      1.00
bin_c_time_loc       137      0.68      0.57      0.80      0.50      1.00
bin_d_bars           511     12.00      7.50     22.00      2.00    143.00

-- Vertical axis - price magnitude (rails/height, undercut, thrust) ----
feature                n    median       q25       q75       min       max
--------------------------------------------------------------------------
box_width            998      0.10      0.06      0.14      0.01      0.25
tightness_ratio      998      0.56      0.45      0.69      0.13      1.23
atr_ratio            998      1.05      0.98      1.15      0.24      2.01
lps_descent_frac     997      1.00      0.67      1.00      0.00      1.00
bin_c_undercut_atr   137      0.78      0.54      0.96      0.00      2.04
lps_stretch_atr      511     -1.06     -1.63     -0.51     -3.81      1.58
lps_stretch_box      511     -0.43     -0.71     -0.19     -1.52      0.48
lps_swing_depth_pct   12      0.03      0.02      0.04      0.00      0.08
lps_swing_depth_atr   12      1.20      0.83      1.46      0.60      2.28
lps_swing_depth_box   12      0.54      0.30      0.60      0.18      0.74
last_supper_pullback_from_extension_pct  12      0.03      0.02      0.04      0.00      0.08
last_supper_reclaim_quality  12      0.63      0.55      0.85      0.50      1.00
trav_top_dead_space  440      0.00      0.00      0.00      0.00      0.41
trav_bottom_dead_space 440      0.00      0.00      0.08      0.00      0.55
trav_max_swing_frac  440      1.35      1.13      1.66      0.80      4.98
trav_coil_floor_pos  216      0.32      0.23      0.42      0.09      0.86
final_contraction_depth 997      0.05      0.03      0.08      0.00      0.26
bin_d_vs_b_range_ratio 511      0.84      0.51      1.00      0.09      1.00

-- setup_type = LPS  (n=925) -------------------------------------------
feature                n    median       q25       q75       min       max
--------------------------------------------------------------------------
box_width            925      0.10      0.06      0.14      0.01      0.25
atr_ratio            925      1.05      0.98      1.14      0.24      1.74
tightness_ratio      925      0.56      0.46      0.69      0.13      1.23
lps_descent_frac     924      1.00      0.67      1.00      0.00      1.00
contraction_quality  924      0.71      0.57      0.82      0.24      1.00
base_median_spread_atr 585      0.85      0.79      0.92      0.46      1.10
base_tight_bar_pct   585      0.68      0.60      0.74      0.37      0.95
bin_d_vs_b_range_ratio 477      0.84      0.54      1.00      0.09      1.00
bin_d_ascending_support_quality 439      0.20      0.00      0.75      0.00      1.00
trav_n_full_traversals 413      5.00      3.00      7.00      2.00     23.00
trav_top_dead_space  413      0.00      0.00      0.00      0.00      0.41
base_length          925     32.00     23.00     49.00     11.00    433.00
touches              925     17.00     12.00     25.00      4.00    114.00
vol_contraction      925      0.32      0.22      0.48      0.15      0.99
dist_52w_high_pct    925     -0.07     -0.12     -0.04     -0.61     -0.01

-- setup_type = REBOUND  (n=73) ----------------------------------------
feature                n    median       q25       q75       min       max
--------------------------------------------------------------------------
box_width             73      0.09      0.06      0.11      0.01      0.21
atr_ratio             73      1.09      0.99      1.18      0.38      2.01
tightness_ratio       73      0.53      0.42      0.68      0.26      1.04
lps_descent_frac      73      1.00      0.80      1.00      0.50      1.00
contraction_quality   73      0.73      0.57      0.83      0.34      0.96
base_median_spread_atr  40      0.86      0.77      0.91      0.56      1.10
base_tight_bar_pct    40      0.70      0.62      0.76      0.43      0.94
bin_d_vs_b_range_ratio  34      0.61      0.35      0.95      0.20      1.00
bin_d_ascending_support_quality  30      0.00      0.00      0.00      0.00      0.92
trav_n_full_traversals  27      5.00      3.00      6.00      2.00     11.00
trav_top_dead_space   27      0.00      0.00      0.02      0.00      0.23
base_length           73     22.00     18.00     25.00     11.00     59.00
touches               73     14.00     11.00     18.00      6.00     29.00
vol_contraction       73      0.34      0.22      0.51      0.15      0.90
dist_52w_high_pct     73     -0.11     -0.15     -0.08     -0.57     -0.01

-- tier = S  (n=670) ---------------------------------------------------
feature                n    median       q25       q75       min       max
--------------------------------------------------------------------------
box_width            670      0.09      0.06      0.13      0.01      0.25
atr_ratio            670      1.06      0.98      1.15      0.24      2.01
tightness_ratio      670      0.52      0.43      0.62      0.13      1.17
lps_descent_frac     669      1.00      0.67      1.00      0.00      1.00
contraction_quality  669      0.72      0.58      0.82      0.28      1.00
base_median_spread_atr 363      0.84      0.78      0.91      0.46      1.10
base_tight_bar_pct   363      0.68      0.62      0.74      0.37      0.95
bin_d_vs_b_range_ratio 253      0.83      0.49      0.99      0.11      1.00
bin_d_ascending_support_quality 229      0.00      0.00      0.74      0.00      1.00
trav_n_full_traversals 212      5.00      4.00      7.00      2.00     23.00
trav_top_dead_space  212      0.00      0.00      0.00      0.00      0.41
base_length          670     31.00     23.00     43.00     11.00    433.00
touches              670     17.00     12.00     24.00      4.00    106.00
score                670    123.90    117.50    133.47     96.10    158.50

-- tier = A  (n=263) ---------------------------------------------------
feature                n    median       q25       q75       min       max
--------------------------------------------------------------------------
box_width            263      0.11      0.06      0.16      0.01      0.25
atr_ratio            263      1.05      0.97      1.15      0.38      1.74
tightness_ratio      263      0.66      0.51      0.77      0.20      1.23
lps_descent_frac     263      1.00      0.67      1.00      0.00      1.00
contraction_quality  263      0.69      0.56      0.80      0.24      1.00
base_median_spread_atr 205      0.86      0.79      0.92      0.64      1.05
base_tight_bar_pct   205      0.67      0.59      0.74      0.45      0.90
bin_d_vs_b_range_ratio 201      0.85      0.54      1.00      0.12      1.00
bin_d_ascending_support_quality 188      0.27      0.00      0.70      0.00      1.00
trav_n_full_traversals 176      5.00      3.00      7.00      2.00     19.00
trav_top_dead_space  176      0.00      0.00      0.00      0.00      0.23
base_length          263     32.00     22.00     51.50     11.00    296.00
touches              263     16.00     11.00     22.50      4.00    114.00
score                263    104.90    100.50    108.80     95.00    141.50

-- tier = B  (n=65) ----------------------------------------------------
feature                n    median       q25       q75       min       max
--------------------------------------------------------------------------
box_width             65      0.12      0.09      0.15      0.03      0.18
atr_ratio             65      1.01      0.97      1.10      0.78      1.43
tightness_ratio       65      0.75      0.65      0.90      0.32      1.12
lps_descent_frac      65      1.00      0.67      1.00      0.00      1.00
contraction_quality   65      0.64      0.52      0.77      0.36      0.94
base_median_spread_atr  57      0.89      0.79      0.97      0.55      1.10
base_tight_bar_pct    57      0.65      0.56      0.75      0.43      0.88
bin_d_vs_b_range_ratio  57      0.85      0.51      1.00      0.09      1.00
bin_d_ascending_support_quality  52      0.22      0.00      0.69      0.00      1.00
trav_n_full_traversals  52      3.00      2.00      5.00      2.00     19.00
trav_top_dead_space   52      0.00      0.00      0.01      0.00      0.21
base_length           65     37.00     19.00     72.00     13.00    238.00
touches               65     16.00     10.00     25.00      5.00     85.00
score                 65     90.10     86.00     92.10     77.60     94.70

========================================================================
  3. SEGMENTED PERFORMANCE
========================================================================

-- By tier -------------------------------------------------------------
tier               n   med20d   avg20d   med60d   win%  trig%   avgR   expR
----------------------------------------------------------------------------
S                670    +8.6%    +9.3%   +25.6% +86.4% +89.7%   1.89   1.89
A                263    +6.8%    +6.2%   +19.2% +75.0% +84.5%   1.72   1.72
B                 65    -5.1%    -3.3%        - +25.0% +81.5%   0.77   0.77

-- By setup_type -------------------------------------------------------
setup_type         n   med20d   avg20d   med60d   win%  trig%   avgR   expR
----------------------------------------------------------------------------
LPS              925    +7.9%    +8.4%   +22.0% +83.6% +88.5%   1.63   1.63
REBOUND           73    +9.2%    +9.4%   +41.6% +75.0% +80.0%   5.06   5.06

-- By zone -------------------------------------------------------------
zone               n   med20d   avg20d   med60d   win%  trig%   avgR   expR
----------------------------------------------------------------------------
INSIDE           835    +7.9%    +8.6%   +23.6% +83.7% +89.3%   1.67   1.67
OVERSHOOT_R       89    +5.0%    +3.5%    +1.5% +80.0% +80.7%   0.78   0.78
UNDERCUT_S        73    +9.2%    +9.4%   +41.6% +75.0% +80.0%   5.06   5.06

-- By inner_exists(0/1) ------------------------------------------------
inner_exists(0/1)   n   med20d   avg20d   med60d   win%  trig%   avgR   expR
----------------------------------------------------------------------------
0.0              922    +8.0%    +8.7%   +24.5% +82.7% +88.0%   1.86   1.86
1.0               75    +7.2%    +5.4%        - +86.7% +85.7%   1.43   1.43

-- By lps_in_inner(0/1) ------------------------------------------------
lps_in_inner(0/1)   n   med20d   avg20d   med60d   win%  trig%   avgR   expR
----------------------------------------------------------------------------
0.0              483   +14.4%   +14.5%   +24.5% +92.3% +84.2%   3.00   3.00
1.0               28        -        -        -      - +79.2%      -      -

-- By lps_swing --------------------------------------------------------
lps_swing          n   med20d   avg20d   med60d   win%  trig%   avgR   expR
----------------------------------------------------------------------------
clean_downswing    1        -        -        -      -      -      -      -
rising_support_shelf   2        -        -        -      -      -      -      -
terminal_valley    8        -        -        -      -      -      -      -
undercut_rebound   1        -        -        -      -      -      -      -

-- By inner_source -----------------------------------------------------
inner_source       n   med20d   avg20d   med60d   win%  trig%   avgR   expR
----------------------------------------------------------------------------
inner_climax       4        -        -        -      - +66.7%      -      -
midpoint          38        -        -        -      - +88.2%      -      -

-- By spy_trend --------------------------------------------------------
spy_trend          n   med20d   avg20d   med60d   win%  trig%   avgR   expR
----------------------------------------------------------------------------
BULLISH          951    +7.7%    +7.7%        - +81.8% +87.5%   1.69   1.69

-- By box_width --------------------------------------------------------
box_width          n   med20d   avg20d   med60d   win%  trig%   avgR   expR
----------------------------------------------------------------------------
low              333    +7.9%    +8.0%   +21.4% +90.4% +90.0%   1.91   1.91
mid              332    +7.3%    +8.6%   +23.0% +79.7% +86.5%   1.88   1.88
high             333    +8.2%    +9.1%   +40.7% +74.1% +87.1%   1.64   1.64

-- By breadth ----------------------------------------------------------
breadth            n   med20d   avg20d   med60d   win%  trig%   avgR   expR
----------------------------------------------------------------------------
low              386        -        -        -      - +85.2%      -      -
mid              319        -        -        -      - +88.0%      -      -
high             254    +7.7%    +7.7%        - +81.8% +90.6%   1.69   1.69

========================================================================
  4. PREDICTOR CORRELATIONS vs FORWARD OUTCOMES
========================================================================

-- vs fwd_return_20d  (top predictors by |corr|) -----------------------
feature                     corr
--------------------------------
bin_d_vs_b_support_quality_delta  +0.403  *
eq_s_touch_thirds         +0.387  *
bin_d_range_pct           -0.386  *
trav_max_swing_frac       -0.362  *
eq_lower_dwell            +0.336  *
stage2_52w_low_pct        +0.331  *
bin_d_bars                -0.307  *
bin_b_cog_end             -0.306  *
bin_b_cog_corr            -0.301  *
base_tight_bar_pct        +0.290
eq_upper_dwell            -0.276
lps_position_in_box       -0.256
lps_stretch_box           -0.256
eq_r_touches              -0.249
s_touches                 +0.244

-- vs fwd_return_60d  (top predictors by |corr|) -----------------------
feature                     corr
--------------------------------
lps_stretch_box           -0.644  *
lps_position_in_box       -0.644  *
stage2_52w_low_pct        +0.625  *
lps_stretch_atr           -0.589  *
bin_b_cog_end             -0.577  *
stage2_ma200_slope_1m_pct  +0.572  *
excess_return_6m          +0.523  *
bin_b_cog_corr            -0.505  *
trav_coil_floor_pos       -0.497  *
bin_a_bars                -0.472  *
s_touch_vol_z             -0.468  *
dist_52w_high_pct         -0.428  *
score_high_proximity      -0.422  *
adr_pct                   +0.416  *
eq_lower_dwell            +0.404  *

-- vs r_multiple_20d  (top predictors by |corr|) -----------------------
feature                     corr
--------------------------------
lps_position_in_box       -0.618  *
lps_stretch_box           -0.618  *
bin_b_cog_corr            -0.608  *
bin_b_cog_end             -0.550  *
lps_stretch_atr           -0.516  *
eq_r_touch_thirds         -0.509  *
bin_d_vs_b_range_ratio    -0.481  *
trav_top_dead_space       +0.454  *
eq_lower_dwell            +0.436  *
bin_d_range_pct           -0.392  *
bin_d_bars                -0.380  *
bin_d_higher_low_frac     -0.340  *
trav_last_support_frac    +0.330  *
trav_rail_reaches_high    -0.324  *
bin_c_present             +0.306  *

========================================================================
  5. PRIME-DIRECTIVE TEST - IS TIGHTNESS PREDICTIVE?
========================================================================
The engine's core thesis: tighter, cleaner structure -> better outcomes.
This isolates the tightness features and tests that claim directly.

-- box_width: tight-tertile vs loose-tertile fwd_return_20d ------------
  tight (n=78): mean +7.7%   loose (n=78): mean +9.6%
  edge from tightness: -1.9%  -> CONTRADICTS thesis X

-- atr_ratio: tight-tertile vs loose-tertile fwd_return_20d ------------
  tight (n=78): mean +6.8%   loose (n=78): mean +9.3%
  edge from tightness: -2.5%  -> CONTRADICTS thesis X

-- tightness_ratio: tight-tertile vs loose-tertile fwd_return_20d ------
  tight (n=78): mean +7.6%   loose (n=78): mean +9.1%
  edge from tightness: -1.6%  -> CONTRADICTS thesis X

-- lps_descent_frac: tight-tertile vs loose-tertile fwd_return_20d -----
  tight (n=78): mean +8.1%   loose (n=78): mean +8.8%
  edge from tightness: -0.7%  -> CONTRADICTS thesis X

-- contraction_quality: tight-tertile vs loose-tertile fwd_return_20d --
  tight (n=78): mean +7.4%   loose (n=78): mean +9.4%
  edge from tightness: -2.0%  -> CONTRADICTS thesis X

-- base_median_spread_atr: tight-tertile vs loose-tertile fwd_return_20d 
  tight (n=8): mean +13.3%   loose (n=8): mean +14.3%
  edge from tightness: -1.0%  -> CONTRADICTS thesis X

-- base_tight_bar_pct: tight-tertile vs loose-tertile fwd_return_20d ---
  tight (n=8): mean +14.3%   loose (n=8): mean +8.5%
  edge from tightness: +5.8%  -> supports thesis OK

-- bin_d_vs_b_range_ratio: tight-tertile vs loose-tertile fwd_return_20d 
  tight (n=8): mean +15.7%   loose (n=8): mean +5.4%
  edge from tightness: +10.3%  -> supports thesis OK

-- bin_d_ascending_support_quality: tight-tertile vs loose-tertile fwd_return_20d 
  tight (n=8): mean +15.8%   loose (n=8): mean +16.5%
  edge from tightness: -0.7%  -> CONTRADICTS thesis X

-- trav_n_full_traversals: tight-tertile vs loose-tertile fwd_return_20d 
  tight (n=8): mean +16.3%   loose (n=8): mean +11.4%
  edge from tightness: +4.9%  -> supports thesis OK

-- trav_top_dead_space: tight-tertile vs loose-tertile fwd_return_20d --
  tight (n=8): mean +11.0%   loose (n=8): mean +12.1%
  edge from tightness: -1.1%  -> CONTRADICTS thesis X

========================================================================
  6. SIGNAL EDGE & SUBTRACTION CANDIDATES (Stage 1)
========================================================================
Each scoring sub-score is meant to REWARD a setup. This ranks them by
rank-association with realized outcome and flags the ones that don't
earn their points: HARMFUL (negative) or INERT (near-zero). These are
subtraction CANDIDATES only — re-weighting is a separate guarded step.

-- Win quality (durable vs cash-grab) ----------------------------------
  durable wins: 207   cash-grab wins: 13 (round-trip to stop within 5 bars of target)
  median bars target->stop among round-trips: 2.50

Primary outcome: durable_win  (n=370, minority class=163, noise floor |r| < 0.15)

sub-score                    n   rank_r  verdict
--------------------------------------------------------
score_rs_bonus             369    -0.12  inert
score_uptrend_bonus        370    -0.10  inert
score_box_tightness        370    -0.10  inert
score_contraction          369    -0.06  inert
score_adr                  369    -0.04  inert
score_touch_density        370    -0.01  inert
score_breadth_bonus        369     0.02  inert
score_vol_contraction      370     0.04  inert
score_lps_tightness        370     0.07  inert
score_atr_squeeze          370     0.07  inert
score_high_proximity       369     0.11  inert
score_ascending_support    369     0.12  inert
score_traversal_quality     27     0.19  beneficial
score_base_age             370     0.26  beneficial

-- Subtraction shortlist -----------------------------------------------
  HARMFUL (down-weight / zero): (none)
  INERT   (candidate to trim):  score_rs_bonus, score_uptrend_bonus, score_box_tightness, score_contraction, score_adr, score_touch_density, score_breadth_bonus, score_vol_contraction, score_lps_tightness, score_atr_squeeze, score_high_proximity, score_ascending_support

========================================================================
  END OF REPORT
========================================================================
```
