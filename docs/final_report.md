# SIH-26074 — Sprint 1-9 re-run on real data: findings for Sprint 10

_Draft, filled in as results arrive. Numbers: validation season 2022 (decisions); test season 2023 shown for
reference only. CSS = Composite Skill Score vs GFS-bilinear (0 = raw GFS interpolated, 1 = perfect); see
`selection_criteria.md`. Full tables: `results.md`, `results_s7_s8.md`. Every decision: `decision_log.md`._

## 0. Why everything was re-run

The original Sprints 3-9 trained on a dataset whose "GFS forecast" was noisy ground truth, whose Tmax/Tmin/RH
targets were not ERA5, whose wind was km/h labelled m/s, and whose "context" was edge padding (`audit_previous_sprints.md`).
v3 uses only verified sources (real GFS 0.25 deg, ERA5 via NCAR = ECMWF bit-for-bit, ERA5-Land via CDS, CHIRPS
bit-exact to UCSB), 1,096 monsoon initialisations 2015-2023, land-masked scoring, and a single spatiotemporal
transformer for all sprints (`plan_v3.md`). The v3 pipeline itself was audited (`audit_v3_code.md`).

## 1. Sprint 3 — baselines

| Model | CSS val | CSS test | Note |
|---|---|---|---|
| GFS-bilinear | 0 | 0 | reference |
| GFS + per-pixel quantile mapping | 0.189 | 0.181 | statistical bar |
| Transformer S (H=7, N=16, 50 ep) | 0.220 | 0.230 | raw; rain ~50 % of observed |
| Transformer S + precip-QM | ~0.245-0.25 | | train-fitted per-block QM |

Temperature/RH/wind are far better than both baselines (Tmax MAE 0.9 vs 1.1-1.5 C, RH 2.9 vs 3.8-6.4 %, wind 0.76
vs 1.2-1.9 m/s). Rain amount is the weak point of a deterministic model (log-space loss -> median bias).

## 2. Sprint 4 — history length

## 3. Sprint 5 — spatial context

## 4. Sprint 6 — deterministic vs residual diffusion

## 5. Sprint 7 — denoising steps and sampler

## 6. Sprint 8 — ensemble size vs denoising steps

## 7. Sprint 9 — capacity (dense S/M/L) and MoE sparsity

## 8. Recommended Sprint 10 configuration

## 9. Caveats
* One validation season (2022, wet) and one test season (2023, dry); seasons differ strongly, and longer training
  raised val but lowered test -> Sprint 10 should not tune stopping on 2022 alone.
* ~852 heavily overlapping training initialisations; larger inputs (H, N) overfit sooner.
