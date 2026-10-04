import { gauge, mjoDiagram, skillBars, reliability, spark, importance } from "./charts.js";

// ------------------------------------------------------------------ i18n
const T = {
  en: {
    app_title: "Monsoon Outlook", app_sub: "Mandya · 234 panchayats · 1–4 weeks", season: "Season", issued: "Issued",
    tab_panchayat: "Panchayat", tab_map: "Risk map", tab_officer: "Officer", tab_model: "Model",
    search_ph: "Search your panchayat…", taluk: "taluk", next4: "Next 4 weeks", advice: "What to do", copy: "Copy",
    week1_rain: "This week, day by day", week1_hint: "downscaled forecast, mm", what_happened: "What actually happened",
    replay_hint: "season replay", week: "Week", drivers: "Climate drivers", blocks: "Blocks (taluks)",
    blocks_hint: "mean probability across panchayats", queue: "Advisory dispatch queue", only_red: "Red alerts",
    red_amber: "Red + amber", all_gp: "All panchayats", export_csv: "Export CSV", ml_title: "How the forecast is made",
    ml_sub: "A hybrid system: a deep downscaling model for the first week, a sub-seasonal model driven by global climate signals for weeks 1–4, and an agronomic expert system that turns probabilities into advice.",
    skill_lead: "Skill by lead week", bss_note: "Brier skill score vs climatology: 0 = no better than the long-term average, 1 = perfect. Bars show 90% confidence intervals across seasons; faded bars include zero.",
    drivers_value: "What each climate signal predicts", drivers_note: "The MJO drives breaks (dry spells) at every lead; ENSO and IOD set how wet the season runs.",
    reliability: "Reliability", v3_card: "Week 1: downscaling model", v3_hint: "2023 held-out season, per panchayat",
    v3_note: "Error of the downscaled forecast against observed rain and temperature, next to the raw 0.25° GFS forecast it starts from.",
    facts: "Data and validation", wk: "Wk", onset: "Onset", dry: "Dry week", wet: "Wet week", heavy: "Heavy rain",
    break3w: "Dry spell (7+ days) within 3 weeks", false3w: "False-onset risk", onset_started: "Monsoon started",
    onset_pending: "Monsoon not started", onset_expected: "most likely", no_onset4: "not expected within 4 weeks",
    observed: "observed", forecast: "forecast", copied: "Copied", red: "Act now", amber: "Prepare", green: "OK",
    gps_red: "panchayats with red alerts", mean_break: "mean dry-spell risk", mean_heavy: "mean heavy-rain risk (wk 1)",
    p_onset: "Onset ≤ 2 wk", reliability_wait: "Reliability curves are produced by the 43-season cross-validation.",
    el_nino: "El Niño", la_nina: "La Niña", neutral: "Neutral", pos_iod: "Positive IOD", neg_iod: "Negative IOD",
    mjo_active: "active", mjo_weak: "weak", phase: "phase", amp: "amplitude", select_gp: "Tap a panchayat for details",
    importance: "What the models rely on", importance_hint: "permutation importance on held-out seasons",
    within2: "onset within 2 wk", within4: "within 4 wk", shipped: "Validated skill of what ships", shipped_hint: "one row per event and lead",
    hybrid_note: "Each event uses the most skilful validated model: the climate-driver outlook (1981–2023), or a hybrid with the GEFS ensemble (2000–2019), GFS days 1–16 or the v3 downscaling model (2015–2023).",
  },
  kn: {
    app_title: "ಮುಂಗಾರು ಮುನ್ನೋಟ", app_sub: "ಮಂಡ್ಯ · 234 ಪಂಚಾಯಿತಿ · 1–4 ವಾರ", season: "ಹಂಗಾಮು", issued: "ಪ್ರಕಟಣೆ",
    tab_panchayat: "ಪಂಚಾಯಿತಿ", tab_map: "ಅಪಾಯ ನಕ್ಷೆ", tab_officer: "ಅಧಿಕಾರಿ", tab_model: "ಮಾದರಿ",
    search_ph: "ನಿಮ್ಮ ಪಂಚಾಯಿತಿ ಹುಡುಕಿ…", taluk: "ತಾಲ್ಲೂಕು", next4: "ಮುಂದಿನ 4 ವಾರಗಳು", advice: "ಏನು ಮಾಡಬೇಕು", copy: "ನಕಲಿಸಿ",
    week1_rain: "ಈ ವಾರ, ದಿನವಾರು", week1_hint: "ಮುನ್ಸೂಚನೆ, ಮಿಮೀ", what_happened: "ನಿಜವಾಗಿ ಆದದ್ದು",
    replay_hint: "ಹಂಗಾಮಿನ ಪುನರಾವರ್ತನೆ", week: "ವಾರ", drivers: "ಹವಾಮಾನ ಚಾಲಕಗಳು", blocks: "ತಾಲ್ಲೂಕುಗಳು",
    blocks_hint: "ಪಂಚಾಯಿತಿಗಳ ಸರಾಸರಿ ಸಂಭವನೀಯತೆ", queue: "ಸಲಹೆ ರವಾನೆ ಪಟ್ಟಿ", only_red: "ಕೆಂಪು ಎಚ್ಚರಿಕೆ",
    red_amber: "ಕೆಂಪು + ಕಿತ್ತಳೆ", all_gp: "ಎಲ್ಲಾ ಪಂಚಾಯಿತಿ", export_csv: "CSV ಡೌನ್‌ಲೋಡ್", ml_title: "ಮುನ್ಸೂಚನೆ ಹೇಗೆ ತಯಾರಾಗುತ್ತದೆ",
    ml_sub: "ಮೊದಲ ವಾರಕ್ಕೆ ಆಳ ಕಲಿಕೆಯ ಡೌನ್‌ಸ್ಕೇಲಿಂಗ್ ಮಾದರಿ, 1–4 ವಾರಗಳಿಗೆ ಜಾಗತಿಕ ಹವಾಮಾನ ಸಂಕೇತಗಳ ಉಪ-ಋತುಮಾನ ಮಾದರಿ, ಮತ್ತು ಸಂಭವನೀಯತೆಯನ್ನು ಸಲಹೆಯಾಗಿ ಬದಲಿಸುವ ಕೃಷಿ ತಜ್ಞ ವ್ಯವಸ್ಥೆ.",
    skill_lead: "ವಾರವಾರು ನಿಖರತೆ", bss_note: "ಬ್ರಿಯರ್ ಕೌಶಲ್ಯ ಅಂಕ: 0 = ದೀರ್ಘಾವಧಿ ಸರಾಸರಿಯಷ್ಟೇ, 1 = ಪರಿಪೂರ್ಣ. ಗೆರೆಗಳು 90% ವಿಶ್ವಾಸಾಂತರ.",
    drivers_value: "ಪ್ರತಿ ಹವಾಮಾನ ಸಂಕೇತ ಏನನ್ನು ಊಹಿಸುತ್ತದೆ", drivers_note: "MJO ಒಣ ಹವೆಯ ಅವಧಿಗಳನ್ನು, ENSO ಮತ್ತು IOD ಹಂಗಾಮಿನ ಒಟ್ಟು ಮಳೆಯನ್ನು ನಿರ್ಧರಿಸುತ್ತವೆ.",
    reliability: "ವಿಶ್ವಾಸಾರ್ಹತೆ", v3_card: "ವಾರ 1: ಡೌನ್‌ಸ್ಕೇಲಿಂಗ್ ಮಾದರಿ", v3_hint: "2023 ಪರೀಕ್ಷಾ ಹಂಗಾಮು, ಪಂಚಾಯಿತಿವಾರು",
    v3_note: "ಗಮನಿಸಿದ ಮಳೆ ಮತ್ತು ತಾಪಮಾನದ ವಿರುದ್ಧ ದೋಷ, ಮೂಲ 0.25° GFS ಮುನ್ಸೂಚನೆಯ ಜೊತೆಗೆ.",
    facts: "ದತ್ತಾಂಶ ಮತ್ತು ಪರಿಶೀಲನೆ", wk: "ವಾ", onset: "ಮುಂಗಾರು ಆರಂಭ", dry: "ಒಣ ವಾರ", wet: "ಮಳೆಯ ವಾರ", heavy: "ಭಾರಿ ಮಳೆ",
    break3w: "3 ವಾರಗಳಲ್ಲಿ ಒಣ ಹವೆ (7+ ದಿನ)", false3w: "ಸುಳ್ಳು ಮುಂಗಾರು ಅಪಾಯ", onset_started: "ಮುಂಗಾರು ಆರಂಭವಾಗಿದೆ",
    onset_pending: "ಮುಂಗಾರು ಇನ್ನೂ ಆರಂಭವಾಗಿಲ್ಲ", onset_expected: "ಹೆಚ್ಚು ಸಾಧ್ಯತೆ", no_onset4: "4 ವಾರಗಳಲ್ಲಿ ನಿರೀಕ್ಷೆಯಿಲ್ಲ",
    observed: "ಗಮನಿಸಿದ", forecast: "ಮುನ್ಸೂಚನೆ", copied: "ನಕಲಿಸಲಾಗಿದೆ", red: "ಈಗ ಕ್ರಮ", amber: "ಸಿದ್ಧರಾಗಿ", green: "ಸರಿ",
    gps_red: "ಕೆಂಪು ಎಚ್ಚರಿಕೆಯ ಪಂಚಾಯಿತಿಗಳು", mean_break: "ಸರಾಸರಿ ಒಣ ಹವೆ ಅಪಾಯ", mean_heavy: "ಸರಾಸರಿ ಭಾರಿ ಮಳೆ ಅಪಾಯ (ವಾ 1)",
    p_onset: "≤ 2 ವಾರದಲ್ಲಿ ಆರಂಭ", reliability_wait: "43 ಹಂಗಾಮುಗಳ ಪರಿಶೀಲನೆಯಿಂದ ವಿಶ್ವಾಸಾರ್ಹತೆ ರೇಖೆಗಳು ಬರುತ್ತವೆ.",
    el_nino: "ಎಲ್ ನಿನೊ", la_nina: "ಲಾ ನಿನಾ", neutral: "ತಟಸ್ಥ", pos_iod: "ಧನಾತ್ಮಕ IOD", neg_iod: "ಋಣಾತ್ಮಕ IOD",
    mjo_active: "ಸಕ್ರಿಯ", mjo_weak: "ದುರ್ಬಲ", phase: "ಹಂತ", amp: "ಪ್ರಾಬಲ್ಯ", select_gp: "ವಿವರಗಳಿಗೆ ಪಂಚಾಯಿತಿ ಒತ್ತಿ",
    importance: "ಮಾದರಿಗಳು ಯಾವುದನ್ನು ಅವಲಂಬಿಸಿವೆ", importance_hint: "ಪರೀಕ್ಷಾ ಹಂಗಾಮುಗಳ ಮೇಲೆ",
    within2: "2 ವಾರದಲ್ಲಿ ಆರಂಭ", within4: "4 ವಾರದಲ್ಲಿ", shipped: "ಬಳಕೆಯಲ್ಲಿರುವ ಮಾದರಿಯ ನಿಖರತೆ", shipped_hint: "ಪ್ರತಿ ಘಟನೆ ಮತ್ತು ವಾರ",
    hybrid_note: "ವಾರ 1: ಡೌನ್‌ಸ್ಕೇಲಿಂಗ್ ಮಾದರಿಯೊಂದಿಗೆ ಸಂಯೋಜನೆ (2015–2023); ವಾರ 2–4: ಹವಾಮಾನ ಚಾಲಕಗಳು (1981–2023).",
  },
};
const COLORS = { onset: "#2e9b5f", false3w: "#c2410c", break3w: "#b7791f", dry: "#b7791f", wet: "#2f6fd6", heavy: "#7e3fb2" };

