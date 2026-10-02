# Sprint 10 open problems — results on the 2023 test season

All models: H=3, N=40 (N/M 2.5), mm-loss, MoE backbone (E8 top-2, 50 %), trained 2015-2022 for fixed epochs;
diffusion sampled with DPM-Solver++ 24 steps x 8 members. CSS vs GFS-bilinear (ensemble mean for diffusion).

| model | CSS | CSS +precipQM | precip_crps | precip_ssr | precip_cov90 | precip_bias_ratio | brier30 | precip_csi30 | precip_wet_mae | tmax_mae | rh_mae | wind_vec_rmse |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| deterministic MoE (seed 0) | _pending_ |
| deterministic MoE (seed 1) | _pending_ |
| diffusion, in-sample residuals (seed 0) | _pending_ |
| diffusion, in-sample residuals (seed 1) | _pending_ |
| diffusion, CROSS-FITTED residuals (seed 0) | _pending_ |
| diffusion, CROSS-FITTED residuals (seed 1) | _pending_ |
| diffusion, cross-fitted, MoE denoiser (seed 0) | _pending_ |
| diffusion, cross-fitted, trained 2015-21 (calibration model) | _pending_ |
