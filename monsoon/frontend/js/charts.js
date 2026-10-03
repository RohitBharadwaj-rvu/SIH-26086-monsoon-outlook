// Small SVG chart helpers (no external libraries).
const NS = "http://www.w3.org/2000/svg";
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

export function gauge(p, color, size = 64) {
  const r = size / 2 - 6, c = 2 * Math.PI * r, v = Math.max(0, Math.min(1, p ?? 0));
  return `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" aria-hidden="true">
    <circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke="#edf1f6" stroke-width="7"/>
    <circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke="${color}" stroke-width="7" stroke-linecap="round"
      stroke-dasharray="${(v * c).toFixed(1)} ${c.toFixed(1)}" transform="rotate(-90 ${size / 2} ${size / 2})"/>
    <text x="50%" y="54%" text-anchor="middle" font-size="${size * 0.24}" font-weight="800" fill="#0f1f33">${Math.round(v * 100)}%</text></svg>`;
}

// MJO phase-space diagram (OMI plotted as x = PC2, y = -PC1, comparable with RMM phases 1-8)
export function mjoDiagram(points, labels) {
  const S = 220, c = S / 2, sc = 34;
  const px = (x) => c + x * sc, py = (y) => c - y * sc;
  let g = `<svg viewBox="0 0 ${S} ${S}" role="img" aria-label="MJO phase diagram">`;
  g += `<rect x="0" y="0" width="${S}" height="${S}" rx="12" fill="#f6f9fc"/>`;
  for (let k = 0; k < 4; k++) {
    const a = (Math.PI / 4) * k;
    g += `<line x1="${c - Math.cos(a) * 100}" y1="${c + Math.sin(a) * 100}" x2="${c + Math.cos(a) * 100}" y2="${c - Math.sin(a) * 100}" stroke="#dde4ee" stroke-width="1"/>`;
  }
  g += `<circle cx="${c}" cy="${c}" r="${sc}" fill="#fff" stroke="#c9d3e0" stroke-dasharray="3 3"/>`;
  for (let ph = 1; ph <= 8; ph++) {
    const a = ((180 + 45 * (ph - 1) + 22.5) * Math.PI) / 180;
    g += `<text x="${c + Math.cos(a) * 92}" y="${c - Math.sin(a) * 92 + 4}" text-anchor="middle" font-size="11" font-weight="700" fill="#6b7b90">${ph}</text>`;
  }
  const regions = labels || ["W. Hem/Africa", "Indian Ocean", "Maritime Cont.", "W. Pacific"];
  const rpos = [[c - 70, c + 4], [c, S - 8], [c + 70, c + 4], [c, 14]];
  regions.forEach((t, i) => (g += `<text x="${rpos[i][0]}" y="${rpos[i][1]}" text-anchor="middle" font-size="8.5" fill="#94a3b8">${esc(t)}</text>`));
  const pts = points.filter((p) => p.x != null);
  if (pts.length > 1) g += `<polyline points="${pts.map((p) => `${px(p.x)},${py(p.y)}`).join(" ")}" fill="none" stroke="#13a3a8" stroke-width="1.6" stroke-opacity=".55"/>`;
  pts.forEach((p, i) => {
    const last = i === pts.length - 1;
    g += `<circle cx="${px(p.x)}" cy="${py(p.y)}" r="${last ? 6 : 3}" fill="${last ? "#0f2a4a" : "#13a3a8"}" stroke="#fff" stroke-width="${last ? 2 : 1}"/>`;
  });
  return g + `</svg>`;
}