const S = { meta: null, model: null, seasons: {}, season: null, issue: 0, gp: null, lang: localGet("lang") || "en",
            mapEvent: "break3w", mapWeek: 1, map: null, gpLayer: null, geo: null };
function localGet(k) { try { return localStorage.getItem("mo_" + k); } catch { return null; } }
function localSet(k, v) { try { localStorage.setItem("mo_" + k, v); } catch { /* storage unavailable */ } }
const t = (k) => T[S.lang][k] ?? T.en[k] ?? k;
const $ = (q) => document.querySelector(q);
const pct = (p) => (p == null ? "–" : `${Math.round(p * 100)}%`);
// all dates are calendar dates: do the arithmetic and formatting in UTC so the local time zone never shifts a day
const fmtDate = (iso, opts = { day: "numeric", month: "short" }) => new Date(iso + "T00:00:00Z").toLocaleDateString(S.lang === "kn" ? "kn-IN" : "en-IN", { ...opts, timeZone: "UTC" });
const addDays = (iso, n) => { const d = new Date(iso + "T00:00:00Z"); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); };
function shade(hex, p) { // blend event colour with white by probability
  const v = Math.max(0, Math.min(1, p ?? 0)), n = parseInt(hex.slice(1), 16);
  const r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255, a = 0.12 + 0.88 * v;
  const mix = (c) => Math.round(255 + (c - 255) * a);
  return `rgb(${mix(r)},${mix(g)},${mix(b)})`;
}
const textOn = (p) => (p >= 0.55 ? "#fff" : "#0f1f33");
function toast(msg) { const el = $("#toast"); el.textContent = msg; el.hidden = false; clearTimeout(toast._t); toast._t = setTimeout(() => (el.hidden = true), 1800); }

