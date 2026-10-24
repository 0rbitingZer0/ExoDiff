"use strict";


const PAGE = 50;
const JUP_M = 317.83;

const FIELDS = [
  ["radius", "size", "Earths"],
  ["mass", "mass", "Earths"],
  ["period", "one orbit takes", "days"],
  ["orbit", "orbit size", "au"],
  ["eccentricity", "orbit stretch", ""],
  ["distance", "distance", "parsecs"],
];

const SRC = {
  winn: ["Winn 2010", "https://arxiv.org/abs/1001.2010"],
  iau15: ["IAU 2015 B3, Prša et al. 2016", "https://arxiv.org/abs/1605.09788"],
  iau12: ["IAU 2012 B2", "https://iauarchive.eso.org/static/resolutions/IAU2012_English.pdf"],
  parsec: ["IAU 2015 B2, Mamajek et al. 2015", "https://arxiv.org/abs/1510.06262"],
  cols: ["NASA archive column definitions", "https://exoplanetarchive.ipac.caltech.edu/docs/API_PS_columns.html"],
  laughlin: ["Laughlin et al. 2011", "https://arxiv.org/abs/1101.5827"],
  wg: ["Wright & Gaudi 2013", "https://arxiv.org/abs/1210.2471"],
  jupiter: ["NASA Jupiter fact sheet", "https://nssdc.gsfc.nasa.gov/planetary/factsheet/jupiterfact.html"],
  eu: ["exoplanet.eu readme", "https://exoplanet.eu/readme/"],
  gaiaDist: ["Bailer-Jones et al. 2021", "https://arxiv.org/abs/2012.05220"],
  tic: ["Stassun et al. 2019, section 2.3", "https://arxiv.org/abs/1905.10694"],
  nasaMethods: ["NASA: how we find exoplanets", "https://science.nasa.gov/exoplanets/how-we-find-and-characterize/"],
};

const CARDS = {
  radius: {
    title: "size: the row's numbers don't fit together",
    maths: "size (Earths) = size ratio × star size (Suns) × 109.076",
    src: ["winn", "iau15"],
  },
  density: {
    title: "density: doesn't match mass and size",
    maths: "density (g/cm³) = 5.495 × mass (Earths) ÷ size (Earths)³",
    src: ["iau15", "cols"],
  },
  kepler: {
    title: "orbit size: doesn't match orbit time and star mass",
    maths: "orbit size (au) = (star mass (Suns) × (orbit time in days ÷ 365.25)²)^(1/3)",
    src: ["winn", "iau15", "iau12"],
  },
  a_over_rstar: {
    title: "orbit in star sizes: doesn't match orbit size ÷ star size",
    maths: "orbit in star sizes = orbit size (au) × 215.032 ÷ star size (Suns)",
    src: ["cols", "iau15", "iau12"],
  },
  A5: { src: ["iau15", "jupiter"] },
  gaia: { src: ["tic", "gaiaDist"] },
  eu: { src: ["eu"] },
  massKind: { src: ["wg"] },
};

const state = { meta: null, index: [], shards: {}, why: [], wording: { texts: {}, labels: {} }, updates: [], page: 0, filtered: [] };
const unmark = (t) => (typeof t === "string" ? t.replace(/\*\*/g, "") : t);
const W = (key) => { const w = state.wording.texts[key]; return w ? { compare: unmark(w.compare), means: unmark(w.means), details: unmark(w.details) } : null; };
const LABEL = (key) => state.wording.labels[key] || key;

const el = (tag, attrs = {}, ...children) => {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null) continue;
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else node.setAttribute(k, v);
  }
  for (const c of children) if (c != null) node.append(c);
  return node;
};
const safeUrl = (u) => (typeof u === "string" && u.startsWith("https://") ? u : null);
const link = (label, url) => {
  const href = safeUrl(url);
  return href ? el("a", { href, rel: "noopener", text: label }) : document.createTextNode(label);
};
const num = (x, d = 4) => (x == null ? "" : String(Number(Number(x).toPrecision(d))));
const planetHref = (name) => `#/planet/${encodeURIComponent(name)}`;
const WHAT = {
  radius: ["size", "radius", "Earths"], density: ["density", "density", "g/cm³"],
  kepler: ["orbit size", "orbit", "au"], a_over_rstar: ["orbit in star sizes", null, ""],
};
function renderHome() {
  const count = (f) => state.index.filter(f).length.toLocaleString();
  document.getElementById("scope-findings").textContent = `with findings (${count((p) => openCount(p) > 0)})`;
  document.getElementById("scope-notes").textContent = `with notes (${count((p) => (p.nk || []).length > 0)})`;
  document.getElementById("scope-all").textContent = `all (${state.index.length.toLocaleString()})`;
  typeOptions();
}
function typeOptions() {
  const f = document.getElementById("filters"), sel = f.type, keep = sel.value, scope = f.scope.value;
  const tally = (field) => { const t = new Map(); for (const p of state.index) for (const k of p[field] || []) t.set(k, (t.get(k) || 0) + 1); return t; };
  const group = (label, prefix, t) => el("optgroup", { label }, ...[...t.entries()].sort((x, y) => y[1] - x[1])
    .map(([k, n]) => el("option", { value: `${prefix}:${k}`, text: `${LABEL(k)} (${n.toLocaleString()})` })));
  sel.replaceChildren(el("option", { value: "", text: "any" }),
    scope !== "notes" ? group("findings", "f", tally("fk")) : null, scope !== "findings" ? group("notes", "n", tally("nk")) : null);
  sel.value = [...sel.options].some((o) => o.value === keep) ? keep : "";
}
const gap = (x) => (x.a && x.b ? Math.abs(Math.log(Math.abs(x.a / x.b))) : 0);

function openCount(p) { return p.a + p.b + p.c + (p.x || 0) + (p.e || 0); }
const shownFindings = (p) => p.nf ?? openCount(p);
const shownNotes = (p) => p.nn ?? (p.l || 0);

function renderList() {
  const f = document.getElementById("filters");
  const q = f.q.value.trim().toLowerCase();
  const scope = f.scope.value, [kind, key] = (f.type.value || ":").split(/:(.*)/s);
  let list = state.index.filter((p) => scope === "all" || (scope === "findings" ? openCount(p) > 0 : (p.nk || []).length > 0));
  if (key) list = list.filter((p) => (p[kind === "f" ? "fk" : "nk"] || []).includes(key));
  if (q) list = list.filter((p) => p.n.toLowerCase().includes(q) || (p.h || "").toLowerCase().includes(q) || p.refs.some((r) => r.toLowerCase().includes(q)));
  const az = (x, y) => x.n.localeCompare(y.n, "en", { numeric: true });
  const sorts = {
    az, findings: (x, y) => shownFindings(y) - shownFindings(x) || az(x, y), notes: (x, y) => shownNotes(y) - shownNotes(x) || az(x, y),
    year: (x, y) => (y.y || 0) - (x.y || 0) || az(x, y),
  };
  list.sort(sorts[f.sort.value] || az);
  state.filtered = list;
  document.getElementById("count").textContent = `${list.length.toLocaleString()} planet${list.length === 1 ? "" : "s"}`;
  document.getElementById("list").replaceChildren(...list.slice(state.page * PAGE, (state.page + 1) * PAGE).map((p) => {
    const n = shownFindings(p), nn = shownNotes(p);
    const tags = el("span", { class: "tags" },
      el("span", { class: "tag", text: `${p.p} paper${p.p === 1 ? "" : "s"}` }),
      n ? el("span", { class: "tag look", text: `${n} finding${n === 1 ? "" : "s"}` }) : null,
      p.em ? el("span", { class: "tag note", text: "mass estimated" }) : null,
      nn && !p.em ? el("span", { class: "tag note", text: `${nn} note${nn === 1 ? "" : "s"}` }) : null,
      null);
    return el("li", {}, el("a", { href: planetHref(p.n) },
      el("span", { class: "pname", text: p.n }, el("span", { class: "psub", text: [p.h, p.d, p.y].filter(Boolean).join(" · ") })),
      tags));
  }));
  renderPager(Math.ceil(list.length / PAGE));
}

function renderPager(pages) {
  for (const id of ["pager-top", "pager"]) pagerInto(document.getElementById(id), pages);
}
function pagerInto(nav, pages) {
  nav.hidden = pages <= 1;
  if (nav.hidden) return nav.replaceChildren();
  const cur = state.page;
  const go = (i, text, label) => el("button", { type: "button", class: i === cur ? "current" : "", "data-page": i,
    "aria-label": label || `page ${i + 1}`, "aria-current": i === cur ? "page" : null, text });
  const items = [cur > 0 ? go(cur - 1, "<--", "previous page") : null];
  let last = -1;
  for (let i = 0; i < pages; i++) {
    if (i !== 0 && i !== pages - 1 && Math.abs(i - cur) > 2) continue;
    if (i - last > 1) items.push(el("span", { class: "gap", text: "…" }));
    items.push(go(i, String(i + 1)));
    last = i;
  }
  items.push(cur < pages - 1 ? go(cur + 1, "-->", "next page") : null);
  nav.replaceChildren(...items.filter(Boolean));
}

function exportCsv() {
  const cols = ["planet", "star", "papers", "findings", "notes", "values_possible", "row_adds_up", "nasa_catalog", "exoplanet_eu", "gaia_dr3", "finding_types", "note_types", "found_by", "year", "url"];
  const esc = (v) => { let s = String(v ?? ""); if (/^[=+\-@]/.test(s)) s = "'" + s; return `"${s.replace(/"/g, '""')}"`; };
  const lines = [cols.join(",")].concat(state.filtered.map((p) => [p.n, p.h, p.p, shownFindings(p), shownNotes(p), p.a, p.b, p.c, p.x || 0, p.e || 0,
    (p.fk || []).map(LABEL).join("; "), (p.nk || []).map(LABEL).join("; "), p.d, p.y, location.href.split("#")[0] + planetHref(p.n)].map(esc).join(",")));
  const blob = new Blob([lines.join("\n") + "\n"], { type: "text/csv" });
  const a = el("a", { href: URL.createObjectURL(blob), download: `exodiff-planets-${state.meta.snapshot_retrieved_at_utc.slice(0, 10)}.csv` });
  document.body.append(a); a.click(); a.remove();
}

const publicDate = () => ((state.meta.check_c || {}).public_snapshot || {}).retrieved_at_utc?.slice(0, 10) || "the last update";
const euDate = () => (state.meta.check_d || {}).eu_retrieved_at_utc?.slice(0, 10) || "the last update";
async function loadPlanet(name) {
  const entry = state.index.find((p) => p.n === name);
  if (!entry) return null;
  if (!state.shards[entry.s]) {
    const res = await fetch(`data/planets/${String(entry.s).padStart(2, "0")}.json`, { cache: "no-cache" });
    if (!res.ok) throw new Error(`planet data returned ${res.status}`);
    state.shards[entry.s] = await res.json();
  }
  return state.shards[entry.s][name];
}

