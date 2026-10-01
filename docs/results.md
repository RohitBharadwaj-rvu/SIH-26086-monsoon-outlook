# Results (validation 2022; test 2023 shown for reference only)


## Sprint 3 — deterministic baseline + loss variant (H=7, N=16)

| config | seeds | val CSS (mean ± sd) | val CSS +precipQM | test CSS | precip_wet_mae | precip_csi15 | precip_csi30 | precip_fss15 | precip_bias_ratio | tmax_mae | tmin_mae | rh_mae | wind_vec_rmse |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **lin_h7_n16** | 2 | 0.1467 ± 0.0118 | nan | 0.1580 | 17.676 | 0.282 | 0.209 | 0.619 | 0.541 | 0.932 | 0.422 | 3.064 | 0.784 |
| GFS-bilinear (reference) | | 0 | | 0 | 17.826 | 0.278 | 0.174 | 0.624 | 0.807 | 1.501 | 0.687 | 6.412 | 1.863 |

Noise floor 0.0118; configs within it of the best: lin_h7_n16. **Selected: lin_h7_n16** (cheapest within the floor).


## Sprint 4 — history length (N=16)

| config | seeds | val CSS (mean ± sd) | val CSS +precipQM | test CSS | precip_wet_mae | precip_csi15 | precip_csi30 | precip_fss15 | precip_bias_ratio | tmax_mae | tmin_mae | rh_mae | wind_vec_rmse |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| s4_h14_n16 | 2 | 0.1363 ± 0.0202 | nan | 0.1758 | 17.828 | 0.265 | 0.185 | 0.604 | 0.510 | 0.926 | 0.386 | 2.918 | 0.757 |
| **s4_h3_n16** | 2 | 0.1270 ± 0.0107 | nan | 0.1708 | 17.858 | 0.259 | 0.187 | 0.591 | 0.500 | 0.930 | 0.393 | 2.944 | 0.768 |
| s4_h1_n16 | 2 | 0.0999 ± 0.0302 | nan | 0.1258 | 18.196 | 0.245 | 0.172 | 0.562 | 0.470 | 0.950 | 0.392 | 2.975 | 0.762 |
| GFS-bilinear (reference) | | 0 | | 0 | 17.826 | 0.278 | 0.174 | 0.624 | 0.807 | 1.501 | 0.687 | 6.412 | 1.863 |

Noise floor 0.0219; configs within it of the best: s4_h14_n16, s4_h3_n16. **Selected: s4_h3_n16** (cheapest within the floor).


## Sprint 5 — spatial context (H=7; N=16 row shared with Sprint 4)

| config | seeds | val CSS (mean ± sd) | val CSS +precipQM | test CSS | precip_wet_mae | precip_csi15 | precip_csi30 | precip_fss15 | precip_bias_ratio | tmax_mae | tmin_mae | rh_mae | wind_vec_rmse |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **s5_h7_n40** | 2 | 0.1306 ± 0.0072 | nan | 0.2093 | 17.889 | 0.249 | 0.182 | 0.570 | 0.519 | 0.909 | 0.398 | 2.989 | 0.760 |
| s5_h7_n32 | 2 | 0.1233 ± 0.0055 | nan | 0.1884 | 17.980 | 0.253 | 0.182 | 0.578 | 0.507 | 0.928 | 0.397 | 3.039 | 0.753 |
| GFS-bilinear (reference) | | 0 | | 0 | 17.826 | 0.278 | 0.174 | 0.624 | 0.807 | 1.501 | 0.687 | 6.412 | 1.863 |

Noise floor 0.0064; configs within it of the best: s5_h7_n40. **Selected: s5_h7_n40** (cheapest within the floor).


## Sprint 6 — deterministic vs diffusion

_no results yet for s6__


## Sprint 9 — capacity and MoE

_no results yet for s9__