// ------------------------------------------------------------------ data
async function getJSON(u) { const r = await fetch(u); if (!r.ok) throw new Error(u + " " + r.status); return r.json(); }
async function season(y) { if (!S.seasons[y]) S.seasons[y] = await getJSON(`data/season_${y}.json`); return S.seasons[y]; }
const EV = () => S.meta.events;
function probs(code, issueIdx = S.issue) {
  const row = S.seasons[S.season].gp[code].p[issueIdx], o = {};
  EV().forEach((e, i) => (o[e] = row[i]));
  return o;
}
const issueDate = (i = S.issue) => S.seasons[S.season].issues[i].date;
const onsetSeen = (code, i = S.issue) => { const ob = S.seasons[S.season].gp[code].onset_obs; return ob && ob < issueDate(i); };
function renderAdv(a, lang = S.lang) {
  const tpl = S.meta.templates[a[0]][lang];
  return tpl.replace(/\{(\w+)\}/g, (_, k) => a[3][k] ?? "");
}
function smsText(code, lang) {
  const adv = S.seasons[S.season].gp[code].adv[S.issue], g = gpByCode(code);
  const head = lang === "kn" ? `${g.name}: ` : `${g.name}: `;
  const body = renderAdv(adv[0], lang);
  const lim = lang === "kn" ? 140 : 160;
  let s = head + body;
  if (s.length > lim) { const cut = s.slice(0, lim); const k = Math.max(cut.lastIndexOf(". "), cut.lastIndexOf("; ")); s = k > 40 ? cut.slice(0, k + 1) : cut.slice(0, lim - 1) + "…"; }
  return s;
}
const gpByCode = (c) => S.meta.gps.find((g) => g.code === c);

// ------------------------------------------------------------------ chrome
function applyI18n() {
  document.body.classList.toggle("kn", S.lang === "kn");
  document.documentElement.lang = S.lang;
  document.querySelectorAll("[data-i18n]").forEach((el) => (el.textContent = t(el.dataset.i18n)));
  document.querySelectorAll("[data-i18n-ph]").forEach((el) => (el.placeholder = t(el.dataset.i18nPh)));
  $("#btn-lang").textContent = S.lang === "en" ? "ಕನ್ನಡ" : "English";
}
function fillSelectors() {
  $("#sel-season").innerHTML = S.meta.seasons.map((y) => `<option ${y === S.season ? "selected" : ""}>${y}</option>`).join("");
  const iss = S.seasons[S.season].issues;
  $("#sel-issue").innerHTML = iss.map((x, i) => `<option value="${i}" ${i === S.issue ? "selected" : ""}>${fmtDate(x.date, { day: "numeric", month: "short" })}</option>`).join("");
}
function showView(v) {
  document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("active", b.dataset.view === v));
  document.querySelectorAll(".view").forEach((s) => s.classList.toggle("active", s.id === "view-" + v));
  localSet("view", v);
  if (v === "map") { ensureMap(); setTimeout(() => S.map.invalidateSize(), 50); }
  render();
}
const activeView = () => document.querySelector(".tab.active").dataset.view;