const COLUMN = {
  pl_rade: "size (Earths)", pl_radj: "size (Jupiters)", pl_bmasse: "mass (Earths)", pl_bmassj: "mass (Jupiters)",
  pl_masse: "mass (Earths)", pl_massj: "mass (Jupiters)", pl_msinie: "minimum mass (Earths)", pl_msinij: "minimum mass (Jupiters)",
  pl_orbper: "orbit time", pl_orbsmax: "orbit size", pl_orbeccen: "orbit stretch", pl_dens: "density",
  pl_ratdor: "orbit in star sizes", pl_ratror: "size ratio", st_rad: "star size", st_mass: "star mass", sy_dist: "distance",
  st_age: "star age", st_teff: "star temperature", st_met: "star metallicity", st_lum: "star brightness", pl_orbincl: "orbit tilt",
};
const plain = (text) => String(text || "").replace(/\b(pl|st|sy)_[a-z0-9]+\b/g, (c) => COLUMN[c] || c);
const sources = (keys) => (keys && keys.length
  ? el("p", { class: "cite" }, "source: ", ...keys.flatMap((k, i) => [i ? ", " : null, link(SRC[k][0], SRC[k][1])]).filter(Boolean))
  : null);
const lineP = (label, text) => (text ? el("p", { class: "line" }, el("span", { class: "k", text: label }), el("span", { text })) : null);
const CHECK_NAME = { A: "values possible?", B: "row adds up?", C: "NASA catalog data", D: "exoplanet.eu", E: "Gaia DR3", F: "NASA catalog page text" };

const SAME_AS_CHECK = new Set(["other", "unit-copies", "catalog", "impossible", "letters"]);
function whyText(w, lead) {
  if (w.id === "double") {
    return lead.rule === "period"
      ? "exactly double or half. Gaps in the observations can leave an orbit time ambiguous (aliasing, Wright & Gaudi 2013); a doubled or halved value would fit that."
      : "exactly double or half. A diameter stored as a radius, or a factor of two lost in a calculation, would fit that.";
  }
  return `${w.title.toLowerCase()}. ${w.why}`;
}
const COL_FIELD = {
  pl_rade: "radius", pl_radj: "radius", pl_bmasse: "mass", pl_bmassj: "mass", pl_masse: "mass", pl_massj: "mass",
  pl_msinie: "mass", pl_msinij: "mass", pl_orbper: "period", pl_orbsmax: "orbit", pl_orbeccen: "eccentricity",
  sy_dist: "distance", pl_ratror: "ratio", st_rad: "star_radius", st_mass: "star_mass", pl_ratdor: "a_rstar", pl_dens: "density",
};
const B_CELLS = {
  radius: ["radius", "ratio", "star_radius"], density: ["density", "mass", "radius"],
  kepler: ["orbit", "period", "star_mass"], a_over_rstar: ["a_rstar", "orbit", "star_radius"],
};
const EXTRA_COLS = [["ratio", "size ratio", ""], ["star_radius", "star size", "Suns"], ["star_mass", "star mass", "Suns"],
  ["a_rstar", "orbit in star sizes", ""], ["density", "density", "g/cm³"]];

const NOUN = { radius: "size", mass: "mass", period: "orbit time", orbit: "orbit size", eccentricity: "orbit stretch", distance: "distance" };
const B_TITLE = {
  radius: "The size doesn't follow from the row's own size ratio and star size",
  density: "The density doesn't follow from the row's own mass and size",
  kepler: "The orbit size doesn't follow from the row's own orbit time and star mass",
  a_over_rstar: "The orbit in star sizes doesn't follow from the row's own orbit size and star size",
};
const UNIT_OF = { radius: "Earths", mass: "Earths", period: "days", orbit: "au", eccentricity: "", distance: "parsecs" };
const range = (v) => (v && v.v != null ? { v: Number(v.v), lo: v.e2 != null ? Number(v.v) + Number(v.e2) : null, hi: v.e1 != null ? Number(v.v) + Number(v.e1) : null } : null);
const overlaps = (a, b) => a && b && a.lo != null && a.hi != null && b.lo != null && b.hi != null && Math.max(a.lo, b.lo) <= Math.min(a.hi, b.hi);

function compare(subject, a, ref, b) {
  if (a == null || b == null || !Number.isFinite(a / b) || a / b <= 0) return a != null && b != null ? `${subject} is ${num(a, 6)}, ${ref} ${num(b, 6)}` : "";
  const r = a / b;
  if (r >= 1.995) return `${subject} is ${num(r, 3)}× ${ref}`;
  if (r <= 1 / 1.995) return `${ref} is ${num(1 / r, 3)}× ${subject}`;
  const p = Math.abs((r - 1) * 100);
  return `${subject} is ${p < 10 ? p.toFixed(1) : Math.round(p)}% ${r > 1 ? "higher" : "lower"} than ${ref}`;
}
function bigMass(planet) {
  const measured = planet.papers.filter((p) => p.values.mass && !p.values.mass.lim);
  const ref = measured.find((p) => p.default) || measured[0];
  return !!ref && ref.values.mass.v >= 30;
}
function massPair(planet, defMass, euEarth, eu) {
  const j = defMass && defMass.j;
  if (!j || !bigMass(planet)) return null;
  return [range(j), { v: euEarth / JUP_M, lo: eu.em != null ? (euEarth - Math.abs(eu.em)) / JUP_M : null, hi: eu.ep != null ? (euEarth + Math.abs(eu.ep)) / JUP_M : null }];
}

function planFindings(planet) {
  const def = planet.papers.find((p) => p.default) || { values: {}, ref: null };
  const groups = new Map();
  for (const l of planet.leads) {
    const key = l.group || (l.label_only ? `${l.kind}|${l.rule}|${l.bucket || ""}|${l.title || ""}`
      : `${l.kind}|${l.rule}|${l.ref || ""}|${(l.pair || []).map((x) => num(x, 4)).join("/")}`);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(l);
  }
  const all = [...groups.values()];
  const open = all.filter((g) => !g[0].label_only).sort((x, y) => gap({ a: pairOf(y[0])[0], b: pairOf(y[0])[1] }) - gap({ a: pairOf(x[0])[0], b: pairOf(x[0])[1] }));
  const soft = all.filter((g) => g[0].label_only);
  const plan = { open: [], soft: [], agree: new Map(), papers: new Map(), extra: new Set(), kinds: new Set(), whys: new Map() };
  let n = 0;
  for (const g of [...open, ...soft]) {
    const k = ++n, l = g[0], isSoft = !!l.label_only;
    const f = { n: k, soft: isSoft, leads: g, l, count: g.length };
    markCells(planet, def, g, k, isSoft, plan);
    (isSoft ? plan.soft : plan.open).push(f);
    plan.kinds.add(l.kind === "C" && l.rule === "label" ? "massKind" : l.kind === "B" ? l.rule : l.kind === "A" ? `A:${l.rule}` : l.kind);
    if (!isSoft && l.why && !SAME_AS_CHECK.has(l.why)) {
      const w = state.why.find((x) => x.id === l.why);
      if (w) plan.whys.set(w.id, [w, l]);
    }
  }
  return plan;
}

function markCells(planet, def, g, k, soft, plan) {
  const add = (map, key) => { if (!map.has(key)) map.set(key, []); if (!map.get(key).some((m) => m.n === k)) map.get(key).push({ n: k, soft }); };
  for (const l of g) {
    if (l.kind === "C") add(plan.agree, `${l.rule === "label" ? l.field : l.rule}|catalog`);
    else if (l.kind === "F") add(plan.agree, `${l.rule}|catalog`);
    else if (l.kind === "D") (l.fields || [l.rule]).forEach((x) => add(plan.agree, `${x}|eu`));
    else if (l.kind === "E") add(plan.agree, "distance|nasa");
    else {
      const rows = planet.papers.map((p, i) => [p, i]).filter(([p]) => l.ref && p.ref === l.ref);
      let fields;
      if (l.kind === "B") {
        fields = B_CELLS[l.rule] || [];
        const own = rows.filter(([p]) => p.values[fields[0]] && Number(p.values[fields[0]].v) === Number(l.listed));
        const use = own.length ? own : rows;
        use.forEach(([, i]) => fields.forEach((f) => add(plan.papers, `${i}|${f}`)));
        if (use.some(([p]) => p.default)) add(plan.agree, `${fields[0]}|nasa`);
      } else {
        fields = [...new Set(String(l.column || "").split(",").map((c) => COL_FIELD[c.trim()]).filter(Boolean))];
        rows.forEach(([, i]) => (fields.length ? fields : ["paper"]).forEach((f) => add(plan.papers, `${i}|${f}`)));
        if (rows.some(([p]) => p.default)) fields.filter((f) => FIELDS.some(([x]) => x === f)).forEach((f) => add(plan.agree, `${f}|nasa`));
      }
      fields.filter((f) => EXTRA_COLS.some(([e]) => e === f)).forEach((f) => plan.extra.add(f));
    }
  }
}

