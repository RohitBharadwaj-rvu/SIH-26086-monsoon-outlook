# Model selection criteria

Every experiment is scored on the **2022 validation season** (122 initialisations x 7 leads, land pixels only).
The **2023 test season is never used for any decision**; it is reported once for the final candidates.

## 1. Reference forecast

All skill is measured against **GFS-bilinear**: the real 00Z GFS 0.25 deg forecast interpolated to 0.05 deg.
A model is only useful if it beats what the operational forecast already gives for free.

## 2. Composite Skill Score (CSS)

`CSS = sum_i w_i * skill_i / sum_i w_i`, with per-component skill

* error metrics (lower is better): `skill = 1 - e_model / e_ref`
* score metrics in [0,1] (higher is better): `skill = (s_model - s_ref) / (1 - s_ref)`

| Variable group | Component | Weight | Why |
|---|---|---|---|
| Precipitation (0.50) | wet-day MAE (obs > 1 mm) | 0.10 | amount error where it rains |
| | RMSE | 0.05 | penalises big misses |
| | CSI @ 5 mm | 0.05 | rain / no-rain advisory |
| | CSI @ 15 mm | 0.08 | moderate rain (spraying, harvest) |
| | CSI @ 30 mm | 0.08 | heavy rain |
| | CSI @ 64.5 mm | 0.04 | IMD "heavy rainfall" class, flood risk |
| | FSS @ 15 mm, 125 km window | 0.05 | spatial placement, tolerant of small shifts |
| | abs(log bias ratio) | 0.05 | GFS is 1.4-2.2x too wet; bias correction matters |
| Temperature (0.24) | Tmax MAE | 0.12 | heat stress |
| | Tmin MAE | 0.12 | crop night temperature |
| Humidity (0.11) | RH MAE | 0.11 | disease advisories |
| Wind (0.15) | vector RMSE | 0.15 | spraying windows |

CSS = 0 means "as good as GFS-bilinear", 1 means perfect. All components are lead-averaged (D+0..D+6).

## 3. Probabilistic models (Sprint 6 onward)

For ensembles the deterministic CSS is computed on the **ensemble mean**, and additionally:

* **CRPS skill** per variable vs a deterministic model (CRPS of a deterministic forecast = its MAE),
* **spread-skill ratio** (ideal 1.0) and **90 % interval coverage** (ideal 0.90),
* **Brier score** for P > 15 mm and P > 30 mm.

Probabilistic CSS (pCSS) replaces the MAE components with the matching CRPS components
(precip wet MAE -> precip CRPS, Tmax/Tmin/RH MAE -> CRPS), keeping all other weights.

## 4. Decision rules (robustness)

1. Every configuration is trained with **2 seeds**; decisions use the **seed mean**.
2. **Noise floor**: two configs are "tied" if their CSS difference is smaller than
   `max(0.005, 2 x pooled seed standard deviation)`.
3. **Ties go to the cheaper option** (shorter history, smaller context, fewer parameters, fewer
   sampling steps/members), because cost is real at inference time.
4. **Physical gates**: a config is rejected if Tmax < Tmin on more than 1 % of pixels, or if its precipitation
   bias ratio is worse than GFS-bilinear's.
5. **No single-variable regressions**: a winner must not be worse than the runner-up by more than 5 % on any
   CSS component; otherwise the decision is flagged in the decision log for review.
