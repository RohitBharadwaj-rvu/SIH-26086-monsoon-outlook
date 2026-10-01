# Decision log (overnight 2026-10-01 -> 02, all times IST)

| Time | Decision | Reason |
|---|---|---|
| 19:45 | New private repo `RohitBharadwaj-rvu/SIH-26074-downscaling-v3`; old repo untouched | user request |
| 19:50 | v3 dataset uploaded as a private Kaggle dataset to each of the 3 team accounts | private datasets cannot be shared across accounts by API; 3 x 559 MB uploads |
| 20:00 | Spatiotemporal transformer (S 17.7M / M 34.2M / L 58.7M) replaces the U-Net for all sprints | user request: follow the plan's DiT/MoE design |
| 20:05 | Diffusion = residual of the frozen deterministic transformer (CorrDiff-style) | cleaner S6 comparison; diffusion only models what regression misses |
| 20:05 | Mass-conservation loss dropped | with real GFS (1.4-2.2x wet) it would teach the GFS bias |
| 20:06 | Timing on Kaggle T4: S N40 H14 ~70 s/epoch, L ~107 s/epoch; 2 runs per T4x2 session work | measured |
| 20:08 | S runs: 50 epochs max, patience 10, 55 min budget | fits ~2 runs per lane per 2 h |
| 20:09 | Added `--precip_lin_w` (precip L1 in mm) variant | after 2 epochs CSI@15 collapsed (log-space Huber -> median bias); tested as `lin_*` alongside S3-5 |
| 20:10 | Phase A launched: 16 runs (S4 H in {1,3,7,14}, S5 N in {24,32,40} at H=7, loss variant), 2 seeds each | |
| 20:12 | Kaggle allows >= 2 concurrent GPU sessions per account -> 6 sessions / 12 GPUs | quota 81.7 h / 13.8 h ~ 5.9 sessions: keep ~6 running |
| 20:40 | Sprint 3 non-learned baselines: GFS-QM (per-lead, per-pixel quantile mapping, train 2015-21) CSS 0.22 val / 0.19 test vs GFS-bilinear | `scripts/baselines_s3.py`; learned models must beat 0.22 |
| 20:40 | CORRECTION: GFS is ~15-18 % too dry over land, not 1.4-2.2x too wet | earlier figure compared against coarse CHIRPS incl. 0-filled sea pixels; mass-conservation loss stays removed (GFS biased either way) |
| 20:42 | Every deterministic run from Phase B/C on also reports CSS after post-hoc precip quantile mapping (train-fitted, per lead) | timing runs predicted only 35-43 % of observed rain (log-loss median bias); calibration is cheap and needs no retraining. Selection still uses raw CSS so Phase A stays comparable |
| 21:02 | Long-schedule (100 ep) confirmation runs for the Sprint 4 and Sprint 5 runner-ups, added automatically when Phase B/C is planned | all Phase A runs hit the 50-epoch cap still improving; larger contexts converge slower, so 50-epoch ranking may favour small N |
| 21:14 | Calibration check: pooled precip QM lifts val CSS 0.138/0.155 -> 0.213/0.228 (GFS-QM 0.218), test 0.251/0.207 (GFS-QM 0.194); bias only 0.54 -> 0.68, so switched to per-block (5x5 px) QM, verified next on s4_h14 ckpts | precipitation is half the CSS weight |
| 21:22 | Tie rule corrected to 1 SE of the difference of seed means (pooled_sd*sqrt(2/n)) and summary header fixed | old 2*sd rule (0.044 with 2 seeds) would have tied H=1 (worst, 0.100) with H=14 (0.136) and picked H=1 |
| 21:25 | Diffusion pilot (S, H=7, N=16, on s4_h7_n16_s0, 2 seeds, 60 min) queued for the slot freed at ~22:05 | de-risks the never-run-at-scale diffusion pipeline ~2 h before the main S6 run; early read on precip bias |
| 21:26 | Per-block QM check (s4_h14): val CSS 0.150/0.122 -> 0.224/0.199, test 0.205/0.147 -> 0.265/0.211; bias val 0.66/0.61, test 0.87/0.76. Residual val dryness is year shift (2022 wetter than train), not spatial pooling. Kept per-block QM as det output step; diffusion is the intended intensity fix | calibrated det >= GFS-QM (0.218 val / 0.194 test) |
| 22:00 | **Metric fix**: CSS bias component changed from ratio skill `1 - lb/lb_ref` to bounded `exp(-lb) - exp(-lb_ref)`; all CSS recomputed from stored aggregates (summarizer now recomputes, so planner uses the fixed metric) | at D+5/D+6 GFS is nearly unbiased (log-bias 0.10) so the ratio gave skill -7.7 on that one term, swamping CSS (made every model look worse than GFS at long leads) and inflating seed noise |
| 22:00 | Re-scored with the fixed metric: GFS-QM 0.187 val / 0.179 test; raw transformer 0.208-0.228 val (all leads positive), i.e. beats GFS-QM before any calibration | |
| 22:03 | Confirmation runs (100 ep, 2 seeds) always include H=14, N=40 and H=14+N=40 besides the runner-ups | 50-epoch Phase A may under-rate long history / wide context (they converge slower and still improving); user's prior that they should help deserves a converged test |
| 22:14 | H* = 3, N* = 16 (N/M = 1.00), precip mm-loss = True | Sprint 4 winner s4_h3_n16, Sprint 5 winner s4_h7_n16, Sprint 3 winner lin_h7_n16 (seed-mean val CSS, ties to cheaper) |
| 22:14 | Long-schedule confirmation run for runner-up H: H=14, N=16 | Phase A runs were capped at 50 epochs while still improving |
| 22:14 | Long-schedule confirmation run for runner-up N: H=3, N=20 | Phase A runs were capped at 50 epochs while still improving |
| 22:14 | Long-schedule confirmation run for runner-up Nmax: H=3, N=40 | Phase A runs were capped at 50 epochs while still improving |
| 22:14 | Long-schedule confirmation run for runner-up Hmax+Nmax: H=14, N=40 | Phase A runs were capped at 50 epochs while still improving |
| 22:15 | precip mm-loss (`--precip_lin_w 1.0`) fixed ON for all Phase B/C runs | Sprint 3: lin 0.225 vs plain 0.220 CSS (> 0.005 floor), CSI@30 0.209 vs 0.180, bias 0.54 vs 0.50 |
| 22:15 | Confirmation runs H=14/N=16 and H=14/N=40 started early (independent of the H*/N* decision) on idle slots; confirmation budget 130 min so N=40 also reaches 100 epochs | equal-epoch, not equal-wall-time, comparison avoids penalising slower wide-context configs |
| 22:15 | Sprint 4 with H=5/10 and seed 2: H=1 0.212 < H=5 0.219 ~ H=7 0.220 ~ H=10 0.221 ~ H=3 0.223 < H=14 0.228 (floor 0.0077) | rule picks H=3; H=14 tested at 100 epochs |