function describeFinding(planet, f) {
  const l = f.l;
  const def = planet.papers.find((p) => p.default) || { values: {}, ref: null };
  const defRef = def.ref || "NASA's default paper";
  const field = l.kind === "B" ? (WHAT[l.rule] || [])[1] : l.kind === "E" ? "distance" : l.rule;
  const unit = l.kind === "B" ? (WHAT[l.rule] || [])[2] : UNIT_OF[field] || "";
  if (l.kind === "D" && l.bucket === "D-letters") {
    const pairs = l.fields.map((x) => { const e = (planet.eu || {})[x] || {}; return `${NOUN[x]}: exoplanet.eu ${num(e.v, 6)}, NASA ${num(e.nasa, 6)}${UNIT_OF[x] ? " " + UNIT_OF[x] : ""}`; });
    return {
      title: "exoplanet.eu may give this planet a different letter",
      bars: null,
      gapText: `exoplanet.eu's ${l.fields.map((x) => NOUN[x]).join(", ")} for this planet match NASA's values for another planet around the same star (${pairs.join("; ")}).`,
      facts: [l.shared_alias ? `exoplanet.eu also calls this planet “${l.shared_alias}”, which NASA lists as a name of ${l.alias_of}.` : null],
    };
  }
  if (l.kind === "D") {
    const eu = (planet.eu || {})[l.rule] || {};
    const own = l.row != null ? planet.papers.find((p) => p.ref === l.matched && p.values[l.rule] && Number(p.values[l.rule].v) === Number(l.row)) : null;
    const base = own || def;
    let a = range(base.values[l.rule]);
    let b = { v: l.eu, lo: eu.em != null ? l.eu - Math.abs(eu.em) : null, hi: eu.ep != null ? l.eu + Math.abs(eu.ep) : null };
    let u = unit;
    const mj = l.rule === "mass" ? massPair(planet, base.values.mass, l.eu, eu) : null;
    if (mj) { [a, b] = mj; u = "Jupiters"; }
    const higher = b.v > (a ? a.v : l.nasa);
    const ecc = l.rule === "eccentricity";
    const rows = planet.papers.map((p) => p.values[l.rule]).filter(Boolean)
      .map((v) => (mj ? (v.j ? v.j.v : v.v / JUP_M) : v.v)).filter((v) => v != null).map(Number);
    const beyondAll = rows.length && (higher ? b.v > Math.max(...rows) : b.v < Math.min(...rows));
    const title = l.bucket === "D-newer-paper" ? `exoplanet.eu's ${NOUN[l.rule]} comes from a paper newer than any in NASA's archive`
      : l.matched ? `exoplanet.eu and NASA cite the same paper but give a different ${NOUN[l.rule]}`
      : `exoplanet.eu lists a ${higher ? "higher" : "lower"} ${NOUN[l.rule]} than ${beyondAll ? "any paper NASA has" : "NASA's default paper"}`;
    return {
      title,
      bars: [[`NASA · ${own ? own.ref : defRef}`, a, "nasa"], [`exoplanet.eu${l.source ? ` · ${l.source}` : ""}`, b, "other"]], unit: u,
      gapText: `${ecc ? `exoplanet.eu's value is ${num(Math.abs(b.v - (a ? a.v : l.nasa)), 3)} ${higher ? "higher" : "lower"} than NASA's` : compare("exoplanet.eu's value", b.v, "NASA's", a ? a.v : l.nasa)} · ${l.bars != null && Number.isFinite(l.bars) ? `${num(l.bars, 2)} error bars apart` : overlaps(a, b) ? "ranges overlap" : "ranges don't overlap"}`,
      facts: [l.source ? (l.source.includes(";")
          ? `exoplanet.eu's page lists ${l.source} for this value${l.bucket === "D-newer-paper" ? "; NASA's archive holds none of them" : ""}.`
          : `exoplanet.eu's page gives ${l.source} as the source of this value${l.matched ? `; NASA's archive has it as ${l.matched}` : l.bucket === "D-newer-paper" ? "; NASA's archive may not have this paper yet" : ""}.`) : null,
        l.shared_alias ? `exoplanet.eu also calls this planet “${l.shared_alias}”, which NASA lists as a name of ${l.alias_of}.` : null],
    };
  }
  if (l.kind === "E") {
    const g = planet.gaia || {};
    const a = range(def.values.distance);
    const b = { v: l.gaia, lo: g.lo, hi: g.hi };
    const scale = (l.gaia / l.nasa - 1) * 100;
    const shown = (Math.max(l.nasa, l.gaia) / Math.min(l.nasa, l.gaia) - 1) * 100;
    return {
      title: l.ref === "TICv8" ? `NASA's distance predates Gaia DR3: ${shown.toFixed(1)}% ${l.nasa > l.gaia ? "farther" : "nearer"} than Gaia DR3's`
        : `NASA's distance is ${shown.toFixed(1)}% ${l.nasa > l.gaia ? "farther" : "nearer"} than Gaia DR3's`,
      bars: [[`NASA · ${l.ref || "?"}`, a, "nasa"], ["Gaia DR3", b, "other"]], unit: "parsecs",
      gapText: `${shown.toFixed(1)}% apart · ${overlaps(a, b) ? "ranges overlap" : "ranges don't overlap"}`,
      facts: [(l.same_star || []).length ? `This is about the star, so it also shows on ${l.same_star.join(", ")}.` : null,
        l.star_from_catalogue ? `The row's star size comes from the TESS Input Catalog, where a star's size scales with its distance (Stassun et al. 2019, eq. 4): with Gaia DR3's distance it would be about ${Math.abs(scale).toFixed(0)}% ${scale > 0 ? "larger" : "smaller"}, and so would any planet size computed from it.` : null],
    };
  }
  if (l.kind === "C") {
    const a = range(def.values[l.rule]);
    const [, pv] = pairOf(l);
    return {
      title: l.rule === "distance" ? "NASA catalog data (not shown on the page) has a distance no NASA paper has"
        : `NASA catalog data (behind its page) has a ${NOUN[l.rule]} that no NASA paper has`,
      bars: [[`NASA archive · ${defRef}`, a, "nasa"], ["catalog page", pv != null ? { v: pv } : null, "other"]], unit,
      gapText: pv != null && a ? compare("the catalog page's value", pv, "the archive's", a.v) : `page shows ${l.display}`,
    };
  }
  if (l.kind === "B") {
    const row = planet.papers.find((p) => p.ref === l.ref && p.values[field] && Number(p.values[field].v) === Number(l.listed));
    const a = range(row ? row.values[field] : { v: l.listed });
    return {
      title: l.transit_fit ? "The paper's orbit size (from the transit fit) doesn't fit its star mass" : B_TITLE[l.rule] || "The row's numbers don't fit together",
      bars: [[`listed · ${l.ref}`, a, "nasa"], ["from the row's other numbers", { v: l.implied }, "other"]], unit,
      gapText: `${compare("the listed value", l.listed, "what the row's other numbers give", l.implied)}${l.bars ? ` · ${num(l.bars, 2)}× the row's own uncertainty` : ""}`,
      facts: [["B-cat", "B-src"].includes(l.bucket) ? `Context: ${l.fine_when}` : null,
        l.transit_numeric_only ? "This orbit size equals the row's distance in star sizes × the star's size. The orbit is stretched, and for a stretched orbit that distance is measured at mid-transit, so this is only a numerical match." : null],
    };
  }
  const [a, b] = pairOf(l);
  if (l.kind === "A" && (l.rule === "A5" || l.rule === "A5m") && a != null && b != null) {
    const noun = NOUN[COL_FIELD[l.column]] || "value";
    return {
      title: `The Earth-unit and Jupiter-unit copies of the ${noun} disagree`,
      bars: [[`Earth copy · ${l.ref}`, { v: a }, "nasa"], ["Jupiter copy, converted", { v: b }, "other"]], unit: "Earths",
      gapText: compare("the Earth copy", a, "the converted Jupiter copy", b),
    };
  }
  return { title: l.title ? l.title[0].toUpperCase() + l.title.slice(1) : "A value that can't be right", bars: null,
    gapText: plain(l.detail || "") };
}

function axisFormat(lo, hi) {
  const dec = Math.min(8, Math.max(0, Math.ceil(-Math.log10((hi - lo) / 3 || 1)) + 1));
  const fmtTick = (v) => (dec > 0 ? Number(v).toFixed(dec) : num(v, 3));
  const fmtVal = (v) => {
    const str = Number(Number(v).toPrecision(10)).toFixed(20).replace(/0+$/, "");
    const own = (str.split(".")[1] || "").length;
    const sig = v ? Math.max(0, 2 - Math.floor(Math.log10(Math.abs(v)))) : 0;
    const t = Number(v).toFixed(Math.min(own, Math.max(dec + 1, 4, sig)));
    return t.includes(".") ? t.replace(/0+$/, "").replace(/\.$/, "") : t;
  };
  return { fmtTick, fmtVal };
}

function rangeChart(bars, unit) {
  const rows = bars.filter(([, r]) => r && r.v != null && Number.isFinite(r.v));
  if (rows.length < 2) return null;
  const xs = rows.flatMap(([, r]) => [r.v, r.lo, r.hi]).filter((x) => x != null && Number.isFinite(x));
  let lo = Math.min(...xs), hi = Math.max(...xs);
  const pad = (hi - lo || Math.abs(hi) || 1) * 0.08;
  lo -= pad; hi += pad;
  const box = (document.getElementById("planet") || {}).clientWidth || 680;
  const W = Math.max(320, Math.min(680, box - 40)), narrow = W < 520;
  const L = narrow ? 118 : 210, R = narrow ? 84 : 150, rowH = 30, max = narrow ? 16 : 30, H = rows.length * rowH + 24;
  const x = (v) => L + ((v - lo) / (hi - lo)) * (W - L - R);
  const { fmtTick, fmtVal } = axisFormat(lo, hi);
  const NS = "http://www.w3.org/2000/svg";
  const s = (tag, attrs, text) => { const n = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v); if (text != null) n.textContent = text; return n; };
  const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, class: "range-chart", role: "img",
    "aria-label": rows.map(([label, r]) => `${label}: ${num(r.v, 6)}${r.lo != null ? ` (${num(r.lo, 4)} to ${num(r.hi, 4)})` : ""}`).join("; ") });
  rows.forEach(([label, r, cls], i) => {
    const y = 14 + i * rowH;
    svg.append(s("text", { x: 0, y: y + 4, class: "rc-label" }, label.length > max ? label.slice(0, max - 1) + "…" : label));
    const g = s("g", { class: `rc-${cls}` });
    g.append(s("title", {}, `${label}: ${num(r.v, 6)}${r.lo != null && r.hi != null ? ` (range ${num(r.lo, 4)} to ${num(r.hi, 4)})` : " (no range given)"}${unit ? " " + unit : ""}`));
    if (r.lo != null && r.hi != null) g.append(s("rect", { x: x(r.lo), y: y - 3, width: Math.max(2, x(r.hi) - x(r.lo)), height: 6, rx: 3, class: "rc-bar" }));
    g.append(s("circle", { cx: x(r.v), cy: y, r: 5, class: "rc-dot" }));
    svg.append(g);
    const err = r.lo != null && r.hi != null ? ` ${fmtVal(r.lo)}–${fmtVal(r.hi)}` : "";
    svg.append(s("text", { x: W - R + 12, y: y + 4, class: "rc-value" }, fmtVal(r.v)));
    if (err) svg.append(s("text", { x: W - R + 12, y: y + 16, class: "rc-tick" }, err.trim()));
  });
  const ay = rows.length * rowH + 8;
  svg.append(s("line", { x1: L, x2: W - R, y1: ay, y2: ay, class: "rc-axis" }));
  [lo + pad, (lo + hi) / 2, hi - pad].forEach((t) => svg.append(s("text", { x: x(t), y: ay + 13, class: "rc-tick", "text-anchor": "middle" }, fmtTick(t))));
  return el("figure", { class: "rc" }, svg, unit ? el("figcaption", {}, el("span", { class: "unit-name", text: unit })) : null);
}

