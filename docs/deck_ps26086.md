# PS 26086 deck: slide content (draft for the SIH template)

Placeholders in [brackets] are for the team to fill in. Every number comes from `docs/results_ps26086.md`.

---

## 1. Title
* **Problem statement:** SIH PS 26086. Hyperlocal Monsoon Onset & Break Prediction System (MoES / NCMRWF)
* **Solution:** Monsoon Outlook, a panchayat-level 1–4 week monsoon outlook with farmer advisories [rename freely]
* **Team:** [team name] · [team ID] · [institute]
* **Theme / category:** [as per SIH portal]

## 2. Proposed solution
* **What it is:** a probabilistic monsoon outlook for every gram panchayat (234 in Mandya district, Karnataka), issued daily from 1 May to 30 September, covering the next 1–4 weeks.
* **What it forecasts:** onset week, false-onset risk, dry spells (≥ 7 days), dry weeks, wet weeks and heavy-rain days.
* **How it turns into advice:** an expert-system engine converts the probabilities into ranked, crop-specific advisories in Kannada and English. They reach farmers through the mobile web app and as SMS / WhatsApp text (gateway in dry-run mode).
* **Who uses it:**
  * Farmers: the panchayat card.
  * Agriculture officers: the block risk map and the advisory dispatch queue.
  * Scientists: the ML view.
* **What makes it different:**
  * It is honest about skill: every event is validated on seasons the models never saw, and the app shows what it can and cannot forecast.
  * Probabilities are calibrated: a 70 % forecast happens about 70 % of the time (shown in the app).

## 3. Technical approach
**Pipeline:** data → models → selection → advisories → delivery.
* **Climate drivers:**
  * real-time MJO (NOAA ROMI) and BSISO
  * ENSO (weekly Niño 3.4)
  * IOD (DMI)
* **Observations:** CHIRPS 0.05° daily rain, 1981–2023, area-weighted to each panchayat polygon.
* **Sub-seasonal outlook:** 18 regularised logistic models (event × week), with MJO/BSISO × season interactions. Validated by 9-fold season-blocked cross-validation over 43 monsoons.
* **Weather-model hybrids** (stackers on top of the outlook):
  * NOAA GEFSv12, 11 members, weeks 1–4; quantile-mapped to local rain, with event definitions applied to each member.
  * GFS 0.25°, days 1–16.
  * Our v3 deep-learning downscaling model: spatiotemporal transformer + residual diffusion, 0.25° → 0.05°, 16-member ensemble.
* **Selection rule, fixed in advance:** a hybrid replaces the outlook only if it beats it on held-out seasons AND its 90 % confidence interval is above zero.
* **Delivery:** static web app (map, panchayat card, officer view, ML view), a CLI that issues a full outlook for any date, and SMS / WhatsApp text builder.
* **Stack:** Python (scikit-learn, PyTorch), Kaggle GPU/CPU, vanilla JS + Leaflet.

## 4. Results (validated skill)
Brier skill score vs climatology; 0 = no better than the long-term average.

| Event | Week 1 | Week 2 | Week 3 | Week 4 |
|---|---|---|---|---|
| Dry week | **0.16** | **0.15** | **0.08** | **0.06** |
| Wet week | **0.23** | 0.03 | – | – |
| Dry spell (≥ 7 days) within 3 weeks | **0.08** | | | |
| False onset within 3 weeks | **0.06** | | | |

* **How it was tested:**
  * The GEFS hybrid was trained on 20 reforecast seasons (2000–2019), then tested unchanged on real 2021–2023 operational forecasts; the gains held.
  * Reliability: calibration gap 1–2 % for dry weeks.
* **Honest limits:**
  * Heavy-rain days and onset timing in weeks 1–3 show no reliable skill.
  * The app therefore caps heavy-rain alerts at amber and presents onset messages as guidance.

## 5. Feasibility & viability
* **Runs on public data only:** NOAA GEFS/GFS (AWS), NOAA PSL MJO, CHIRPS and the BSISO index. It needs no proprietary feeds. IMD gridded rain or NCMRWF NEPS can replace them.
* **Cheap to run:**
  * The outlook and hybrids run on CPU in minutes per day for a district.
  * The v3 ensemble needs one GPU for under 10 seconds per district per day (a full season of 122 days took 15 minutes on a T4).
* **Scaling:** any district, once the panchayat polygons are added; the models retrain per region from CHIRPS / IMD.
* **Risks and mitigations:**
  * Skill varies by season and region: validation and the "can / cannot" panel are part of the product.
  * Advisory wording: Kannada texts are to be reviewed with KVK / UAS agronomists.
  * Connectivity: SMS fallback.

## 6. Impact & benefits
* **Farmers:** sowing after confirmed onset, not on false-start rains (false-onset risk 3 weeks ahead); top-dressing and irrigation timed around dry spells forecast 1–4 weeks ahead.
* **Officers:** a block-level risk map and dispatch queue (red / amber / green) for advisories.
* **Scientists / IMD:** a transparent, reproducible evaluation (43 + 20 + 9 seasons, independent operational test, reliability) that other districts can reuse.
* **Economic case:** fewer re-sowings after false starts and better-timed inputs [add a cost-per-hectare estimate if the team has one].

## 7. References
* NOAA PSL Real-time OMI (ROMI); Kikuchi et al. BSISO index; NOAA Niño 3.4 weekly; JAMSTEC/NOAA DMI.
* Funk et al. 2015, CHIRPS; Hamill et al. 2022, GEFSv12 reforecast.
* Marteau et al. 2009 (agronomic onset definition); IMD dry-day definition (< 2.5 mm).
* Code and results: github.com/RohitBharadwaj-rvu/SIH-26074-downscaling-v3 (`outlook/`, `monsoon/`, `docs/results_ps26086.md`).

## Visuals to place
* App screenshots: panchayat card (Kannada), risk map, officer dispatch queue, ML view (can/cannot panel + reliability grid).
* Pipeline diagram (slide 3).
* Skill table or bars (slide 4).
