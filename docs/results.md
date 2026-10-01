# Results (validation 2022; test 2023 shown for reference only)


## Sprint 3 — deterministic baseline + loss variant (H=7, N=16)

| config | seeds | val CSS (mean ± sd) | val CSS +precipQM | test CSS | precip_wet_mae | precip_csi15 | precip_csi30 | precip_fss15 | precip_bias_ratio | tmax_mae | tmin_mae | rh_mae | wind_vec_rmse |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **lin_h7_n16** | 2 | 0.2254 ± 0.0068 | nan | 0.2156 | 17.676 | 0.282 | 0.209 | 0.619 | 0.541 | 0.932 | 0.422 | 3.064 | 0.784 |
| s4_h7_n16 | 3 | 0.2203 ± 0.0012 | nan | 0.2304 | 17.785 | 0.258 | 0.183 | 0.588 | 0.502 | 0.934 | 0.402 | 2.965 | 0.761 |
| GFS-bilinear (reference) | | 0 | | 0 | 17.826 | 0.278 | 0.174 | 0.624 | 0.807 | 1.501 | 0.687 | 6.412 | 1.863 |

Noise floor 0.0050; configs within it of the best: lin_h7_n16. **Selected: lin_h7_n16** (cheapest within the floor).


## Sprint 4 — history length (N=16)

| config | seeds | val CSS (mean ± sd) | val CSS +precipQM | test CSS | precip_wet_mae | precip_csi15 | precip_csi30 | precip_fss15 | precip_bias_ratio | tmax_mae | tmin_mae | rh_mae | wind_vec_rmse |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| s4_h14_n16 | 2 | 0.2276 ± 0.0102 | nan | 0.2325 | 17.828 | 0.265 | 0.185 | 0.604 | 0.510 | 0.926 | 0.386 | 2.918 | 0.757 |
| **s4_h3_n16** | 3 | 0.2230 ± 0.0057 | nan | 0.2261 | 17.871 | 0.259 | 0.186 | 0.590 | 0.507 | 0.926 | 0.391 | 2.935 | 0.763 |
| s4_h10_n16 | 2 | 0.2209 ± 0.0054 | 0.2465 | 0.2337 | 17.806 | 0.259 | 0.181 | 0.591 | 0.515 | 0.940 | 0.394 | 2.973 | 0.770 |
| s4_h7_n16 | 3 | 0.2203 ± 0.0012 | nan | 0.2304 | 17.785 | 0.258 | 0.183 | 0.588 | 0.502 | 0.934 | 0.402 | 2.965 | 0.761 |
| s4_h5_n16 | 3 | 0.2193 ± 0.0119 | 0.2451 | 0.2335 | 17.875 | 0.260 | 0.184 | 0.587 | 0.507 | 0.936 | 0.395 | 2.985 | 0.770 |
| s4_h1_n16 | 3 | 0.2121 ± 0.0152 | nan | 0.2082 | 18.130 | 0.248 | 0.176 | 0.569 | 0.473 | 0.942 | 0.389 | 2.965 | 0.757 |
| GFS-bilinear (reference) | | 0 | | 0 | 17.826 | 0.278 | 0.174 | 0.624 | 0.807 | 1.501 | 0.687 | 6.412 | 1.863 |

Noise floor 0.0077; configs within it of the best: s4_h14_n16, s4_h3_n16, s4_h10_n16, s4_h7_n16. **Selected: s4_h3_n16** (cheapest within the floor).


## Sprint 5 — spatial context (H=7; N=16 row shared with Sprint 4)

| config | seeds | val CSS (mean ± sd) | val CSS +precipQM | test CSS | precip_wet_mae | precip_csi15 | precip_csi30 | precip_fss15 | precip_bias_ratio | tmax_mae | tmin_mae | rh_mae | wind_vec_rmse |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| s5_h7_n20 | 2 | 0.2265 ± 0.0253 | 0.2521 | 0.2390 | 17.618 | 0.267 | 0.200 | 0.601 | 0.531 | 0.930 | 0.406 | 2.975 | 0.756 |
| s5_h7_n28 | 2 | 0.2235 ± 0.0131 | 0.2479 | 0.2385 | 17.808 | 0.266 | 0.199 | 0.601 | 0.514 | 0.936 | 0.391 | 3.079 | 0.752 |
| **s4_h7_n16** | 3 | 0.2203 ± 0.0012 | nan | 0.2304 | 17.785 | 0.258 | 0.183 | 0.588 | 0.502 | 0.934 | 0.402 | 2.965 | 0.761 |
| s5_h7_n40 | 2 | 0.2176 ± 0.0036 | nan | 0.2401 | 17.889 | 0.249 | 0.182 | 0.570 | 0.519 | 0.909 | 0.398 | 2.989 | 0.760 |
| s5_h7_n24 | 2 | 0.2158 ± 0.0036 | nan | 0.2360 | 17.894 | 0.255 | 0.185 | 0.581 | 0.497 | 0.930 | 0.397 | 3.091 | 0.755 |
| s5_h7_n32 | 2 | 0.2154 ± 0.0053 | nan | 0.2408 | 17.980 | 0.253 | 0.182 | 0.578 | 0.507 | 0.928 | 0.397 | 3.039 | 0.753 |
| GFS-bilinear (reference) | | 0 | | 0 | 17.826 | 0.278 | 0.174 | 0.624 | 0.807 | 1.501 | 0.687 | 6.412 | 1.863 |

Noise floor 0.0120; configs within it of the best: s5_h7_n20, s5_h7_n28, s4_h7_n16, s5_h7_n40, s5_h7_n24, s5_h7_n32. **Selected: s4_h7_n16** (cheapest within the floor).


## Sprint 4/5 confirmation — 100-epoch schedule (H, N)

_no results yet for ('s45_confirm', 's9_dense_S')_


## Sprint 6 — deterministic vs diffusion

_no results yet for ('s6_', 's9_dense_S')_


## Sprint 9 — capacity and MoE

_no results yet for s9__