// ------------------------------------------------------------------ panchayat view
function renderPanchayat() {
  const g = gpByCode(S.gp), p = probs(S.gp), d0 = issueDate(), seen = onsetSeen(S.gp);
  $("#gp-name").textContent = g.name;
  $("#gp-taluk").textContent = g.taluk;
  const ob = S.seasons[S.season].gp[S.gp].onset_obs;
  const badge = $("#onset-badge");
  if (seen) {
    badge.className = "onset-badge";
    badge.innerHTML = `${t("onset_started")}<small>${fmtDate(ob)}</small>`;
  } else {
    const cum = []; let acc = 0;
    for (let k = 1; k <= 4; k++) { acc = 1 - (1 - acc) * (1 - p[`onset_${k}`]); cum.push(acc); }
    const best = [1, 2, 3, 4].reduce((a, k) => (p[`onset_${k}`] > p[`onset_${a}`] ? k : a), 1);
    badge.className = "onset-badge pending";
    badge.innerHTML = `${t("onset_pending")}<small>${t("within2")} ${pct(cum[1])} · ${t("within4")} ${pct(cum[3])}</small>`;
  }
  $("#weeks-range").textContent = `${fmtDate(d0)} – ${fmtDate(addDays(d0, 27))}`;
  let h = `<div></div>` + [1, 2, 3, 4].map((k) => `<div class="tl-h"><strong>${t("wk")} ${k}</strong>${fmtDate(addDays(d0, 7 * (k - 1)))}</div>`).join("");
  const rows = [["onset", "onset"], ["dry", "dry"], ["wet", "wet"], ["heavy", "heavy"]];
  for (const [key, col] of rows) {
    h += `<div class="tl-row"><span class="tl-dot" style="background:${COLORS[col]}"></span>${t(key)}</div>`;
    for (let k = 1; k <= 4; k++) {
      const v = p[`${key}_${k}`];
      if (key === "onset" && seen) { h += `<div class="tl-cell na">–</div>`; continue; }
      h += `<div class="tl-cell" style="background:${shade(COLORS[col], v)};color:${textOn(v)}">${pct(v)}</div>`;
    }
  }
  $("#timeline").innerHTML = h;
  $("#g-break").innerHTML = `${gauge(p.break3w, COLORS.break3w)}<div class="g-label">${t("break3w")}</div>`;
  $("#g-false").innerHTML = seen ? `${gauge(0, COLORS.false3w)}<div class="g-label">${t("false3w")}<small>${t("onset_started")}</small></div>`
    : `${gauge(p.false3w, COLORS.false3w)}<div class="g-label">${t("false3w")}</div>`;
  const adv = S.seasons[S.season].gp[S.gp].adv[S.issue];
  const other = S.lang === "en" ? "kn" : "en";
  $("#advisories").innerHTML = adv.map((a) => `<li class="adv ${a[1]}"><span class="adv-bar"></span><div>
      <div class="adv-top"><span class="pill ${a[1]}">${t(a[1])}</span><span class="pill">${t("wk")} ${a[2]}</span>${S.meta.templates[a[0]].crops.map((c) => `<span class="pill">${c}</span>`).join("")}</div>
      <p>${renderAdv(a)}</p><p class="sub">${renderAdv(a, other)}</p></div></li>`).join("");
  const wa = adv.map((a) => `${a[1] === "red" ? "🔴" : a[1] === "amber" ? "🟠" : "🟢"} ${renderAdv(a, "kn")}\n${renderAdv(a, "en")}`).join("\n\n");
  $("#btn-wa").href = `https://wa.me/?text=${encodeURIComponent(`${g.name} (${g.taluk}) — ${fmtDate(d0)}\n\n${wa}`)}`;
  $("#btn-sms").href = `sms:?&body=${encodeURIComponent(smsText(S.gp, S.lang))}`;
  $("#btn-copy").onclick = () => navigator.clipboard?.writeText(`${g.name} — ${fmtDate(d0)}\n\n${wa}`).then(() => toast(t("copied")));
  const w1 = S.seasons[S.season].gp[S.gp].v3w1[S.issue] || [];
  const mx = Math.max(10, ...w1);
  $("#daily-bars").innerHTML = w1.map((v, i) => `<div class="db"><span class="db-val">${v >= 0.5 ? v.toFixed(0) : "0"}</span><span class="db-bar" style="height:${(100 * v) / mx}%"></span><span class="db-day">${fmtDate(addDays(d0, i), { weekday: "short" })}</span></div>`).join("");
  const obs = S.seasons[S.season].gp[S.gp].obs[S.issue] || [];
  $("#verify").innerHTML = obs.map((mm, k) => {
    const dry = p[`dry_${k + 1}`], wet = p[`wet_${k + 1}`];
    return `<div class="vf"><div class="wk">${t("wk")} ${k + 1}</div><div class="mm">${mm.toFixed(0)} mm</div>
      <span class="tag" style="background:${shade(COLORS.dry, dry)};color:${textOn(dry)}">${t("dry")} ${pct(dry)}</span>
      <span class="tag" style="background:${shade(COLORS.wet, wet)};color:${textOn(wet)};margin-top:3px">${t("wet")} ${pct(wet)}</span></div>`;
  }).join("");
}

function setupSearch() {
  const inp = $("#gp-search"), box = $("#gp-results");
  inp.addEventListener("input", () => {
    const q = inp.value.trim().toLowerCase();
    if (!q) { box.hidden = true; return; }
    const hits = S.meta.gps.filter((g) => g.name.toLowerCase().includes(q) || g.taluk.toLowerCase().includes(q)).slice(0, 12);
    box.innerHTML = hits.map((g) => `<button data-code="${g.code}"><span>${g.name}</span><small>${g.taluk}</small></button>`).join("");
    box.hidden = !hits.length;
  });
  box.addEventListener("click", (e) => {
    const b = e.target.closest("button"); if (!b) return;
    selectGP(b.dataset.code); inp.value = ""; box.hidden = true;
  });
  document.addEventListener("click", (e) => { if (!e.target.closest(".search-wrap")) box.hidden = true; });
}
function selectGP(code) { S.gp = code; localSet("gp", code); render(); }

