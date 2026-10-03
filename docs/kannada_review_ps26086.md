# Kannada advisory review sheet (PS 26086)

The advisory texts below were drafted without a native-speaker review. Before any field use, a Kannada-speaking agronomist (KVK / UAS Bangalore) should check each one for:
* accuracy;
* farmer-friendly vocabulary, using local crop names and Mandya usage;
* SMS length.

Placeholders such as `{p}` (probability) and `{wk_kn}` (week) are filled at issue time.

Advisories fire at these probability thresholds (`outlook/advisory.py`, THRESH):
`{'onset_soon': 0.45, 'false_risk': 0.45, 'delayed': 0.3, 'break': 0.65, 'break_red': 0.8, 'dry_week': 0.45, 'heavy_week': 0.2, 'wet_week': 0.45, 'el_nino': 0.8, 'pos_iod': 0.4}`

### `false_onset` (level: red)

| | Text |
|---|---|
| English | False-onset risk {p}: first rains may be followed by a dry spell. Do not sow on the first showers; wait for a second wet spell or sow only where protective irrigation is available. |
| ಕನ್ನಡ | ಸುಳ್ಳು ಮುಂಗಾರು ಅಪಾಯ {p}: ಮೊದಲ ಮಳೆಯ ನಂತರ ಒಣ ಹವೆ ಬರಬಹುದು. ಮೊದಲ ಮಳೆಗೆ ಬಿತ್ತನೆ ಮಾಡಬೇಡಿ; ಎರಡನೇ ಮಳೆಗಾಗಿ ಕಾಯಿರಿ ಅಥವಾ ನೀರಾವರಿ ಇದ್ದರೆ ಮಾತ್ರ ಬಿತ್ತಿ. |
| Reviewer: correct? (Y/N) | |
| Reviewer: suggested wording | |

### `onset_soon` (level: green)

| | Text |
|---|---|
| English | Monsoon onset likely within 2 weeks ({p}). Prepare land and seed; sow after 20 mm of rain over two days. |
| ಕನ್ನಡ | 2 ವಾರಗಳಲ್ಲಿ ಮುಂಗಾರು ಆರಂಭ ಸಾಧ್ಯತೆ ({p}). ಭೂಮಿ ಮತ್ತು ಬೀಜ ಸಿದ್ಧಪಡಿಸಿ; ಎರಡು ದಿನದಲ್ಲಿ 20 ಮಿಮೀ ಮಳೆಯಾದ ನಂತರ ಬಿತ್ತನೆ ಮಾಡಿ. |
| Reviewer: correct? (Y/N) | |
| Reviewer: suggested wording | |

### `delayed_onset` (level: amber)

| | Text |
|---|---|
| English | Onset unlikely in the next 4 weeks ({p}). Keep paddy nursery and seed ready; plan short-duration varieties if sowing slips. |
| ಕನ್ನಡ | ಮುಂದಿನ 4 ವಾರಗಳಲ್ಲಿ ಮುಂಗಾರು ಆರಂಭ ಸಾಧ್ಯತೆ ಕಡಿಮೆ ({p}). ಸಸಿಮಡಿ ಮತ್ತು ಬೀಜ ಸಿದ್ಧವಿಡಿ; ತಡವಾದರೆ ಅಲ್ಪಾವಧಿ ತಳಿಗಳನ್ನು ಆರಿಸಿ. |
| Reviewer: correct? (Y/N) | |
| Reviewer: suggested wording | |

### `break` (level: amber)

| | Text |
|---|---|
| English | Dry spell of a week or more likely in the next 3 weeks ({p}). Postpone fertilizer top dressing and paddy transplanting; mulch and plan protective irrigation. |
| ಕನ್ನಡ | ಮುಂದಿನ 3 ವಾರಗಳಲ್ಲಿ ಒಂದು ವಾರಕ್ಕಿಂತ ಹೆಚ್ಚು ಒಣ ಹವೆ ಸಾಧ್ಯತೆ ({p}). ಮೇಲುಗೊಬ್ಬರ ಮತ್ತು ನಾಟಿಯನ್ನು ಮುಂದೂಡಿ; ಹೊದಿಕೆ ಹಾಕಿ, ರಕ್ಷಣಾತ್ಮಕ ನೀರಾವರಿಗೆ ಸಿದ್ಧರಾಗಿ. |
| Reviewer: correct? (Y/N) | |
| Reviewer: suggested wording | |

### `heavy` (level: amber)

| | Text |
|---|---|
| English | Heavy rain (30 mm+ in a day) possible {wk_en} ({p}). Clear field drains; avoid spraying and fertilizer just before; protect harvested produce. |
| ಕನ್ನಡ | {wk_kn} ಭಾರಿ ಮಳೆ (ದಿನಕ್ಕೆ 30 ಮಿಮೀ+) ಸಾಧ್ಯತೆ ({p}). ಹೊಲದ ಕಾಲುವೆ ಸ್ವಚ್ಛಗೊಳಿಸಿ; ಸಿಂಪರಣೆ ಮತ್ತು ಗೊಬ್ಬರ ಹಾಕಬೇಡಿ; ಕೊಯ್ಲಾದ ಬೆಳೆಯನ್ನು ರಕ್ಷಿಸಿ. |
| Reviewer: correct? (Y/N) | |
| Reviewer: suggested wording | |

### `good_window` (level: green)

| | Text |
|---|---|
| English | Good soil-moisture window this week (wet week {p}). Suitable for paddy transplanting and top dressing. |
| ಕನ್ನಡ | ಈ ವಾರ ಮಣ್ಣಿನ ತೇವಾಂಶ ಉತ್ತಮ ({p}). ಭತ್ತ ನಾಟಿ ಮತ್ತು ಮೇಲುಗೊಬ್ಬರಕ್ಕೆ ಸೂಕ್ತ ಸಮಯ. |
| Reviewer: correct? (Y/N) | |
| Reviewer: suggested wording | |

### `el_nino` (level: amber)

| | Text |
|---|---|
| English | El Niño conditions (Niño 3.4 {enso}) without a compensating positive IOD: below-normal rain risk this season. Prefer drought-tolerant ragi and pulses over water-intensive paddy where water is uncertain. |
| ಕನ್ನಡ | ಎಲ್ ನಿನೊ ಸ್ಥಿತಿ (ನಿನೊ 3.4 {enso}): ಈ ಹಂಗಾಮಿನಲ್ಲಿ ಕಡಿಮೆ ಮಳೆ ಅಪಾಯ. ನೀರು ಖಚಿತವಿಲ್ಲದ ಕಡೆ ಭತ್ತದ ಬದಲು ರಾಗಿ ಮತ್ತು ದ್ವಿದಳ ಧಾನ್ಯ ಬೆಳೆಯಿರಿ. |
| Reviewer: correct? (Y/N) | |
| Reviewer: suggested wording | |

### `normal` (level: green)

| | Text |
|---|---|
| English | No major risk in the next 4 weeks. Continue normal field operations. |
| ಕನ್ನಡ | ಮುಂದಿನ 4 ವಾರಗಳಲ್ಲಿ ದೊಡ್ಡ ಅಪಾಯವಿಲ್ಲ. ಸಾಮಾನ್ಯ ಕೃಷಿ ಕೆಲಸ ಮುಂದುವರಿಸಿ. |
| Reviewer: correct? (Y/N) | |
| Reviewer: suggested wording | |

