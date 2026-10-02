# Sprint 10 open problems — results on the 2023 test season

All models: H=3, N=40 (N/M 2.5), mm-loss, MoE backbone (E8 top-2, 50 %), trained 2015-2022 for fixed epochs;
diffusion sampled with DPM-Solver++ 24 steps x 8 members. CSS vs GFS-bilinear (ensemble mean for diffusion).

| model | CSS | CSS +precipQM | precip_crps | precip_ssr | precip_cov90 | precip_bias_ratio | brier30 | precip_csi30 | precip_wet_mae | tmax_mae | rh_mae | wind_vec_rmse |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| deterministic MoE (seed 0) | 0.2183 | 0.2323 | nan | nan | nan | 0.689 | nan | 0.185 | 17.274 | 1.217 | 3.602 | 0.695 |
| deterministic MoE (seed 1) | 0.2278 | 0.2409 | nan | nan | nan | 0.687 | nan | 0.184 | 17.276 | 1.116 | 3.399 | 0.670 |
| diffusion, in-sample residuals (seed 0) | 0.2466 |  | 5.640 | 1.004 | 0.361 | 0.921 | 0.050 | 0.191 | 16.546 | 1.189 | 3.518 | 0.657 |
| diffusion, in-sample residuals (seed 1) | _pending_ |
| diffusion, CROSS-FITTED residuals (seed 0) | 0.2466 |  | 4.474 | 0.865 | 0.487 | 0.773 | 0.039 | 0.155 | 16.463 | 1.136 | 3.356 | 0.621 |
| diffusion, CROSS-FITTED residuals (seed 1) | _pending_ |
| diffusion, cross-fitted, MoE denoiser (seed 0) | 0.2482 |  | 4.449 | 0.811 | 0.438 | 0.786 | 0.039 | 0.157 | 16.274 | 1.156 | 3.409 | 0.613 |
| diffusion, cross-fitted, trained 2015-21 (calibration model) | 0.2447 |  | 4.499 | 1.020 | 0.516 | 0.912 | 0.041 | 0.151 | 16.282 | 1.145 | 3.384 | 0.663 |