// ------------------------------------------------------------------ map view
const MAP_EVENTS = [["break3w", false], ["false3w", false], ["onset", true], ["dry", true], ["wet", true], ["heavy", true]];
function mapValue(code) {
  const p = probs(code), e = S.mapEvent, k = S.mapWeek;
  if (e === "onset") { if (onsetSeen(code)) return null; let acc = 0; for (let j = 1; j <= k; j++) acc = 1 - (1 - acc) * (1 - p[`onset_${j}`]); return acc; }
  if (e === "false3w") return onsetSeen(code) ? null : p.false3w;
  if (e === "break3w") return p.break3w;
  return p[`${e}_${k}`];
}
function ensureMap() {
  if (S.map) return;
  S.map = L.map("map", { zoomControl: true, attributionControl: true, preferCanvas: false });
  L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}",
    { attribution: "Tiles © Esri — Esri, HERE, Garmin, © OpenStreetMap contributors", maxZoom: 14 }).addTo(S.map);
  S.gpLayer = L.geoJSON(S.geo.gp, { style: styleGP, onEachFeature: (f, l) => {
    l.on("click", () => { selectGP(f.properties.code); showInfo(f.properties.code); });
    l.on("mouseover", () => showInfo(f.properties.code));
  } }).addTo(S.map);
  L.geoJSON(S.geo.taluk, { style: { fill: false, color: "#0f2a4a", weight: 1.6, opacity: 0.8 }, interactive: false }).addTo(S.map);
  S.map.fitBounds(S.gpLayer.getBounds(), { padding: [10, 10] });
}
function styleGP(f) {
  const v = mapValue(f.properties.code), col = COLORS[S.mapEvent] || COLORS.dry;
  const sel = f.properties.code === S.gp;
  return { fillColor: v == null ? "#e5e9ef" : shade(col, v), fillOpacity: 0.92, color: sel ? "#0f1f33" : "#ffffff", weight: sel ? 2.4 : 0.6 };
}
function showInfo(code) {
  const g = gpByCode(code), v = mapValue(code), el = $("#map-info");
  const adv = S.seasons[S.season].gp[code].adv[S.issue][0];
  el.style.display = "block";
  el.innerHTML = `<strong>${g.name}</strong><span class="hint">${g.taluk}</span><div style="margin:6px 0 4px;font-size:1.2rem;font-weight:800">${v == null ? "–" : pct(v)}</div><span class="pill ${adv[1]}">${t(adv[1])}</span><p style="margin:6px 0 0;font-size:.8rem;line-height:1.35">${renderAdv(adv)}</p>`;
}
function eventTitle(e) { return e === "onset" ? t("onset") : t(e); }
function renderMap() {
  $("#event-chips").innerHTML = MAP_EVENTS.map(([e]) => `<button class="chip ${e === S.mapEvent ? "active" : ""}" data-e="${e}"><span class="tl-dot" style="background:${COLORS[e]}"></span>${eventTitle(e)}</button>`).join("");
  const weekly = MAP_EVENTS.find(([e]) => e === S.mapEvent)[1];
  $("#week-chips").innerHTML = [1, 2, 3, 4].map((k) => `<button class="chip ${k === S.mapWeek ? "active" : ""}" data-k="${k}" ${weekly ? "" : "disabled style='opacity:.4'"}>${k}</button>`).join("");
  if (S.gpLayer) S.gpLayer.setStyle(styleGP);
  const col = COLORS[S.mapEvent];
  const d0 = issueDate();
  const span = weekly ? (S.mapEvent === "onset" ? `${fmtDate(d0)} – ${fmtDate(addDays(d0, 7 * S.mapWeek - 1))}` : `${fmtDate(addDays(d0, 7 * (S.mapWeek - 1)))} – ${fmtDate(addDays(d0, 7 * S.mapWeek - 1))}`) : `${fmtDate(d0)} – ${fmtDate(addDays(d0, 20))}`;
  $("#map-legend").innerHTML = `<strong>${eventTitle(S.mapEvent)}</strong> · ${span}<div class="ramp">${[0, .1, .2, .3, .4, .5, .6, .7, .8, .9].map((v) => `<span style="background:${shade(col, v + .05)}"></span>`).join("")}</div><div class="ticks"><span>0%</span><span>50%</span><span>100%</span></div>`;
  const vals = S.meta.gps.map((g) => mapValue(g.code)).filter((v) => v != null);
  const reds = S.meta.gps.filter((g) => S.seasons[S.season].gp[g.code].adv[S.issue][0][1] === "red").length;
  const mean = vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
  const hi = vals.filter((v) => v >= 0.5).length;
  $("#map-summary").innerHTML = `<div class="stat"><div class="v">${pct(mean)}</div><div class="l">${eventTitle(S.mapEvent)} · mean</div></div>
    <div class="stat"><div class="v">${hi}</div><div class="l">≥ 50% · ${S.lang === "kn" ? "ಪಂಚಾಯಿತಿಗಳು" : "panchayats"}</div></div>
    <div class="stat"><div class="v">${reds}</div><div class="l">${t("gps_red")}</div></div>`;
}

