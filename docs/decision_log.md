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
