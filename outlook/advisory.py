"""
Expert-system engine for PS 26086: turns a panchayat's 4-week outlook into crop-specific agronomic advisories
(English + Kannada) and short SMS / WhatsApp texts.

Input per panchayat and issue date:
  p          dict of probabilities: onset_1..4, false3w, break3w, dry_1..4, wet_1..4, heavy_1..4
  onset_seen True if the season's onset has already been observed at this panchayat
  enso       latest weekly Nino 3.4 anomaly (C), iod = latest DMI
  month      issue month (crop calendar)
Output: list of advisories {id, level (red/amber/green), week, crops, en, kn}, plus sms_en / sms_kn / whatsapp.

Thresholds are explicit and documented (THRESH) so agronomists can tune them; every rule cites the probabilities that
triggered it. Kannada texts are short, plain sentences for SMS (review by a native agronomist recommended).
"""
from __future__ import annotations

# Alert only when risk is clearly above its normal frequency (1981-2023 base rates: break 0.54, false onset 0.32,
# dry week 0.18, wet week 0.24, heavy week 0.06-0.09)
THRESH = {"onset_soon": 0.45, "false_risk": 0.45, "delayed": 0.30, "break": 0.65, "break_red": 0.80, "dry_week": 0.45,
          "heavy_week": 0.20, "wet_week": 0.45, "el_nino": 0.8, "pos_iod": 0.4}

WEEK_KN = {1: "ಈ ವಾರ", 2: "ಮುಂದಿನ ವಾರ", 3: "3ನೇ ವಾರ", 4: "4ನೇ ವಾರ"}
WEEK_EN = {1: "this week", 2: "next week", 3: "in week 3", 4: "in week 4"}


TEMPLATES = {
    "false_onset": {"level": "red", "crops": ["ragi", "paddy", "pulses"],
        "en": "False-onset risk {p}: first rains may be followed by a dry spell. Do not sow on the first showers; wait for a second wet spell or sow only where protective irrigation is available.",
        "kn": "ಸುಳ್ಳು ಮುಂಗಾರು ಅಪಾಯ {p}: ಮೊದಲ ಮಳೆಯ ನಂತರ ಒಣ ಹವೆ ಬರಬಹುದು. ಮೊದಲ ಮಳೆಗೆ ಬಿತ್ತನೆ ಮಾಡಬೇಡಿ; ಎರಡನೇ ಮಳೆಗಾಗಿ ಕಾಯಿರಿ ಅಥವಾ ನೀರಾವರಿ ಇದ್ದರೆ ಮಾತ್ರ ಬಿತ್ತಿ."},
    "onset_soon": {"level": "green", "crops": ["ragi", "paddy", "pulses"],
        "en": "Monsoon onset likely within 2 weeks ({p}). Prepare land and seed; sow after 20 mm of rain over two days.",
        "kn": "2 ವಾರಗಳಲ್ಲಿ ಮುಂಗಾರು ಆರಂಭ ಸಾಧ್ಯತೆ ({p}). ಭೂಮಿ ಮತ್ತು ಬೀಜ ಸಿದ್ಧಪಡಿಸಿ; ಎರಡು ದಿನದಲ್ಲಿ 20 ಮಿಮೀ ಮಳೆಯಾದ ನಂತರ ಬಿತ್ತನೆ ಮಾಡಿ."},
    "delayed_onset": {"level": "amber", "crops": ["ragi", "paddy"],
        "en": "Onset unlikely in the next 4 weeks ({p}). Keep paddy nursery and seed ready; plan short-duration varieties if sowing slips.",
        "kn": "ಮುಂದಿನ 4 ವಾರಗಳಲ್ಲಿ ಮುಂಗಾರು ಆರಂಭ ಸಾಧ್ಯತೆ ಕಡಿಮೆ ({p}). ಸಸಿಮಡಿ ಮತ್ತು ಬೀಜ ಸಿದ್ಧವಿಡಿ; ತಡವಾದರೆ ಅಲ್ಪಾವಧಿ ತಳಿಗಳನ್ನು ಆರಿಸಿ."},
    "break": {"level": "amber", "crops": ["ragi", "paddy", "sugarcane"],
        "en": "Dry spell of a week or more likely in the next 3 weeks ({p}). Postpone fertilizer top dressing and paddy transplanting; mulch and plan protective irrigation.",
        "kn": "ಮುಂದಿನ 3 ವಾರಗಳಲ್ಲಿ ಒಂದು ವಾರಕ್ಕಿಂತ ಹೆಚ್ಚು ಒಣ ಹವೆ ಸಾಧ್ಯತೆ ({p}). ಮೇಲುಗೊಬ್ಬರ ಮತ್ತು ನಾಟಿಯನ್ನು ಮುಂದೂಡಿ; ಹೊದಿಕೆ ಹಾಕಿ, ರಕ್ಷಣಾತ್ಮಕ ನೀರಾವರಿಗೆ ಸಿದ್ಧರಾಗಿ."},
    "heavy": {"level": "amber", "crops": ["ragi", "paddy", "sugarcane"],
        "en": "Heavy rain (30 mm+ in a day) possible {wk_en} ({p}). Clear field drains; avoid spraying and fertilizer just before; protect harvested produce.",
        "kn": "{wk_kn} ಭಾರಿ ಮಳೆ (ದಿನಕ್ಕೆ 30 ಮಿಮೀ+) ಸಾಧ್ಯತೆ ({p}). ಹೊಲದ ಕಾಲುವೆ ಸ್ವಚ್ಛಗೊಳಿಸಿ; ಸಿಂಪರಣೆ ಮತ್ತು ಗೊಬ್ಬರ ಹಾಕಬೇಡಿ; ಕೊಯ್ಲಾದ ಬೆಳೆಯನ್ನು ರಕ್ಷಿಸಿ."},
    "good_window": {"level": "green", "crops": ["paddy", "ragi"],
        "en": "Good soil-moisture window this week (wet week {p}). Suitable for paddy transplanting and top dressing.",
        "kn": "ಈ ವಾರ ಮಣ್ಣಿನ ತೇವಾಂಶ ಉತ್ತಮ ({p}). ಭತ್ತ ನಾಟಿ ಮತ್ತು ಮೇಲುಗೊಬ್ಬರಕ್ಕೆ ಸೂಕ್ತ ಸಮಯ."},
    "el_nino": {"level": "amber", "crops": ["ragi", "paddy", "pulses"],
        "en": "El Niño conditions (Niño 3.4 {enso}) without a compensating positive IOD: below-normal rain risk this season. Prefer drought-tolerant ragi and pulses over water-intensive paddy where water is uncertain.",
        "kn": "ಎಲ್ ನಿನೊ ಸ್ಥಿತಿ (ನಿನೊ 3.4 {enso}): ಈ ಹಂಗಾಮಿನಲ್ಲಿ ಕಡಿಮೆ ಮಳೆ ಅಪಾಯ. ನೀರು ಖಚಿತವಿಲ್ಲದ ಕಡೆ ಭತ್ತದ ಬದಲು ರಾಗಿ ಮತ್ತು ದ್ವಿದಳ ಧಾನ್ಯ ಬೆಳೆಯಿರಿ."},
    "normal": {"level": "green", "crops": ["ragi", "paddy", "sugarcane"],
        "en": "No major risk in the next 4 weeks. Continue normal field operations.",
        "kn": "ಮುಂದಿನ 4 ವಾರಗಳಲ್ಲಿ ದೊಡ್ಡ ಅಪಾಯವಿಲ್ಲ. ಸಾಮಾನ್ಯ ಕೃಷಿ ಕೆಲಸ ಮುಂದುವರಿಸಿ."},
}