// ------------------------------------------------------------------ officer view
function ensoLabel(v) { return v == null ? "–" : v >= 0.5 ? t("el_nino") : v <= -0.5 ? t("la_nina") : t("neutral"); }
function iodLabel(v) { return v == null ? "–" : v >= 0.4 ? t("pos_iod") : v <= -0.4 ? t("neg_iod") : t("neutral"); }
function renderOfficer() {
  const iss = S.seasons[S.season].issues, cur = iss[S.issue];
  $("#drivers-date").textContent = fmtDate(cur.date, { day: "numeric", month: "short", year: "numeric" });
  const trail = iss.slice(Math.max(0, S.issue - 5), S.issue + 1).map((x) => ({ x: x.mjo_x, y: x.mjo_y }));
  $("#mjo-plot").innerHTML = mjoDiagram(trail);
  $("#d-mjo").innerHTML = `<div class="k">MJO</div><div class="v">${cur.mjo_phase ? `${t("phase")} ${cur.mjo_phase}` : "–"}</div><div class="s">${cur.mjo_amp != null ? `${t("amp")} ${cur.mjo_amp.toFixed(2)} · ${cur.mjo_amp >= 1 ? t("mjo_active") : t("mjo_weak")}` : ""}</div>`;
  $("#d-enso").innerHTML = `<div class="k">ENSO · Niño 3.4</div><div class="v">${cur.nino34 != null ? `${cur.nino34 > 0 ? "+" : ""}${cur.nino34.toFixed(1)} °C` : "–"}</div><div class="s">${ensoLabel(cur.nino34)}</div>`;
  $("#d-iod").innerHTML = `<div class="k">IOD · DMI</div><div class="v">${cur.dmi != null ? `${cur.dmi > 0 ? "+" : ""}${cur.dmi.toFixed(2)}` : "–"}</div><div class="s">${iodLabel(cur.dmi)}</div>`;
  const upto = iss.slice(0, S.issue + 1);
  $("#driver-spark").innerHTML = spark([
    { name: "Niño 3.4", color: "#d64545", values: upto.map((x) => x.nino34) },
    { name: "DMI", color: "#2f6fd6", values: upto.map((x) => x.dmi) },
    { name: "MJO amp", color: "#0e7c86", values: upto.map((x) => x.mjo_amp) }]);
  // taluk table
  const cols = [["p_onset", (p, c) => (onsetSeen(c) ? null : 1 - (1 - p.onset_1) * (1 - p.onset_2)), COLORS.onset],
                ["false3w", (p, c) => (onsetSeen(c) ? null : p.false3w), COLORS.false3w], ["break3w", (p) => p.break3w, COLORS.break3w],
                ["heavy", (p) => p.heavy_1, COLORS.heavy], ["dry", (p) => p.dry_2, COLORS.dry]];
  const heads = [t("taluk"), ...cols.map(([k]) => (k === "heavy" ? `${t("heavy")} (${t("wk")} 1)` : k === "dry" ? `${t("dry")} (${t("wk")} 2)` : t(k))), "🔴"];
  let rows = "";
  for (const tk of S.meta.taluks) {
    const gs = S.meta.gps.filter((g) => g.taluk === tk);
    const cells = cols.map(([, f, col]) => {
      const v = gs.map((g) => f(probs(g.code), g.code)).filter((x) => x != null);
      const m = v.length ? v.reduce((a, b) => a + b, 0) / v.length : null;
      return `<td class="num">${m == null ? "–" : `<span class="heat" style="background:${shade(col, m)};color:${textOn(m)}">${pct(m)}</span>`}</td>`;
    }).join("");
    const reds = gs.filter((g) => S.seasons[S.season].gp[g.code].adv[S.issue][0][1] === "red").length;
    rows += `<tr><td><strong>${tk}</strong> <span class="hint">${gs.length}</span></td>${cells}<td class="num">${reds}</td></tr>`;
  }
  $("#taluk-table").innerHTML = `<thead><tr>${heads.map((h) => `<th>${h}</th>`).join("")}</tr></thead><tbody>${rows}</tbody>`;
  renderQueue();
}
function queueItems() {
  const f = $("#queue-filter").value, ok = f === "red" ? ["red"] : f === "amber" ? ["red", "amber"] : ["red", "amber", "green"];
  return S.meta.gps.map((g) => ({ g, adv: S.seasons[S.season].gp[g.code].adv[S.issue] })).filter((x) => ok.includes(x.adv[0][1]))
    .sort((a, b) => ["red", "amber", "green"].indexOf(a.adv[0][1]) - ["red", "amber", "green"].indexOf(b.adv[0][1]) || a.g.taluk.localeCompare(b.g.taluk));
}
function renderQueue() {
  const items = queueItems();
  $("#queue").innerHTML = items.slice(0, 120).map(({ g, adv }) => `<div class="q"><div><span class="gpn">${g.name}</span> <span class="gpt">${g.taluk}</span> <span class="pill ${adv[0][1]}">${t(adv[0][1])}</span>
      <div class="msg">${smsText(g.code, S.lang)}</div></div>
      <div class="acts"><a class="btn wa small" target="_blank" rel="noopener" href="https://wa.me/?text=${encodeURIComponent(smsText(g.code, "kn") + "\n" + smsText(g.code, "en"))}">WA</a>
      <a class="btn sms small" href="sms:?&body=${encodeURIComponent(smsText(g.code, S.lang))}">SMS</a></div></div>`).join("") || `<p class="hint">—</p>`;
}
function exportCSV() {
  const rows = [["lgd_code", "panchayat", "taluk", "issued", "level", "sms_en", "sms_kn"]];
  for (const { g, adv } of queueItems()) rows.push([g.code, g.name, g.taluk, issueDate(), adv[0][1], smsText(g.code, "en"), smsText(g.code, "kn")]);
  const csv = "﻿" + rows.map((r) => r.map((x) => `"${String(x).replace(/"/g, '""')}"`).join(",")).join("\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  a.download = `mandya_advisories_${issueDate()}.csv`; a.click();
}

// ------------------------------------------------------------------ model (ML) view
function renderModel() {
  const M = S.model;
  $("#pipeline").innerHTML = M.pipeline.map((s, i) => `<div class="stage"><span class="n">${i + 1}</span><h3>${s.name}</h3><div class="role">${s.role}</div>
      <ul>${s.inputs.map((x) => `<li>${x}</li>`).join("")}</ul><div class="meta">${s.params}${s.training ? ` · ${s.training}` : ""}</div></div>`).join("");
  const cats = [1, 2, 3, 4].map((k) => `${t("wk")} ${k}`);
  let series, src;
  if (M.cv_43_seasons) {
    const cv = M.cv_43_seasons;
    const mk = (ev, color) => ({ name: t(ev), color, values: [1, 2, 3, 4].map((k) => { const m = cv[`${ev}_${k}`]; return m ? { v: m.bss, lo: m.ci90[0], hi: m.ci90[1] } : null; }) });
    series = [mk("dry", COLORS.dry), mk("wet", COLORS.wet), mk("heavy", COLORS.heavy), mk("onset", COLORS.onset)];
    if (M.final_selection) {   // the shipped version of each target (outlook, or a validated hybrid for weeks 1-2)
      const F = M.final_selection;
      series.forEach((s, j) => { const ev = ["dry", "wet", "heavy", "onset"][j];
        s.values = [1, 2, 3, 4].map((k) => { const f = F[`${ev}_${k}`]; return f ? { v: f.bss, lo: f.ci90[0], hi: f.ci90[1] } : null; }); });
      const rows = Object.entries(F).map(([k, f]) => `<tr><td>${k.replace(/_(\d)$/, " · wk $1").replace("break3w", "dry spell (3 wk)").replace("false3w", "false onset (3 wk)")}</td>
        <td>${({ outlook: "climate drivers", v3: "+ v3 week 1", gfs: "+ GFS d1–16 + v3", gefs: "+ GEFS 11-member ensemble", gefs2: "+ calibrated GEFS ensemble", blend: "GFS + GEFS hybrids averaged", v3ens: "+ v3 diffusion ensemble" })[f.source]}</td><td class="num">${f.bss.toFixed(3)}</td>
        <td class="num">[${f.ci90[0].toFixed(3)}, ${f.ci90[1].toFixed(3)}]</td><td>${f.seasons}</td></tr>`).join("");
      $("#sel-table").innerHTML = `<thead><tr><th>Event</th><th>Shipped model</th><th>Brier skill</th><th>90% CI</th><th>Validated on</th></tr></thead><tbody>${rows}</tbody>`;
    }
    src = "1981–2023 · 43 seasons";
  } else {
    const F = M.feasibility_9_seasons.all_predictors;
    const pick = (row, k) => (k === "1" && row.v3 ? row.v3 : row.all) || null;
    const mk = (ev, color) => ({ name: t(ev), color, values: ["1", "2", "3", "4"].map((k) => { const r = F[ev]?.[k]; const v = r && pick(r, k); return v ? { v: v[0], lo: v[1], hi: v[2] } : null; }) });
    series = [mk("dry", COLORS.dry), mk("wet", COLORS.wet), mk("heavy", COLORS.heavy)];
    src = "2015–2023 · 9 seasons";
  }
  $("#skill-src").textContent = src;
  $("#skill-chart").innerHTML = skillBars(cats, series, { ymin: -0.1, ymax: 0.35 }) + (M.final_selection ? `<div class="chart-note">${t("hybrid_note")}</div>` : "");
  const sp = M.feasibility_9_seasons.by_index || {};
  const dser = (ev, key, name, color) => ({ name, color, values: ["1", "2", "3", "4"].map((k) => { const v = sp[ev]?.[k]?.[key]; return v ? { v: v[0], lo: v[1], hi: v[2] } : null; }) });
  $("#driver-chart").innerHTML = skillBars(cats, [dser("dry", "mjo", "MJO → dry", "#b7791f"), dser("dry", "enso_iod", "ENSO+IOD → dry", "#e6c58a"),
    dser("wet", "mjo", "MJO → wet", "#2f6fd6"), dser("wet", "enso_iod", "ENSO+IOD → wet", "#9cbcf0")], { ymin: -0.1, ymax: 0.2, height: 230 });
  if (M.cv_43_seasons && M.cv_43_seasons.break3w) {
    $("#rel-event").textContent = t("break3w");
    $("#rel-chart").innerHTML = reliability(M.cv_43_seasons.break3w.reliability, COLORS.break3w);
  } else {
    $("#rel-chart").innerHTML = `<p class="hint">${t("reliability_wait")}</p>`;
  }
  const V = M.v3_gp_skill_2023;
  if (V) {
    const any = Object.values(V)[0];
    const rows = [["GFS 0.25° (raw)", any.gfs_rain_mae_mm, any.gfs_wet_day_mae_mm, any.gfs_rain_bias_ratio, any.gfs_tmax_mae_c, null, false]]
      .concat(Object.entries(V).map(([m, s]) => [`v3 ${m}`, s.rain_mae_mm, s.wet_day_mae_mm, s.rain_bias_ratio, s.tmax_mae_c, s.range_coverage_5_95, m === "ENSEMBLE"]));
    $("#v3-table").innerHTML = `<thead><tr><th></th><th>Rain MAE</th><th>Wet-day MAE</th><th>Bias</th><th>Tmax MAE</th><th>5–95% cover</th></tr></thead><tbody>` +
      rows.map((r) => `<tr class="${r[6] ? "best" : ""}"><td>${r[0]}</td><td class="num">${r[1].toFixed(2)}</td><td class="num">${r[2].toFixed(2)}</td><td class="num">${r[3].toFixed(2)}</td><td class="num">${r[4].toFixed(2)}</td><td class="num">${r[5] == null ? "–" : pct(r[5])}</td></tr>`).join("") + `</tbody>`;
  }
  if (M.cv_43_seasons) {
    const names = { clim_logit: "Panchayat climatology", rain7: "Rain, last 7 days", rain30: "Rain, last 30 days", dry_days14: "Dry days, last 14",
      season_anom: "Season-to-date anomaly", wet_starts: "Sowing-rain events so far", days_since_wet_start: "Days since sowing rain",
      mjo_pc1: "MJO PC1", mjo_pc2: "MJO PC2", mjo_amp: "MJO amplitude", nino34: "ENSO (Niño 3.4)", dmi: "IOD (DMI)",
      doy_sin: "Season (sin)", doy_cos: "Season (cos)", lat: "Latitude", lon: "Longitude", clim_mean: "Mean seasonal rain" };
    const tg = [["break3w", t("break3w"), COLORS.break3w], ["dry_2", `${t("dry")} (${t("wk")} 2)`, COLORS.dry], ["wet_2", `${t("wet")} (${t("wk")} 2)`, COLORS.wet]];
    const groups = tg.filter(([k]) => M.cv_43_seasons[k]?.importance).map(([k, name, color]) => {
      const v = M.cv_43_seasons[k].importance; return { name, color, values: v, max: Math.max(...Object.values(v), 1e-9) };
    });
    if (groups.length) {
      const keys = Object.keys(names).filter((k) => groups.some((g) => (g.values[k] || 0) > 0));
      keys.sort((a, b) => groups.reduce((s, g) => s + (g.values[b] || 0) / g.max, 0) - groups.reduce((s, g) => s + (g.values[a] || 0) / g.max, 0));
      $("#imp-chart").innerHTML = importance(keys.slice(0, 10).map((k) => ({ key: k, label: names[k] })), groups);
    }
  }
  const facts = [["43", "monsoon seasons of 0.05° rainfall (1981–2023) for training and validation"], ["234", "gram panchayats in 7 blocks, area-weighted from a 0.05° grid"],
    ["18", "outlook models: onset, false onset, dry spell, dry / wet / heavy week × 4 leads"], ["3", "global drivers: MJO, ENSO (Niño 3.4), IOD (DMI)"],
    ["4", "operating modes of the week-1 model (fast → 16-member ensemble)"], ["0", "test seasons used for training: every score is out-of-sample"]];
  $("#facts").innerHTML = facts.map(([v, l]) => `<div class="fact"><div class="v">${v}</div><div class="l">${l}</div></div>`).join("");
}

// ------------------------------------------------------------------ render & boot
function render() {
  if (!S.meta || !S.seasons[S.season]) return;
  const v = activeView();
  if (v === "panchayat") renderPanchayat();
  if (v === "map") renderMap();
  if (v === "officer") renderOfficer();
  if (v === "model") renderModel();
}
async function setSeason(y, keepDate = false) {
  const prevDay = keepDate ? issueDate().slice(5) : null;
  S.season = +y; localSet("season", y);
  await season(S.season);
  const iss = S.seasons[S.season].issues;
  S.issue = prevDay ? Math.max(0, iss.findIndex((x) => x.date.slice(5) >= prevDay)) : Math.min(S.issue, iss.length - 1);
  fillSelectors(); render();
}
async function boot() {
  [S.meta, S.model] = await Promise.all([getJSON("data/meta.json"), getJSON("data/model.json")]);
  S.geo = { gp: await getJSON("data/gp.geojson"), taluk: await getJSON("data/taluk.geojson") };
  S.season = +(localGet("season") || S.meta.default.season);
  await season(S.season);
  const di = S.seasons[S.season].issues.findIndex((x) => x.date === S.meta.default.issue);
  S.issue = di >= 0 ? di : 0;
  S.gp = localGet("gp") && S.meta.gps.some((g) => g.code === localGet("gp")) ? localGet("gp") : (S.meta.gps.find((g) => g.name.toLowerCase().startsWith("melukote")) || S.meta.gps[0]).code;
  applyI18n(); fillSelectors(); setupSearch();
  $("#sel-season").onchange = (e) => setSeason(e.target.value, true);
  $("#sel-issue").onchange = (e) => { S.issue = +e.target.value; render(); };
  $("#btn-lang").onclick = () => { S.lang = S.lang === "en" ? "kn" : "en"; localSet("lang", S.lang); applyI18n(); fillSelectors(); render(); };
  document.querySelectorAll(".tab").forEach((b) => (b.onclick = () => showView(b.dataset.view)));
  $("#event-chips").onclick = (e) => { const b = e.target.closest("[data-e]"); if (b) { S.mapEvent = b.dataset.e; renderMap(); } };
  $("#week-chips").onclick = (e) => { const b = e.target.closest("[data-k]"); if (b && !b.disabled) { S.mapWeek = +b.dataset.k; renderMap(); } };
  $("#queue-filter").onchange = renderQueue;
  $("#btn-csv").onclick = exportCSV;
  showView(localGet("view") || "panchayat");
}
boot().catch((e) => { console.error(e); document.querySelector("main").insertAdjacentHTML("afterbegin", `<div class="card">Could not load data: ${e.message}</div>`); });
