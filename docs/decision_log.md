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
