# SIH-26074 — Spatiotemporal diffusion downscaling, v3 (real data)

Fresh research repo for Sprint 10 preparation. Re-runs every sprint question of the
[original plan](https://github.com/rohzhegde26/SIH-26074-Fast-and-Curious/blob/feat/spatiotemporal-diffusion-downscaler/docs/plans/sprint_wise_implementation_plan.md)
on a rebuilt dataset that uses only genuine sources (see `docs/audit_previous_sprints.md`).

* `data_pipeline/` — real GFS fetch (AWS + NCAR), ERA5 (NCAR ds633.0) and ERA5-Land (CDS) fetchers, v3 dataset builder
* `sihv3/` — spatiotemporal transformer (deterministic, residual diffusion, MoE), data loader, metrics, trainer
* `kaggle/` — multi-account launcher (2 runs per T4x2 session) and live dashboard
* `docs/` — audit, improved sprint plan, selection criteria, decision log
* `results/` — per-job result JSON and logs