// Grouped bars: series = [{name, color, values:[{x, v, lo, hi}]}], categories along x (lead weeks)
export function skillBars(categories, series, { ymin = -0.1, ymax = 0.35, height = 240 } = {}) {
  const W = 520, H = height, L = 40, R = 10, T = 14, B = 40;
  const iw = W - L - R, ih = H - T - B;
  const y = (v) => T + ih * (1 - (Math.max(ymin, Math.min(ymax, v)) - ymin) / (ymax - ymin));
  const gw = iw / categories.length, bw = Math.min(22, (gw - 12) / series.length);
  let g = `<svg viewBox="0 0 ${W} ${H}" role="img">`;
  for (let t = Math.ceil(ymin * 10) / 10; t <= ymax + 1e-9; t += 0.1) {
    g += `<line x1="${L}" x2="${W - R}" y1="${y(t)}" y2="${y(t)}" stroke="${Math.abs(t) < 1e-9 ? "#94a3b8" : "#eef2f7"}" stroke-width="${Math.abs(t) < 1e-9 ? 1.2 : 1}"/>`;
    g += `<text x="${L - 6}" y="${y(t) + 4}" text-anchor="end" font-size="10" fill="#6b7b90">${t.toFixed(1)}</text>`;
  }
  categories.forEach((cat, i) => {
    const x0 = L + gw * i + (gw - bw * series.length) / 2;
    g += `<text x="${L + gw * i + gw / 2}" y="${H - 18}" text-anchor="middle" font-size="11" fill="#3c4d63" font-weight="600">${esc(cat)}</text>`;
    series.forEach((s, j) => {
      const d = s.values[i];
      if (!d || d.v == null) return;
      const x = x0 + j * bw, y0 = y(0), y1 = y(d.v);
      g += `<rect x="${x + 1}" y="${Math.min(y0, y1)}" width="${bw - 2}" height="${Math.max(1, Math.abs(y1 - y0))}" rx="3" fill="${s.color}" opacity="${d.lo != null && d.lo <= 0 ? 0.45 : 0.95}"><title>${esc(s.name)} · ${esc(cat)}: ${d.v.toFixed(3)}${d.lo != null ? ` [${d.lo.toFixed(3)}, ${d.hi.toFixed(3)}]` : ""}</title></rect>`;
      if (d.lo != null) {
        const xm = x + bw / 2;
        g += `<line x1="${xm}" x2="${xm}" y1="${y(d.lo)}" y2="${y(d.hi)}" stroke="#0f1f33" stroke-width="1.1"/>`;
        g += `<line x1="${xm - 3}" x2="${xm + 3}" y1="${y(d.lo)}" y2="${y(d.lo)}" stroke="#0f1f33"/><line x1="${xm - 3}" x2="${xm + 3}" y1="${y(d.hi)}" y2="${y(d.hi)}" stroke="#0f1f33"/>`;
      }
    });
  });
  let lx = L;
  series.forEach((s) => {
    g += `<rect x="${lx}" y="${H - 10}" width="10" height="8" rx="2" fill="${s.color}"/><text x="${lx + 14}" y="${H - 3}" font-size="10" fill="#3c4d63">${esc(s.name)}</text>`;
    lx += 14 + s.name.length * 6 + 16;
  });
  return g + `</svg>`;
}

export function reliability(bins, color = "#0e7c86") {
  const W = 320, H = 300, L = 40, B = 36, T = 12, R = 12, iw = W - L - R, ih = H - T - B;
  const X = (v) => L + v * iw, Y = (v) => T + ih * (1 - v);
  let g = `<svg viewBox="0 0 ${W} ${H}" role="img">`;
  for (let t = 0; t <= 1.0001; t += 0.2) {
    g += `<line x1="${X(t)}" x2="${X(t)}" y1="${T}" y2="${T + ih}" stroke="#eef2f7"/><line x1="${L}" x2="${L + iw}" y1="${Y(t)}" y2="${Y(t)}" stroke="#eef2f7"/>`;
    g += `<text x="${X(t)}" y="${H - 20}" text-anchor="middle" font-size="10" fill="#6b7b90">${t.toFixed(1)}</text><text x="${L - 6}" y="${Y(t) + 4}" text-anchor="end" font-size="10" fill="#6b7b90">${t.toFixed(1)}</text>`;
  }
  g += `<line x1="${X(0)}" y1="${Y(0)}" x2="${X(1)}" y2="${Y(1)}" stroke="#94a3b8" stroke-dasharray="4 3"/>`;
  const pts = bins.filter((b) => b[2] > 0);
  const maxn = Math.max(...pts.map((b) => b[2]));
  g += `<polyline points="${pts.map((b) => `${X(b[0])},${Y(b[1])}`).join(" ")}" fill="none" stroke="${color}" stroke-width="2"/>`;
  pts.forEach((b) => (g += `<circle cx="${X(b[0])}" cy="${Y(b[1])}" r="${3 + 5 * Math.sqrt(b[2] / maxn)}" fill="${color}" fill-opacity=".75" stroke="#fff"><title>forecast ${b[0].toFixed(2)} → observed ${b[1].toFixed(2)} (n=${b[2]})</title></circle>`));
  g += `<text x="${L + iw / 2}" y="${H - 4}" text-anchor="middle" font-size="10.5" fill="#3c4d63">forecast probability</text>`;
  g += `<text x="12" y="${T + ih / 2}" text-anchor="middle" font-size="10.5" fill="#3c4d63" transform="rotate(-90 12 ${T + ih / 2})">observed frequency</text>`;
  return g + `</svg>`;
}