function findingCard(planet, f) {
  const d = describeFinding(planet, f);
  const notes = (planet.nasa_notes || []).filter((x) => x.ref && x.ref === f.l.ref);
  const w = f.l.why && !SAME_AS_CHECK.has(f.l.why) ? state.why.find((x) => x.id === f.l.why) : null;
  return el("article", { class: "finding", id: `f${f.n}` },
    el("div", { class: "finding-head" }, el("span", { class: "tag look", text: `[${f.n}] finding` }),
      el("span", { class: "check", text: `${CHECK_NAME[f.l.kind]}${f.count > 1 ? ` · ${f.count} columns` : ""}` })),
    el("h3", { text: d.title }),
    d.bars ? rangeChart(d.bars, d.unit) : null,
    el("p", { class: "gap-line", text: d.gapText }),
    w ? el("p", { class: "line" }, el("span", { class: "k", text: "pattern" }), w.title.toLowerCase()) : null,
    ...(d.facts || []).filter(Boolean).map((x) => el("p", { class: "line", text: x })),
    ...notes.map((x) => el("p", { class: "line" }, el("span", { class: "k", text: "NASA's note" }), x.text)),
    ...plainLayers(f.l.key));
}
function plainLayers(key) {
  const w = W(key);
  if (!w) return [];
  return [el("p", { class: "what", text: w.means }),
    w.compare || w.details ? el("details", { class: "fold small" }, el("summary", { text: "how this was checked" }),
      w.compare ? lineP("what we compare", w.compare) : null, w.details ? el("p", { class: "muted", text: shortDetails(w.details) }) : null) : null];
}
function shortDetails(text) {
  const stat = state.wording.statistic || "";
  return stat && text.includes(stat) ? text.replace(stat, "").trim() : text;
}

