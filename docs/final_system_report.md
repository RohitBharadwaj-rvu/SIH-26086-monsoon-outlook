# SIH-26074 final system — Sprint 10 report

GFS 0.25° → 0.05° downscaling over 11–15°N, 74–78°E, 7 daily leads × 6 variables (precipitation, Tmax, Tmin, RH,
U, V). All numbers below are on the **2023 monsoon test season** (Jun–Sep, 122 forecasts), which no model,
calibration fit or selection decision used. CSS = composite skill vs GFS-bilinear (higher is better; for
ensembles, the ensemble mean). Tie rule: 1 SE of the paired difference.

## 1. The shipped system

* **Backbone (FAST):** spatiotemporal transformer, S size with an MoE FFN (8 experts, top-2, MoE in 50 % of
  blocks), history H = 3 days, context N = 40 coarse cells (N/M = 2.5), trained 2015–2022, 50 epochs, no mm-loss.
  Rain quantile mapping per lead and 5×5 block, fitted on the multi-season out-of-fold predictions (2015–2022).
* **Generative stage (BALANCED / ACCURATE / ENSEMBLE):** CorrDiff-style residual diffusion (S denoiser,
  v-prediction, cosine schedule, 80 epochs) trained on **cross-fitted** residuals: every training season's
  residual comes from a deterministic model that never saw that season. Sampled with DPM-Solver++(2M), then
  mean-preserving spread calibration per lead × variable, fitted on 2022 by a model trained without 2022.
* **Mode settings** (pre-registered from Sprint 7/8 validation before the 2023 grid was run): FAST = 1 member;
  BALANCED = 16 steps × 8 members; ACCURATE = 32 × 8; ENSEMBLE = 24 × 16.
* Entry point: `sihv3.predict.FinalDownscaler("models/final").predict(history, forecast, mode=...)`.

## 2. Seed selection (out-of-fold, 2023 not used) and 3-seed spread

| seed | OOF CSS 2015–22 (selection score) | final det test CSS | + rain QM | cross-fitted diffusion test CSS | rain CRPS | rain SSR |
|---|---|---|---|---|---|---|
| 0 **(shipped)** | 0.2472 | 0.2361 | 0.2488 | 0.2814 | 4.431 | 1.11 |
| 1 | 0.2432 | 0.2205 | 0.2363 | _pending_ | _pending_ | _pending_ |
| 2 | 0.2428 | 0.2484 | 0.2626 | _pending_ | _pending_ | _pending_ |

Seed 0 has the best OOF score but the seeds are tied within noise (paired season SE ≈ 0.004–0.006).
The spread across seeds in the test column is the honest uncertainty of any single shipped model.

## 3. Cross-fitted vs in-sample residual diffusion (seed 0, final recipe)

| diffusion trained on | test CSS | rain CRPS | rain SSR | rain cov90 | rain bias | CSI30 |
|---|---|---|---|---|---|---|
| in-sample residuals (standard) | 0.2613 | 5.504 | 0.42 | 0.36 | 0.81 | 0.205 |
| **cross-fitted residuals (shipped)** | 0.2814 | 4.431 | 1.11 | 0.48 | 0.91 | 0.192 |

## 4. Capacity under the final recipe (deterministic, H3 N40, 50 ep, 2015–22)

| model | params (active) | test CSS | + rain QM | final train loss |
|---|---|---|---|---|
| dense S | 17.7M (17.7M) | 0.2443 | 0.2570 | 0.034 |
| dense M | 34.2M (34.2M) | 0.2355 | 0.2479 | 0.030 |
| dense L | | _pending_ | | |
| MoE S, seed 0 (shipped) | 28.8M (19.3M) | 0.2361 | 0.2488 | 0.057 |
| MoE S, seed 1 | 28.8M (19.3M) | 0.2205 | 0.2363 | 0.057 |
| MoE S, seed 2 | 28.8M (19.3M) | 0.2484 | 0.2626 | 0.058 |

MoE train losses include the Switch balance term (0.01 × ≈1 per MoE layer × 3 layers ≈ 0.03), i.e. a data loss
of ≈ 0.027: the MoE and the larger dense models fit the 8 training seasons *better* than dense S, but test skill
is flat within the seed spread (±0.014). Capacity is data-limited at this training-set size, not broken.

## 5. Operating modes (2023 test)

| mode | setting | CSS | rain CRPS | rain SSR | Brier>30 | Tmax CRPS | rain bias | latency s/forecast (T4, batch 1) | peak VRAM GB |
|---|---|---|---|---|---|---|---|---|---|
| FAST | det + rain QM | _pending_ |
| FAST (no QM) | det only | _pending_ |
| BALANCED | 16 steps × 8 | _pending_ |
| ACCURATE | 32 steps × 8 | _pending_ |
| ENSEMBLE | 24 steps × 16 | _pending_ |

## 6. Test-time compute matrix (spread-calibrated; cell = CSS / rain CRPS / latency s)

_pending_

## 7. Multivariate physical consistency (per member; observed = ERA5-Land/CHIRPS targets)

_pending_