export function spark(series, { height = 90 } = {}) {
  // series: [{name, color, values:[number|null]}], shared x
  const W = 520, H = height, L = 6, R = 6, T = 8, B = 16;
  const all = series.flatMap((s) => s.values.filter((v) => v != null));
  if (!all.length) return "";
  const lo = Math.min(...all, -0.5), hi = Math.max(...all, 0.5), n = series[0].values.length;
  const X = (i) => L + (W - L - R) * (n > 1 ? i / (n - 1) : 0.5), Y = (v) => T + (H - T - B) * (1 - (v - lo) / (hi - lo));
  let g = `<svg viewBox="0 0 ${W} ${H}"><line x1="${L}" x2="${W - R}" y1="${Y(0)}" y2="${Y(0)}" stroke="#cbd5e1" stroke-dasharray="3 3"/>`;
  let lx = L;
  series.forEach((s) => {
    const pts = s.values.map((v, i) => (v == null ? null : `${X(i)},${Y(v)}`)).filter(Boolean);
    g += `<polyline points="${pts.join(" ")}" fill="none" stroke="${s.color}" stroke-width="2"/>`;
    g += `<rect x="${lx}" y="${H - 10}" width="10" height="3" fill="${s.color}"/><text x="${lx + 13}" y="${H - 6}" font-size="9.5" fill="#3c4d63">${esc(s.name)}</text>`;
    lx += 13 + s.name.length * 5.6 + 14;
  });
  return g + `</svg>`;
}

// Horizontal grouped bars: rows = features, groups = models; values scaled to each model's max
export function importance(features, groups) {
  const rowH = 22, L = 150, R = 16, T = 8, W = 560, H = T + features.length * rowH + 30;
  const bw = (rowH - 6) / groups.length;
  let g = `<svg viewBox="0 0 ${W} ${H}" role="img">`;
  features.forEach((f, i) => {
    const y0 = T + i * rowH;
    g += `<text x="${L - 8}" y="${y0 + rowH / 2 + 4}" text-anchor="end" font-size="11" fill="#3c4d63">${f.label}</text>`;
    groups.forEach((gr, j) => {
      const v = Math.max(0, gr.values[f.key] || 0) / (gr.max || 1);
      g += `<rect x="${L}" y="${y0 + 3 + j * bw}" width="${Math.max(1, v * (W - L - R))}" height="${bw - 1}" rx="2" fill="${gr.color}"><title>${gr.name}: ${(gr.values[f.key] || 0).toExponential(2)}</title></rect>`;
    });
  });
  let lx = L;
  groups.forEach((gr) => { g += `<rect x="${lx}" y="${H - 14}" width="10" height="8" rx="2" fill="${gr.color}"/><text x="${lx + 14}" y="${H - 7}" font-size="10" fill="#3c4d63">${gr.name}</text>`; lx += 14 + gr.name.length * 6 + 18; });
  return g + `</svg>`;
}