function softLine(planet, f) {
  const l = f.l, rows = f.count > 1 ? ` (${f.count} rows)` : "";
  const noun = NOUN[l.rule], u = UNIT_OF[l.rule] ? ` ${UNIT_OF[l.rule]}` : "";
  const li = (text, reason) => el("li", { id: `f${f.n}` }, el("span", { class: "ref", text: `[${f.n}] ` }), text,
    reason ? el("span", { class: "muted", text: ` ${reason}` }) : null);
  const reason = (W(l.key) || {}).means || "";
  if (l.kind === "B") {
    const note = l.bucket === "B-doc" ? (planet.nasa_notes || []).find((x) => x.ref === l.ref) : null;
    const pct = l.pct != null ? ` (${l.pct >= 0 ? "+" : ""}${num(l.pct, 2)}%)` : "";
    return li(`${l.ref}: ${(B_TITLE[l.rule] || "row doesn't add up").toLowerCase()}; listed ${num(l.listed, 6)}, from the row's other values ${num(l.implied, 6)}${pct}.`
      + (note ? ` NASA's note: “${note.text}”` : ""), reason);
  }
  if (l.kind === "D") {
    const defMass = ((planet.papers.find((p) => p.default) || { values: {} }).values.mass || {});
    const inJup = l.rule === "mass" && l.row == null && bigMass(planet) && defMass.j;
    const ours = inJup ? `exoplanet.eu's mass is ${num(l.eu / JUP_M, 4)} Jupiters, NASA's ${num(defMass.j.v, 6)} Jupiters`
      : l.row != null ? `exoplanet.eu's ${noun} is ${num(l.eu, 6)}${u} (${l.source}); NASA's row from ${l.matched} gives ${num(l.row, 6)}${u}`
      : `exoplanet.eu's ${noun} is ${num(l.eu, 6)}${u}, NASA's ${num(l.nasa, 6)}${u}`;
    if (l.bucket === "D-no-errors") {
      const gap = l.rule === "eccentricity" ? `${num(Math.abs(l.eu - l.nasa), 3)} apart` : `${Math.round(Math.abs(l.eu / l.nasa - 1) * 100)}% apart`;
      const def = planet.papers.find((p) => p.default) || { values: {} };
      const dv = def.values[l.rule] || {}, ev = (planet.eu || {})[l.rule] || {};
      const missing = [dv.e1 == null && dv.e2 == null ? "NASA" : null, ev.em == null && ev.ep == null ? "exoplanet.eu" : null].filter(Boolean);
      const g = l.rule === "distance" && planet.gaia && planet.gaia.v ? ` Gaia DR3 gives ${num(planet.gaia.v, 6)} parsecs.` : "";
      return li(`${ours} (${gap}); ${missing.join(" and ") || "one side"} give${missing.length === 1 ? "s" : ""} no uncertainty.${g}`, reason);
    }
    if (l.bucket === "D-limit") {
      const lim = (((planet.papers.find((p) => p.default) || { values: {} }).values[l.rule]) || {}).lim;
      const ev0 = (planet.eu || {})[l.rule] || {};
      const euLimit = ev0.em != null && Math.abs(Math.abs(ev0.em) - l.eu) <= 0.001 * l.eu && !ev0.ep;
      return li(euLimit ? `exoplanet.eu gives an upper limit of ${num(l.eu, 6)}${u} for the ${noun}; NASA's ${lim ? `${lim < 0 ? "lower" : "upper"} limit is` : "value is"} ${num(l.nasa, 6)}${u}.`
        : `NASA gives ${lim < 0 ? "a lower" : "an upper"} limit of ${num(l.nasa, 6)}${u} for the ${noun}; exoplanet.eu's is ${num(l.eu, 6)}${u}.`, reason);
    }
    const extra = { "D-eu-paper": ` (exoplanet.eu cites ${l.source})`, "D-other-row": `; it fits the row from ${l.matched}`,
      "D-close": `: ${num(l.bars, 2)} × the combined uncertainty apart`, "D-theoretical": " (labelled theoretical by exoplanet.eu)" }[l.bucket] || "";
    return li(`${ours}${extra}.`, reason);
  }
  if (l.kind === "E") return li(`NASA's distance is ${num(l.nasa, 6)} parsecs, Gaia DR3's ${num(l.gaia, 6)}. Gaia flag: ${l.quality || "quality screen"}.`, reason);
  if (l.kind === "F") {
    const why = { "older-paper": ` The sentence's number matches ${l.paper || "a published solution"} in NASA's archive, so the two parts were probably written from different sets of values.`,
      "box-unknown": " The facts box says Unknown while the sentence gives a number.",
      calculated: " No paper gives it directly; both numbers look calculated, from different inputs." }[l.cause] || "";
    return el("li", { id: `f${f.n}`, class: why ? "has-why" : null, title: why ? why.trim() : null }, el("span", { class: "ref", text: `[${f.n}] ` }),
      `On NASA's catalog page the summary sentence gives the ${noun} as ${l.sentence}, the facts box as ${l.box}.`,
      why ? el("span", { class: "why-hint", text: " (why?)" }) : null);
  }
  if (l.kind === "C" && l.rule === "label") return li(`${l.title[0].toUpperCase() + l.title.slice(1)}.`, "");
  if (l.kind === "C") {
    const arch = ((planet.papers.find((p) => p.default) || { values: {} }).values[l.rule] || {}).v;
    const text = l.bucket === "C-survey" ? `NASA's catalog data gives a distance of ${l.display} parsecs; the archive has ${num(arch, 8)} (${Math.abs((Number(l.display) / arch - 1) * 100).toFixed(1)}% apart).`
      : l.bucket === "C-estimate" ? `NASA's catalog gives the ${noun} as an estimate: ${l.display} Earths.`
      : `NASA's catalog data gives the ${noun} as ${l.display}, the value from ${l.matched}.`;
    return li(text, reason);
  }
  if (l.rule === "A5r") {
    const re = /^(\w+) = ([-0-9.e+]+), \w+ = ([-0-9.e+]+) \(x[0-9.]+ = ([-0-9.e+]+), rounded to (\d+)/;
    const pairs = [...new Set(f.leads.map((x) => { const m = re.exec(x.detail || ""); return m ? `${num(m[3], 4)} Jupiters stored as ${num(m[2], 6)} Earths, not ${num(m[4], 4)}` : null; }).filter(Boolean))];
    const refs = [...new Set(f.leads.map((x) => x.ref).filter(Boolean))];
    const worst = Math.max(...f.leads.map((x) => { const m = re.exec(x.detail || ""); return m ? Math.abs(Number(m[2]) / Number(m[4]) - 1) * 100 : 0; }));
    return li(`${refs.join(", ")}: ${pairs.join("; ")}.` + (worst >= 5 ? ` The rounded copy ends up ${worst.toFixed(0)}% off the Jupiter value, more than rounding usually needs.` : ""), reason);
  }
  if (l.rule === "A7") {
    const m = /^(\d+) rows; differing: ([^;]+)(?:; the rows also differ in (.+))?$/.exec(l.detail || "");
    return li(m ? `${l.ref} has ${m[1]} rows with a different ${plain(m[2]).replace(/ \(Earths\)/g, "")}${m[3] ? `; the rows also assume a different ${plain(m[3])}` : ""}.` : `${l.ref}: ${plain(l.detail)}.`, reason);
  }
  return li(`${l.title[0].toUpperCase() + l.title.slice(1)}${rows}${l.ref ? `, ${l.ref}` : ""}: ${plain(l.detail)}.`, reason);
}

function findingsSection(planet, plan, name) {
  const otherNotes = (planet.nasa_notes || []).filter((x) => !planet.leads.some((l) => l.ref && l.ref === x.ref && !l.label_only));
  const verdict = plan.open.length
    ? `${plan.open.length} finding${plan.open.length === 1 ? "" : "s"}${plan.soft.length ? ` · ${plan.soft.length} note${plan.soft.length === 1 ? "" : "s"}` : ""}`
    : `No findings.${plan.soft.length ? ` ${plan.soft.length} note${plan.soft.length === 1 ? "" : "s"}.` : ""}`;
  return el("section", { class: "findings" },
    el("h2", { class: "section-title", text: "findings" }),
    el("p", { class: "verdict", text: verdict }),
    plan.open.length && W("general/finding") ? el("p", { class: "muted", text: W("general/finding").means }) : null,
    ...plan.open.map((f) => findingCard(planet, f)),
    plan.open.length ? null : el("p", { class: "clean", text: cleanText(name) }),
    plan.soft.length ? el("details", { class: "fold" }, el("summary", { text: `notes (${plan.soft.length})` }),
      W("general/note") ? el("p", { class: "muted", text: W("general/note").means }) : null,
      el("ul", { class: "soft-list" }, ...plan.soft.map((f) => softLine(planet, f)))) : null,
    otherNotes.length ? el("details", { class: "fold" }, el("summary", { text: `NASA's own notes on this planet (${otherNotes.length})` }),
      el("ul", { class: "soft-list" }, ...otherNotes.map((x) => el("li", {}, x.text,
        el("span", { class: "muted", text: ` ${[x.ref, x.date].filter(Boolean).join(", ")}${x.on === "star" ? " (on the star)" : x.on === "system" ? " (on the system)" : ""}` })))))
      : null);
}

function markedCell(content, marks, extra) {
  const open = (marks || []).some((m) => !m.soft);
  return el("td", { class: `num${open ? " flagged" : ""}` }, ...content,
    ...(marks || []).map(markLink), ...(extra || []));
}
const markLink = (m) => el("sup", { class: `ref ${m.soft ? "soft" : "lead"}` },
  el("button", { type: "button", class: "ref-link", "data-finding": m.n, "aria-label": `finding ${m.n}`, text: `[${m.n}]` }));
document.addEventListener("click", (e) => {
  const b = e.target.closest("button[data-finding]");
  if (!b) return;
  const target = document.getElementById(`f${b.dataset.finding}`);
  if (!target) return;
  const fold = target.closest("details");
  if (fold) fold.open = true;
  target.scrollIntoView({ behavior: "smooth", block: "center" });
  target.classList.remove("flash"); void target.offsetWidth; target.classList.add("flash");
});
const valueText = (v, d = 10) => `${v.lim ? (v.lim > 0 ? "< " : "> ") : ""}${num(v.v, d)}`;
const signed = (x) => (x == null ? "?" : x >= 0 ? `+${num(x, 12)}` : num(x, 12));
const errSpan = (v) => (v.e1 != null || v.e2 != null ? el("span", { class: "err", text: `${signed(v.e1)} / ${v.e2 == null ? "?" : num(v.e2, 12)}` }) : null);

function evidenceCharts(planet, plan) {
  const def = planet.papers.find((p) => p.default) || { values: {} };
  const out = [];
  for (const [field, label, unit0] of FIELDS) {
    const vals = planet.papers.map((p, i) => [p, i]).filter(([p]) => p.values[field]);
    const c = planet.public[field], d = (planet.eu || {})[field], g = field === "distance" ? planet.gaia : null;
    const jup = field === "mass" && bigMass(planet);
    const unit = jup ? "Jupiters" : unit0;
    const conv = (v) => (v == null ? null : jup ? v / JUP_M : v);
    const rng = (v) => {
      const src = jup && v.j ? v.j : v;
      const k = jup && !v.j ? 1 / JUP_M : 1;
      return { v: src.v * k, lo: src.e2 != null ? (src.v + src.e2) * k : null, hi: src.e1 != null ? (src.v + src.e1) * k : null, lim: v.lim };
    };
    const rows = [];
    for (const [p, i] of vals) {
      const r = rng(p.values[field]);
      const same = rows.find((x) => x.kind === "paper" && x.r.v === r.v && x.r.lo === r.lo && x.r.hi === r.hi);
      const marks = plan.papers.get(`${i}|${field}`) || [];
      if (same && !marks.length && !same.marks.length) { same.refs.push(p); continue; }
      rows.push({ kind: "paper", refs: [p], r, marks: [...marks, ...(p.default ? plan.agree.get(`${field}|nasa`) || [] : [])] });
    }
    rows.sort((a, b) => b.refs.some((p) => p.default) - a.refs.some((p) => p.default));
    if (c && c.display) {
      const m = /^\s*([<>])?\s*([0-9.]+)\s*(Earths?|Jupiters?)?\s*$/i.exec(c.display);
      if (m) {
        let v = Number(m[2]);
        const shownUnit = m[3] || "";
        if (field === "mass") v = /^j/i.test(shownUnit) ? (jup ? v : v * JUP_M) : (jup ? v / JUP_M : v);
        const said = c.bucket === "C-default" ? "same as the default paper" : c.bucket === "C-composite" ? `${c.matched}, via NASA's combined table`
          : c.bucket === "C-other" ? `an older paper: ${c.matched}` : "matches no NASA paper";
        rows.push({ kind: "catalog", field, r: { v, lim: m[1] === "<" ? 1 : m[1] === ">" ? -1 : 0 }, note: field === "distance" ? `${said}; not shown on the page` : said, marks: plan.agree.get(`${field}|catalog`) || [] });
      }
    }
    if (d && d.v != null) rows.push({ kind: "eu", r: { v: conv(d.v), lo: d.em != null ? conv(d.v - Math.abs(d.em)) : null, hi: d.ep != null ? conv(d.v + Math.abs(d.ep)) : null }, marks: plan.agree.get(`${field}|eu`) || [] });
    if (g) rows.push({ kind: "gaia", r: { v: g.v, lo: g.lo, hi: g.hi }, marks: [] });
    if (rows.length < 2) continue;
    const band = def.values[field] ? rng(def.values[field]) : null;
    out.push(quantityChart(label, unit, rows, band));
  }
  return el("div", { class: "evidence" }, ...out,
    el("p", { class: "muted ev-legend" }, el("span", { class: "sw nasa" }), " NASA's own sources: each paper (filled = the one NASA shows by default), ",
      el("span", { class: "tri" }, "▲"), " the catalog page. ", el("span", { class: "sw other" }), " outside sources: exoplanet.eu, Gaia DR3. ",
      "Bars are the ranges each source gives; the shaded band is the default paper's range. ",
      el("span", { class: "flag-word", text: "Red, with a ring" }), ": a finding [n]; grey [n]: a note."));
}

function quantityChart(label, unit, rows, band) {
  const NS = "http://www.w3.org/2000/svg";
  const s = (tag, attrs, text) => { const n = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v); if (text != null) n.textContent = text; return n; };
  const box = (document.getElementById("planet") || {}).clientWidth || 760;
  const W = Math.max(320, Math.min(760, box - 20)), narrow = W < 540;
  const L = narrow ? 128 : 230, rowH = 24, top = 8, H = top + rows.length * rowH + 26;
  const measuredRows = rows.filter((x) => !x.r.lim);
  const xs = (measuredRows.length ? measuredRows : rows).flatMap((x) => [x.r.v, x.r.lo, x.r.hi]).concat(band ? [band.lo, band.hi] : []).filter((x) => x != null && Number.isFinite(x));
  let lo = Math.min(...xs), hi = Math.max(...xs);
  const ranged = measuredRows.some((r) => r.r.lo != null && r.r.hi != null);
  if (!ranged) { const mid = (lo + hi) / 2, half = Math.max((hi - lo) / 2, Math.abs(mid) * 0.1) || 0.05; lo = mid - half; hi = mid + half; }
  const floor = Math.min(...xs) >= 0 ? 0 : -Infinity;
  lo = Math.max(lo, floor);
  const pad = (hi - lo || Math.abs(hi) * 0.05 || 1) * 0.1; lo = Math.max(lo - pad, floor); hi += pad;
  const { fmtTick, fmtVal } = axisFormat(lo, hi);
  const valueText = (r) => (r.r.lim ? `${r.r.lim > 0 ? "< " : "> "}${fmtVal(r.r.v)}`
    : `${fmtVal(r.r.v)}${r.marks.length ? ` [${[...new Set(r.marks.map((m) => m.n))].join("][")}]` : ""}`);
  const R = Math.max(narrow ? 70 : 120, 14 + 7.3 * Math.max(...rows.map((r) => valueText(r).length)));
  const x = (v) => L + ((v - lo) / (hi - lo)) * (W - L - R);
  const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, class: "ev-chart", role: "img", "aria-label": `${label}: ` + rows.map((r) => `${rowName(r)} ${num(r.r.v, 5)}`).join("; ") });
  if (band && band.lo != null && band.hi != null) svg.append(s("rect", { x: x(band.lo), y: top - 2, width: Math.max(1, x(band.hi) - x(band.lo)), height: rows.length * rowH, class: "ev-band" }));
  rows.forEach((r, i) => {
    const y = top + i * rowH + rowH / 2;
    const name = rowName(r), max = narrow ? 18 : 34;
    if (r.kind === "paper") {
      const isDef = r.refs.some((p) => p.default);
      svg.append(s("rect", { x: 0, y: y - rowH / 2 + 1, width: L - 10, height: rowH - 2, class: `ev-paper${isDef ? " default" : ""}` }));
      if (isDef) svg.append(s("rect", { x: 0, y: y - rowH / 2 + 1, width: 3, height: rowH - 2, class: "ev-paper-bar" }));
    }
    svg.append(s("text", { x: r.kind === "paper" ? 8 : 0, y: y + 4, class: `ev-label${r.marks.some((m) => !m.soft) ? " flag" : ""}` }, name.length > max ? name.slice(0, max - 1) + "…" : name));
    const fam = r.kind === "eu" || r.kind === "gaia" ? "other" : "nasa";
    const gEl = s("g", { class: `ev-${fam}` });
    gEl.append(s("title", {}, `${name}: ${num(r.r.v, 6)} ${unit || ""}${r.r.lo != null && r.r.hi != null ? ` (range ${num(r.r.lo, 4)} to ${num(r.r.hi, 4)})` : " (no range given)"}${r.note ? ` · ${r.note}` : ""}`));
    gEl.append(s("line", { x1: L, x2: W - R, y1: y, y2: y, class: "ev-guide" }));
    if (r.r.lo != null && r.r.hi != null) gEl.append(s("rect", { x: x(r.r.lo), y: y - 2.5, width: Math.max(2, x(r.r.hi) - x(r.r.lo)), height: 5, rx: 2.5, class: "ev-bar" }));
    const cx = Math.min(Math.max(x(r.r.v), L), W - R);
    if (r.r.lim) {
      gEl.append(s("line", { x1: r.r.lim > 0 ? x(lo) : cx, x2: r.r.lim > 0 ? cx : x(hi), y1: y, y2: y, class: "ev-limit" }));
      gEl.append(s("text", { x: cx + (r.r.lim > 0 ? 4 : -12), y: y + 4, class: "ev-limit-mark" }, r.r.lim > 0 ? "<" : ">"));
      svg.append(gEl);
      svg.append(s("text", { x: W - R + 10, y: y + 4, class: "ev-value" }, valueText(r)));
      return;
    }
    if (r.kind === "catalog") gEl.append(s("path", { d: `M${cx},${y - 6} L${cx + 6},${y + 5} L${cx - 6},${y + 5} Z`, class: "ev-mark solid" }));
    else if (fam === "other") gEl.append(s("path", { d: `M${cx},${y - 6} L${cx + 6},${y} L${cx},${y + 6} L${cx - 6},${y} Z`, class: "ev-mark solid" }));
    else gEl.append(s("circle", { cx, cy: y, r: 5, class: `ev-mark ${r.refs.some((p) => p.default) ? "solid" : "hollow"}` }));
    if (r.marks.some((m) => !m.soft)) gEl.append(s("circle", { cx, cy: y, r: 9.5, class: "ev-flag-ring" }));
    svg.append(gEl);
    svg.append(s("text", { x: W - R + 10, y: y + 4, class: `ev-value${r.marks.some((m) => !m.soft) ? " flag" : ""}` }, valueText(r)));
  });
  const ay = top + rows.length * rowH + 4;
  svg.append(s("line", { x1: L, x2: W - R, y1: ay, y2: ay, class: "ev-axis" }));
  for (let k = 0; k <= 3; k++) { const t = lo + (k / 3) * (hi - lo); svg.append(s("text", { x: x(t), y: ay + 14, class: "ev-tick", "text-anchor": "middle" }, fmtTick(t))); }
  return el("figure", { class: "ev" }, el("figcaption", {}, el("strong", { class: "field", text: label }), unit ? el("span", { class: "unit-name", text: ` ${unit}` }) : null,
    ranged ? null : el("span", { class: "no-range", text: "no ranges given" })), svg);
}
function rowName(r) {
  if (r.kind === "catalog") return r.field === "distance" ? "NASA catalog data" : "NASA catalog page";
  if (r.kind === "eu") return "exoplanet.eu";
  if (r.kind === "gaia") return "Gaia DR3";
  const first = r.refs.find((p) => p.default) || r.refs[0];
  return `${first.ref}${first.default ? " ★" : ""}${r.refs.length > 1 ? ` +${r.refs.length - 1}` : ""}`;
}