def pct(x):
    return f"{100 * x:.0f}%"


def advise(p: dict, onset_seen: bool, month: int, enso: float | None = None, iod: float | None = None) -> list:
    """-> ranked list of [id, level, week, vals]; render() turns one into text."""
    out = []
    add = lambda i, wk, lvl=None, **vals: out.append([i, lvl or TEMPLATES[i]["level"], wk, vals])
    onset4 = 1 - (1 - p["onset_1"]) * (1 - p["onset_2"]) * (1 - p["onset_3"]) * (1 - p["onset_4"])
    onset2 = 1 - (1 - p["onset_1"]) * (1 - p["onset_2"])
    if not onset_seen and month <= 8:
        if p["false3w"] >= THRESH["false_risk"]:
            add("false_onset", 1, p=pct(p["false3w"]))
        if onset2 >= THRESH["onset_soon"] and p["false3w"] < THRESH["false_risk"]:
            add("onset_soon", 1, p=pct(onset2))
        elif onset4 < THRESH["delayed"]:
            add("delayed_onset", 4, p=pct(onset4))
    if p["break3w"] >= THRESH["break"]:
        add("break", 2, "red" if p["break3w"] >= THRESH["break_red"] else "amber", p=pct(p["break3w"]))
    for k in (1, 2, 3, 4):                     # amber only: heavy-rain days show no validated skill over climatology
        if p[f"heavy_{k}"] >= THRESH["heavy_week"]:
            add("heavy", k, "amber", p=pct(p[f"heavy_{k}"]), wk_en=WEEK_EN[k], wk_kn=WEEK_KN[k])
            break
    if onset_seen and p["dry_1"] < THRESH["dry_week"] and p["wet_1"] >= THRESH["wet_week"] and p["break3w"] < THRESH["break"]:
        add("good_window", 1, p=pct(p["wet_1"]))
    if enso is not None and enso >= THRESH["el_nino"] and (iod is None or iod < THRESH["pos_iod"]) and month <= 7:
        add("el_nino", 4, enso=f"{enso:+.1f}°C")
    if not out:
        add("normal", 1)
    order = {"red": 0, "amber": 1, "green": 2}
    out.sort(key=lambda a: (order[a[1]], a[2]))
    return out


def render(a, lang="en"):
    return TEMPLATES[a[0]][lang].format(**a[3])


def sms(text: str, n: int) -> str:
    """First sentence(s) that fit in one SMS (160 GSM chars; Kannada is UCS-2 so a 2-part 140-char budget)."""
    if len(text) <= n:
        return text
    cut = text[:n]
    k = max(cut.rfind(". "), cut.rfind("; "), cut.rfind(": "))
    return (cut[:k + 1] if k > 40 else cut[:n - 1] + "…").strip()


if __name__ == "__main__":
    demo = {"onset_1": 0.1, "onset_2": 0.25, "onset_3": 0.15, "onset_4": 0.1, "false3w": 0.42, "break3w": 0.55,
            "dry_1": 0.3, "dry_2": 0.5, "dry_3": 0.3, "dry_4": 0.2, "wet_1": 0.2, "wet_2": 0.1, "wet_3": 0.2, "wet_4": 0.25,
            "heavy_1": 0.05, "heavy_2": 0.25, "heavy_3": 0.04, "heavy_4": 0.03}
    for a in advise(demo, onset_seen=False, month=6, enso=1.1, iod=0.1):
        print(a[1], a[0], "|", render(a)[:90], "|", sms(render(a, "kn"), 140)[:60])
