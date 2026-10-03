# Feasibility: adapting the v3 system to SIH PS 26086 (monsoon onset / break outlook, 1–4 weeks, panchayat scale)

Measured 2026-10-04 on Mandya's 234 gram panchayats, 2015–2023 (9 monsoon seasons). Script:
`scripts/feasibility_ps26086.py`; numbers in `results/feasibility_ps26086*.json`.

## 1. Data we can actually get

| need | source | status |
|---|---|---|
| NWP days 1–7 | GFS 0.25° (in the v3 dataset) | have |
| NWP days 8–16 | GFS 0.25° f174–f384: NCAR ds084.1 (2015–20, verified to f384), AWS (2021–23, verified f384) | downloadable (≈ the original 7-day fetch again; Kaggle CPU sessions, no GPU quota) |
| NWP weeks 3–4 | none in these archives (would need S2S/CFSv2 extended-range; access and volume are a separate project) | not available |
| MJO | NOAA PSL OMI index, daily (BoM RMM blocks automated access, not used) | have |
| ENSO | CPC weekly Niño 3.4 anomaly | have |
| IOD | HadISST DMI, monthly | have |
| observed rain | CHIRPS 0.05° daily (targets) Jun 1 – Oct 6 | have; May (pre-onset) needs a small CHIRPS download |

## 2. How much predictability is there? (Brier skill vs climatology, leave-one-season-out, 90 % season-bootstrap CI)

Events per panchayat and forecast week: **dry week** = all 7 days < 2.5 mm (break / dry spell), **wet week** = weekly
total ≥ 1.5 × the panchayat's climatology for that calendar week, **heavy week** = any day ≥ 30 mm.

| event | week 1 | week 2 | week 3 | week 4 |
|---|---|---|---|---|
| wet week, v3 week-1 forecast + indices | **0.27** [0.16, 0.34] | – | – | – |
| wet week, ENSO + IOD | 0.09 [0.03, 0.14] | **0.09** [0.03, 0.14] | **0.10** [0.05, 0.14] | 0.06 [0.02, 0.10] |
| dry week, v3 + indices | 0.09 [−0.00, 0.18] | – | – | – |
| dry week, MJO only | 0.08 [−0.02, 0.16] | **0.08** [0.01, 0.15] | 0.07 [−0.01, 0.13] | 0.07 [0.01, 0.13] |
| dry week, ENSO + IOD | < 0 | < 0 | < 0 | < 0 |
| heavy week (any predictor) | ≈ 0 | < 0 | < 0 | < 0 |

Reading:
* **Week 1** is where the skill is (the downscaled GFS): wet-week BSS 0.27.
* **Weeks 2–4** have a small, physically sensible signal: the **MJO** predicts breaks (dry weeks) and **ENSO/IOD**
  predict seasonal wetness, each worth ~0.06–0.10 BSS. Mixing all indices into one model dilutes both, so the
  extended-range model must be event-specific. With 9 seasons the CIs are wide; the ENSO/IOD part is partly a
  "wet season vs dry season" signal learned from 8 seasons.
* **Heavy downpours** are not predictable beyond climatology at panchayat scale with these data, beyond week 1.
* **Onset** cannot be validated: 9 onsets per location, and the dataset starts on 1 June (Mandya's onset is often
  early June). Onset can be *derived* from the weekly wet/dry probabilities (first wet week after a dry run), but its
  skill cannot be demonstrated honestly with 9 events.

## 3. What a PS 26086 version would be

| horizon | model | expected skill |
|---|---|---|
| days 1–7 | shipped v3 (unchanged): probabilities from the diffusion ensemble | measured (above) |
| days 8–14 | **v3 retrained with 16-day GFS input** (rain only for days 8–16), + MJO as an extra input | to be measured; GFS week 2 adds skill over week-2 indices-only (0.09–0.12) only if GFS week 2 is skilful here |
| days 15–28 | **statistical layer**: event-specific logistic models on the panchayat's climatology + MJO (breaks) / ENSO+IOD (wetness) + the v3 days 8–14 outlook | BSS ≈ 0.05–0.10 (measured above) |
| onset | derived from the weekly probabilities + the season's rain so far | not validatable with 9 seasons |
| advisories | the existing rule engine (Kannada/English), extended with break-aware rules (delay sowing, protective irrigation) | – |

## 4. Cost against the remaining GPU budget (≈ 92 GPU-h until the quota reset on Sat 10 Oct 05:30 IST)

| step | GPU-h | wall time |
|---|---|---|
| GFS days 8–16 + May inits + CHIRPS extension (Kaggle CPU sessions) | 0 | ~6–10 h |
| rebuild the dataset (16 leads, May–Sep inits) | 0 (laptop) | ~2 h |
| model change: 16 lead days (day-embedding table, rain-only loss for days 8–16, MJO input) + audit | 0 | ~2 h |
| full pipeline × 3 seeds (folds, final, OOF, diffusion, calibration) at ~1.5× cost per epoch | ~30–35 | ~6–8 h |
| statistical weeks 3–4 layer + onset derivation (CPU) | 0 | ~3 h |
| greenfield PS 26086 frontend (risk maps per week, onset/break timeline, advisories, SMS/WhatsApp text preview) | 0 | ~4–6 h |
| **total** | **≈ 35 of 92** | **≈ 2–3 days** |

## 5. Verdict

Feasible within the remaining quota, with an honest scope: a strong week-1, a retrained week-2, and a weeks-3–4 layer
that is only modestly better than climatology (and says so). Not achievable with these data: reliable onset-date
prediction or heavy-rain probabilities beyond week 1 at panchayat scale. The main risks are the 16-day GFS download
(time, not money) and that GFS week 2 may add little over the MJO/ENSO/IOD baseline here.