function papersTable(planet, plan) {
  const used = (f) => planet.papers.some((p, i) => p.values[f] || plan.papers.has(`${i}|${f}`));
  const jup = bigMass(planet);
  const cols = [...FIELDS.filter(([f]) => used(f)).map(([f, l, u]) => (f === "mass" && jup ? [f, l, "Jupiters"] : [f, l, u])),
    ...EXTRA_COLS.filter(([f]) => plan.extra.has(f))];
  const head = el("tr", {}, el("th", { text: "paper" }), ...cols.map(([, label, unit]) =>
    el("th", {}, el("strong", { class: "field", text: label }), unit ? el("span", { class: "unit-name", text: ` ${unit}` }) : null)));
  const shown = (field) => { const c = planet.public[field]; return c && ["C-default", "C-composite", "C-other"].includes(c.bucket) ? c.matched : null; };
  const rows = planet.papers.map((paper, i) => {
    const nameMarks = plan.papers.get(`${i}|paper`);
    return el("tr", { class: paper.default ? "default" : null },
      el("td", { class: "paper" }, link(paper.ref || "unnamed", paper.url), paper.default ? el("span", { class: "star", text: " ★" }) : null, paper.date ? el("span", { class: "err", text: paper.date }) : null,
        paper.copies ? el("span", { class: "err", text: `×${paper.copies} identical rows in NASA's archive` }) : null,
        ...(nameMarks || []).map(markLink)),
      ...cols.map(([field]) => {
        const v0 = paper.values[field];
        const marks = plan.papers.get(`${i}|${field}`);
        if (!v0) return marks ? markedCell(["–"], marks) : el("td", {});
        const v = field === "mass" && jup
          ? (v0.j ? { ...v0.j, lim: v0.lim } : { v: v0.v / JUP_M, e1: v0.e1 != null ? v0.e1 / JUP_M : null, e2: v0.e2 != null ? v0.e2 / JUP_M : null, lim: v0.lim })
          : v0;
        const kind = field === "mass" && v0.kind && v0.kind !== "Mass" ? ` (${v0.kind})` : "";
        const td = markedCell([el("span", { class: "val", text: valueText(v, 12) + kind })], marks, [errSpan(v)]);
        if (shown(field) && shown(field) === paper.ref && (paper.default || planet.public[field].bucket !== "C-default")) {
          td.classList.add("shown"); td.title = "NASA catalog data (behind its page) uses this value";
        }
        return td;
      }));
  });
  return el("div", { class: "table-wrap" }, el("table", { class: "values nasa-papers" }, el("thead", {}, head), el("tbody", {}, ...rows)));
}

function howChecks(plan) {
  const card = (title, key, src) => {
    const w = W(key);
    return w ? el("div", { class: "how-check" }, el("h3", { text: title }), lineP("what we compare", w.compare), el("p", { text: w.means }),
      w.details ? el("p", { class: "muted", text: w.details }) : null, sources(src)) : null;
  };
  const parts = [];
  for (const k of plan.kinds) {
    if (CARDS[k] && B_CELLS[k]) parts.push(card(CARDS[k].title, `card/${k}`, CARDS[k].src));
    else if (k === "C") parts.push(card("NASA Exoplanet Catalog", "card/public"));
    else if (k === "D") parts.push(card("exoplanet.eu", "card/eu", CARDS.eu.src));
    else if (k === "E") parts.push(card("Gaia DR3 distance", "card/gaia", CARDS.gaia.src));
    else if (k === "F") parts.push(card("NASA catalog page text", "F"));
    else if (k === "massKind") parts.push(card("kind of mass", "card/massKind", CARDS.massKind.src));
    else if (k.startsWith("A:")) parts.push(card(LABEL(`A/${k.slice(2)}`), `A/${k.slice(2)}`, k.startsWith("A:A5") ? CARDS.A5.src : null));
  }
  for (const [w, l] of plan.whys.values())
    parts.push(el("div", { class: "how-check" }, el("h3", { text: `pattern: ${w.title.toLowerCase()}` }), el("p", { text: whyText(w, l) })));
  return parts.filter(Boolean).length ? el("details", { class: "fold" }, el("summary", { text: "how these checks work" }), ...parts.filter(Boolean)) : null;
}

function cleanText(name) {
  const entry = state.index.find((p) => p.n === name) || {};
  const ran = ["values possible", entry.rc ? "row adds up" : null, entry.pc ? "NASA Exoplanet Catalog" : null,
    (state.meta.check_d || {}).by_bucket ? "exoplanet.eu" : null].filter(Boolean);
  const not = [entry.rc ? null : "row adds up (no row had all the numbers it needs)", entry.pc ? null : "NASA Exoplanet Catalog (no page)"].filter(Boolean);
  return `No findings from: ${ran.join(", ")}.${not.length ? ` Not checked: ${not.join("; ")}.` : ""}`;
}

function facts(planet) {
  const d = planet.discovery;
  const row = (k, ...v) => el("div", {}, el("dt", { text: k }), el("dd", {}, ...v));
  return el("dl", { class: "facts" },
    d.method ? row("how it was found", d.method) : null,
    d.year ? row("when", String(d.year)) : null,
    d.ref || d.facility ? row("by", ...(d.ref ? [link(d.ref, d.url)] : []), d.facility ? el("span", { class: "muted", text: `${d.ref ? " · " : ""}${d.facility}` }) : null) : null);
}

const pairOf = (l) => l.pair || [null, null];

async function renderPlanet(name) {
  const box = document.getElementById("planet");
  box.replaceChildren(el("p", { class: "muted", text: "Loading…" }));
  let planet;
  try { planet = await loadPlanet(name); } catch (err) {
    box.replaceChildren(el("p", { class: "prose", text: `The planet data could not be loaded: ${err.message}.` }));
    return;
  }
  if (!planet) {
    box.replaceChildren(el("a", { class: "back", href: "#/", text: "planets" }),
      el("p", { class: "prose", text: `No confirmed planet called “${name}” in this snapshot.` }));
    return;
  }
  document.title = `${planet.name} - ExoDiff`;
  const plan = planFindings(planet);
  box.replaceChildren(...[
    el("a", { class: "back", href: "#/", text: "planets" }),
    el("div", { class: "planet-head" },
      el("h1", { class: "page-title", text: planet.name }),
      el("p", { class: "meta", text: planet.host ? `orbits ${planet.host}` : "" }),
      el("p", { class: "links" }, planet.links.public ? link("NASA Exoplanet Catalog", planet.links.public) : null,
        link("NASA Exoplanet Archive", planet.links.archive),
        planet.links.eu ? link("exoplanet.eu", planet.links.eu) : null)),
    facts(planet),
    findingsSection(planet, plan, name),
    el("h2", { class: "section-title", text: "do the sources agree?" }),
    evidenceCharts(planet, plan),
    el("p", { class: "asof", text: `NASA Exoplanet Catalog as of ${publicDate()}, exoplanet.eu as of ${euDate()}.` }),
    el("h2", { class: "section-title", text: `papers in the NASA archive (${planet.papers.length})` }),
    papersTable(planet, plan),
    el("p", { class: "muted" }, "Every row is a paper NASA's archive lists; ★ is the one its NASA archive column shows."),
    el("p", { class: "asof" }, "Underlined: the value NASA's catalog data uses. [n]: red, a finding; grey, a note. ",
      W("general/precision") ? W("general/precision").means + " " : "", "Also on ",
      link("NASA's overview page", planet.links.archive), "."),
    howChecks(plan),
  ].filter(Boolean));
  window.scrollTo(0, 0);
}

const rich = (text) => String(text || "").split("**").map((part, i) => (i % 2 ? el("strong", { class: "key", text: part }) : document.createTextNode(part)));
const paras = (text) => String(text || "").split(/\n\n+/).map((t) => el("p", { class: "prose" }, ...rich(t)));
const marked = (key) => (state.wording.texts[key] || {}).means || "";

function renderAbout() {
  document.getElementById("about-intro").replaceChildren(...paras(marked("about/intro")));
}

function resultsSection() {
  const m = state.meta, n = (x) => (x ?? 0).toLocaleString();
  const c = m.check_c || {}, d = m.check_d || {}, e = m.check_e || {};
  const flaggedPlanets = (key) => state.index.filter((p) => p[key] > 0).length;
  const byCheck = ((state.updates || [])[0] || {}).by_check || {};
  const rows = [
    [CHECK_NAME.A, byCheck.A, flaggedPlanets("a"), `every value in ${n(m.snapshot_rows)} rows`],
    [CHECK_NAME.B, byCheck.B, flaggedPlanets("b"), `${n(m.row_checks_run)} row checks`],
    [CHECK_NAME.C, c.compared ? byCheck.C : null, flaggedPlanets("c"), c.compared ? `${n(c.compared)} values` : "not run in the latest update"],
    [CHECK_NAME.D, d.compared ? byCheck.D : null, flaggedPlanets("x"), d.compared ? `${n(d.compared)} values on ${n(d.join.matched)} planets` : "not run in the latest update"],
    [CHECK_NAME.E, e.compared ? byCheck.E : null, flaggedPlanets("e"), e.compared ? `distances of ${n(e.compared)} stars (${n(e.by_bucket["E-differs"])} stars differ)` : "not run in the latest update"],
  ];
  return [el("h2", { class: "section-title", text: "latest results" }),
    el("table", { class: "data" }, el("thead", {}, el("tr", {}, ...["check", "findings", "planets", "checked"].map((h) => el("th", { text: h })))),
      el("tbody", {}, ...rows.map(([q, l, p, of]) => el("tr", {}, el("td", { text: q }), el("td", { class: "num", text: l == null ? "–" : n(l) }),
        el("td", { class: "num", text: n(p) }), el("td", { text: of }))))),
    el("p", { class: "muted", text: "These are findings under ExoDiff's stated rules, not counts of confirmed scientific errors." })];
}

function renderMethodology() {
  const m = state.meta;
  document.getElementById("how-intro").replaceChildren(...paras(marked("method/intro")));
  document.getElementById("how-lead").replaceChildren(...paras(marked("about/lead")));
  document.getElementById("how-uncertainty").replaceChildren(...["general/uncertainty", "general/no-uncertainty", "general/precision"].flatMap((k) => paras(marked(k))));
  document.getElementById("how-statistic").replaceChildren(el("p", { class: "prose", text: state.wording.statistic || "" }));
  const check = (question, key) => { const w = state.wording.texts[key] || {};
    return el("div", { class: "method-check" }, el("h3", { class: "question", text: question }), el("p", { class: "prose" }, ...rich(w.compare)), ...paras(w.means)); };
  document.getElementById("how-steps").replaceChildren(check("Are the values possible?", "card/values"), check("Does each row add up?", "card/rows"),
    check("Does the NASA Exoplanet Catalog match the archive?", "card/public"), check("Does the NASA catalog page agree with itself?", "F"),
    check("Does exoplanet.eu agree?", "card/eu"), check("Does Gaia DR3 agree?", "card/gaia"));
  const ev = m.detector_evaluation || {}, radius = ev.row_check || {}, ids = ev.identities || {}, copies = ev.unit_copies || {};
  const share = (r, key = "finding_rate") => (r && r[key] != null ? `${Math.round(r[key] * 100)}%` : "–");
  const rows = [["a planet's size", ...["2%", "5%", "10%", "25%"].map((k) => share(radius[`planet radius off by ${k}`]))],
    ...[["kepler", "a planet's orbit size"], ["a_over_rstar", "distance to the star, in star sizes"], ["density", "a planet's density"]]
      .filter(([k]) => ids[k]).map(([k, label]) => [label, "–", ...["listed value off by 5%", "off by 10%", "off by 25%"].map((x) => share(ids[k][x]))]),
    ...[["pl_rade", "a size kept in both Earths and Jupiters, one copy changed"], ["pl_bmasse", "a mass kept in both units, one copy changed"]]
      .filter(([k]) => copies[k]).map(([k, label]) => [label, share(copies[k]["copy off by 2%"], "rate"), share(copies[k]["copy off by 5%"], "rate"), "–", "–"])];
  const look = copies.pl_rade && copies.pl_rade["copy off by 2%"], tenths = look ? Math.round((10 * look.labelled_innocent) / look.planted) : 0;
  document.getElementById("how-eval").replaceChildren(
    el("p", { class: "prose", text: "To test the checks, every build takes real archive rows, changes one value by a known amount, and counts how often the change is big enough to be a finding (more than 2 error bars)." }),
    el("table", { class: "data" }, el("thead", {}, el("tr", {}, ...["value changed", "by 2%", "by 5%", "by 10%", "by 25%"].map((h) => el("th", { text: h })))),
      el("tbody", {}, ...rows.map((r) => el("tr", {}, ...r.map((v, i) => el("td", { class: i ? "num" : null, text: v })))))),
    el("p", { class: "muted", text: `Small changes often stay inside a value's own uncertainty range, so they aren't caught. Density is hardest: it depends on size cubed.${tenths ? ` About ${tenths} in 10 size copies changed by 2% look like the known difference between Jupiter's average and equatorial size, and are labelled as that.` : ""}` }),
    el("p", { class: "muted", text: "Some of these may still be shown as notes when they match a known explanation. The test shows what the checks catch when an error is planted; it doesn't prove that every real error is caught." }));
  document.getElementById("how-cards").replaceChildren(...["radius", "density", "kepler", "a_over_rstar"].map((k) => {
    const cc = CARDS[k], w = W(`card/${k}`) || {};
    return el("div", { class: "case" }, el("div", { class: "case-head" }, el("h3", { text: cc.title.split(":")[0] })),
      lineP("what we compare", w.compare), el("p", { text: w.means }), el("pre", { text: cc.maths }), el("p", { class: "muted", text: w.details }), sources(cc.src));
  }));
  document.getElementById("how-units").replaceChildren(el("table", { class: "data" },
    el("tbody", {}, ...[
      ["Earths (size)", "Earth's equatorial radius, 6,378.1 km. Jupiter is 11.209 Earths wide.", "iau15"],
      ["Earths (mass)", "Earth's mass. Jupiter is 317.83 Earths heavy.", "iau15"],
      ["Suns", "the Sun's radius, 695,700 km, or its mass", "iau15"],
      ["au", "149,597,870.7 km, about the Earth–Sun distance", "iau12"],
      ["parsecs", "648,000/π au, about 3.26 light-years", "parsec"],
      ["orbit stretch", "eccentricity: 0 is a circle, values close to 1 a long, thin ellipse", "cols"],
      ["uncertainty (±)", "the range the paper gives for a value", null],
    ].map(([u, d, k]) => el("tr", {}, el("td", { text: u }), el("td", { text: d }), el("td", {}, k ? link(SRC[k][0], SRC[k][1]) : ""))))));
}

const fmtDate = (d) => (d ? new Date(`${d}T00:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }) : "");
const signedN = (n) => (n > 0 ? `+${n.toLocaleString()}` : n < 0 ? `−${(-n).toLocaleString()}` : "0");
const plural = (n, word) => `${n.toLocaleString()} ${word}${n === 1 ? "" : "s"}`;
const planetLink = (n) => (state.index.some((p) => p.n === n) ? el("a", { href: planetHref(n), text: n }) : el("span", { text: n }));
const changeLabel = (x) => {
  const field = x.kind === "A" || x.kind === "E" || x.rule === "letters" ? null : NOUN[x.rule] || (WHAT[x.rule] || [])[0] || x.rule;
  return [x.key ? LABEL(x.key) : CHECK_NAME[x.kind] || x.kind, field, x.ref].filter(Boolean).join(" · ");
};
const CAUSE = { "first run": "first update tracked", "new data": "new data from the sources", "rule change": "a change in ExoDiff's rules, not in the data",
  "new data and a rule change": "new data from the sources and a change in ExoDiff's rules", "same data re-checked": "the same data checked again" };
const arr = (x) => (Array.isArray(x) ? x : []);
const counted = (e, k) => (Array.isArray(e[k]) ? e[k].length : null);
const noteKinds = (checks) => { const parts = Object.entries(checks && typeof checks === "object" ? checks : {})
  .filter(([, v]) => Array.isArray(v)).map(([k, [a, b]]) => `${CHECK_NAME[k] || k} ${a} → ${b}`); return parts.length ? ` (${parts.join(", ")})` : ""; };

const RUN_STATUS = { fresh: "new data", unchanged: "no change", copy: "unreachable: saved copy used", missing: "unreachable: not checked",
  skipped: "skipped: its input isn't available this run", partial: "partly read: some pages failed and are retried next run", failed: "the check failed: findings kept from the last run" };
function sourceStatus() {
  const sources = ((state.meta.run || {}).sources) || {};
  return Object.entries(sources).map(([name, r]) => ({ name, status: r.status, text: RUN_STATUS[r.status] || r.status,
    date: (r.copy_from || "").slice(0, 10), checked: (r.checked_utc || "").slice(0, 10) }));
}

function sourceNote() {
  const down = (x) => ["copy", "missing", "partial", "failed"].includes(x.status);
  const all = sourceStatus(), siteDown = new Set(all.filter(down).map((x) => x.name));
  const notes = all.filter((x) => down(x) && !(x.name === "exoplanet.eu pages" && siteDown.has("exoplanet.eu")))
    .map((x) => (x.status === "copy" && x.date ? `${x.name}: unreachable, copy from ${fmtDate(x.date)}` : `${x.name}: ${RUN_STATUS[x.status]}`));
  const box = document.getElementById("source-note");
  box.hidden = !notes.length;
  box.textContent = notes.join(" · ");
}

function updateChart(updates, series, { W, H = 150, axis = true, label = "", line = false, partial = (e) => arr(e.not_checked).some((c) => "ABCDE".includes(c)) }) {
  const NS = "http://www.w3.org/2000/svg";
  const s = (tag, attrs, text) => { const n = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v); if (text != null) n.textContent = text; return n; };
  const order = updates.map((e, i) => ({ e, i })).reverse();
  const vals = order.filter(({ e }) => !(line && partial(e))).flatMap(({ e }) => series.map((x) => x.value(e)).filter((v) => v != null));
  if (!vals.length) vals.push(0);
  let hi = Math.max(1, ...vals), lo = Math.min(0, ...vals);
  if (line) { const pad = Math.max(1, (Math.max(...vals) - Math.min(...vals)) * 0.15); hi = Math.max(...vals) + pad; lo = Math.max(0, Math.min(...vals) - pad); }
  const L = axis ? 44 : 0, R = axis ? 8 : 0, T = axis ? 10 : 2, B = axis ? 22 : 2;
  const y = (v) => T + ((hi - v) / (hi - lo)) * (H - T - B);
  const step = (W - L - R) / Math.max(1, order.length), bw = Math.min(26, Math.max(2, step * 0.7));
  const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, class: "col-chart", role: "img", "aria-label": label });
  order.forEach(({ e, i }, k) => {
    const g = s("g", { class: "col", "data-update": i }), cx = L + step * (k + 0.5);
    const parts = series.map((x) => [x, x.value(e)]).filter(([, v]) => v != null);
    const skipped = partial(e) ? arr(e.not_checked).map((c) => CHECK_NAME[c] || c) : [];
    const top = T, bottom = H - B;
    g.append(s("title", {}, `${fmtDate(e.date)} (${CAUSE[e.cause] || e.cause}): ${parts.map(([x, v]) => `${Math.abs(v).toLocaleString()} ${x.name}`).join(", ")}${skipped.length ? ` (not checked: ${skipped.join(", ")})` : ""}`));
    g.append(s("rect", { x: L + step * k, y: 0, width: step, height: H, class: "col-hit" }));
    for (const [x, v] of parts) {
      if (line) g.append(s("circle", { cx, cy: Math.min(bottom, Math.max(top, y(v))), r: axis ? 3.5 : 2, class: `${x.cls}${skipped.length ? " hollow" : ""}` }));
      else if (v) g.append(s("rect", { x: cx - bw / 2, y: y(Math.max(v, 0)), width: bw, height: Math.max(1, Math.abs(y(v) - y(0))), class: x.cls }));
    }
    svg.append(g);
  });
  if (line) for (const x of series) {
    let run = [];
    const flush = () => { if (run.length > 1) svg.prepend(s("polyline", { points: run.join(" "), class: `col-line ${x.cls}` })); run = []; };
    order.forEach(({ e }, k) => { const v = x.value(e); if (v == null || partial(e)) flush(); else run.push(`${L + step * (k + 0.5)},${y(v)}`); });
    flush();
  }
  if (axis) {
    svg.append(s("line", { x1: L, x2: W - R, y1: y(line ? lo : 0), y2: y(line ? lo : 0), class: "col-axis" }));
    const ticks = line ? [Math.round(hi), Math.round(lo)] : lo < 0 ? [hi, 0, lo] : [hi, 0];
    for (const t of ticks) svg.append(s("text", { x: L - 6, y: y(t) + 4, "text-anchor": "end", class: "col-tick" }, signedN(t).replace("+", !line && lo < 0 ? "+" : "")));
    const first = order[0].e, last = order[order.length - 1].e;
    svg.append(s("text", { x: L, y: H - 6, class: "col-tick" }, fmtDate(first.date)));
    if (order.length > 1) svg.append(s("text", { x: W - R, y: H - 6, "text-anchor": "end", class: "col-tick" }, fmtDate(last.date)));
  }
  svg.addEventListener("click", (ev) => {
    const g = ev.target.closest("g.col");
    const d = g && document.getElementById(`update-${g.dataset.update}`);
    if (d) { d.open = true; d.scrollIntoView({ block: "start" }); }
  });
  return svg;
}

function renderChangesLine() {
  const u = state.updates || [], now = u[0], before = u[1], line = document.getElementById("changes-line");
  if (!now) { line.replaceChildren(); return; }
  const nf = counted(now, "new_findings") || 0, rf = counted(now, "resolved_findings") || 0;
  line.replaceChildren(before ? `Latest update, ${fmtDate(now.date)}: ${plural(nf, "new finding")}, ${rf.toLocaleString()} resolved. ` : `Changes are tracked from ${fmtDate(now.date)}. `,
    el("a", { href: "#/changes", text: "see changes" }));
}

function renderChanges() {
  const box = document.getElementById("changes"), u = state.updates || [], now = u[0], before = u[1];
  const out = [el("h1", { class: "page-title", text: "Changes" }),
    el("p", { class: "prose", text: "Each daily update that changed something is recorded here: findings new and resolved, planets added or removed, and notes that changed." })];
  if (!now) { box.replaceChildren(...out, el("p", { class: "prose", text: "No update has been recorded yet." })); return; }
  const pad = getComputedStyle(box), W = Math.max(280, Math.min(900, (box.clientWidth - parseFloat(pad.paddingLeft) - parseFloat(pad.paddingRight)) || 760));
  const arrow = (k, word) => `${word} ${now[k].toLocaleString()}${before ? ` (${signedN(now[k] - before[k])})` : ""}`;
  const counts = [arrow("findings", "findings"), arrow("planets_with_findings", "planets with findings"), arrow("notes", "notes")].join("; ");
  out.push(el("h2", { class: "section-title", text: "latest update" }),
    el("p", { class: "prose", text: `${fmtDate(now.date)}: ${CAUSE[now.cause] || now.cause}. ${before ? `Compared with ${fmtDate(before.date)}: ${counts}` : counts[0].toUpperCase() + counts.slice(1)}.` }));
  if (arr(now.not_checked).length) out.push(el("p", { class: "prose", text: `Not checked in this update: ${arr(now.not_checked).map((k) => CHECK_NAME[k] || k).join(", ")}. Its findings aren't shown until it is checked again, and aren't counted as resolved.` }));
  if (arr(now.checked_again).length) out.push(el("p", { class: "prose", text: `Checked again in this update after being unreachable: ${arr(now.checked_again).map((k) => CHECK_NAME[k] || k).join(", ")}. Its findings return without counting as new.` }));
  const status = sourceStatus();
  if (status.length) out.push(el("p", { class: "muted", text: `Sources in the latest run (${fmtDate(status[0].checked)}):` }),
    el("table", { class: "data" }, el("thead", {}, el("tr", {}, ...["source", "this run", "data from"].map((h) => el("th", { text: h })))),
      el("tbody", {}, ...status.map((x) => el("tr", {}, el("td", { text: x.name }),
        el("td", { class: ["copy", "missing", "partial", "failed"].includes(x.status) ? "flag-word" : "muted", text: x.text }),
        el("td", { text: x.date ? fmtDate(x.date) : "–" }))))));
  out.push(...resultsSection());

  out.push(el("h2", { class: "section-title", text: "findings over time" }),
    updateChart(u, [{ name: "findings", cls: "col-up", value: (e) => e.findings }], { W, line: true, label: "Findings after each update" }),
    el("p", { class: "muted", text: "Findings shown on the site after each update, one dot per update (updates aren't evenly spaced in time). A hollow dot on the axis marks an update where a check couldn't run, so its total isn't comparable. Click a dot to see that update's changes; each small chart below has its own scale." }));
  out.push(el("div", { class: "mini-charts" }, ...["A", "B", "C", "D", "E"].map((c) => el("figure", {},
    el("figcaption", {}, el("span", { text: CHECK_NAME[c] }), el("span", { text: ((now.by_check || {})[c] ?? 0).toLocaleString() })),
    updateChart(u, [{ name: "findings", cls: "col-up", value: (e) => (e.by_check || {})[c] ?? 0 }], { W: 300, H: 44, axis: false, line: true, partial: (e) => arr(e.not_checked).includes(c), label: `${CHECK_NAME[c]} findings after each update` })))));
  if (before) {
    out.push(el("h2", { class: "section-title", text: "new and resolved findings" }),
      updateChart(u, [{ name: "new", cls: "col-up", value: (e) => counted(e, "new_findings") },
        { name: "resolved", cls: "col-down", value: (e) => (counted(e, "resolved_findings") == null ? null : -counted(e, "resolved_findings")) }], { W, label: "New and resolved findings per update" }),
      el("p", { class: "muted ev-legend" }, el("span", { class: "sw nasa" }), " new findings, above the line  ", el("span", { class: "sw other" }), " resolved, below it"));
  }

  const list = (title, items, render) => (arr(items).length ? el("details", { class: "fold", open: items.length <= 15 ? "" : null },
    el("summary", { text: `${title} (${items.length})` }), el("ul", { class: "soft-list" }, ...items.map((x) => el("li", {}, ...render(x))))) : null);
  const finding = (x) => [planetLink(x.planet), el("span", { class: "muted", text: ` ${changeLabel(x)}` })];
  out.push(el("h2", { class: "section-title", text: "every update" }), ...u.map((e, i) => {
    const nf = counted(e, "new_findings"), rf = counted(e, "resolved_findings"), nc = counted(e, "notes_changed");
    const what = e.cause === "first run" ? `${plural(e.findings, "finding")} on ${plural(e.planets_with_findings, "planet")}`
      : nf == null ? `${plural(e.findings, "finding")}; details kept for the latest 90 updates only`
      : `${nf.toLocaleString()} new, ${rf.toLocaleString()} resolved${nc ? `, notes changed on ${plural(nc, "planet")}` : ""}`;
    const parts = [
      list("new findings", e.new_findings, finding), list("findings resolved", e.resolved_findings, finding),
      list("planets added", e.new_planets, (x) => [planetLink(x)]), list("planets removed", e.removed_planets, (x) => [el("span", { text: x })]),
      list("notes changed", e.notes_changed, (x) => [planetLink(x.planet), el("span", { class: "muted", text: ` notes ${x.from} → ${x.to}${noteKinds(x.checks)}` })]),
    ].filter(Boolean);
    if (!parts.length) parts.push(el("p", { class: "muted", text: e.cause === "first run" ? "Changes are listed from the next update on." : nf == null ? "" : "Nothing changed on any planet." }));
    return el("details", { class: "fold update", id: `update-${i}`, open: i === 0 ? "" : null },
      el("summary", { text: `${fmtDate(e.date)} · ${CAUSE[e.cause] || e.cause} · ${what}${arr(e.not_checked).length ? ` · not checked: ${arr(e.not_checked).map((k) => CHECK_NAME[k] || k).join(", ")}` : ""}${arr(e.checked_again).length ? ` · checked again: ${arr(e.checked_again).map((k) => CHECK_NAME[k] || k).join(", ")}` : ""}` }),
      el("div", { class: "update-body" }, ...parts));
  }));
  box.replaceChildren(...out);
}

function route() {
  const hash = location.hash || "#/";
  const views = { list: "view-list", planet: "view-planet", changes: "view-changes", method: "view-method", about: "view-about" };
  let name = "list";
  if (hash.startsWith("#/planet/")) name = "planet";
  else if (hash === "#/changes") name = "changes";
  else if (hash === "#/methodology" || hash === "#/how") name = "method";
  else if (hash === "#/about") name = "about";
  for (const [k, id] of Object.entries(views)) document.getElementById(id).hidden = k !== name;
  document.querySelectorAll(".site-nav a").forEach((a) => {
    if (a.dataset.route === (name === "planet" ? "list" : name)) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
  const arg = (prefix) => { try { return decodeURIComponent(hash.slice(prefix.length)); } catch { return ""; } };
  if (name === "planet") renderPlanet(arg("#/planet/"));
  if (name === "changes") renderChanges();
  else document.title = "ExoDiff - 0rbitingZer0";
}

async function load() {
  const get = async (path) => {
    const res = await fetch(path, { cache: "no-cache" });
    if (!res.ok) throw new Error(`${path} returned ${res.status}`);
    return res.json();
  };
  try {
    [state.meta, state.index, state.why, state.wording, state.updates] = await Promise.all(
      ["data/meta.json", "data/planets.json", "data/explanations.json", "data/wording.json", "data/updates.json"].map(get));
  } catch (err) {
    document.getElementById("count").textContent = `The data could not be loaded (${err.message}). Run scripts/build_site.py, then serve the site folder.`;
    return;
  }
  const form = document.getElementById("filters");
  form.addEventListener("submit", (e) => e.preventDefault());
  form.addEventListener("input", (e) => { if (e.target.name === "scope") typeOptions(); state.page = 0; renderList(); });
  for (const id of ["pager-top", "pager"]) document.getElementById(id).addEventListener("click", (e) => {
    const b = e.target.closest("button[data-page]");
    if (!b) return;
    state.page = Number(b.dataset.page);
    renderList();
    document.getElementById("count").scrollIntoView({ block: "start" });
  });
  document.getElementById("export").addEventListener("click", exportCsv);
  renderHome();
  renderList();
  renderAbout();
  renderMethodology();
  renderChangesLine();
  sourceNote();
  window.addEventListener("hashchange", route);
  route();
}

load();
