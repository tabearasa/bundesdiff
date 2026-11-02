"use strict";

const UNKNOWN = "⟪frühere Fassung nicht ermittelbar⟫";
const CONTEXT = 1; // unchanged lines shown around changes when folding

// Plain-language labels for the processing status of a single change instruction
const STATUS = {
  applied: {
    label: "neuer Text berechnet",
    title: "Das Gesetz im Internet ist noch nicht aktualisiert. Den neuen Text hat bundesdiff aus der Änderung selbst erzeugt.",
  },
  consolidated: {
    label: "alter Text rekonstruiert",
    title: "Das Gesetz im Internet enthält die Änderung bereits. Den bisherigen Text hat bundesdiff zurückgerechnet.",
  },
  failed: {
    label: "nicht anwendbar",
    title: "Diese Änderung passte nicht zum aktuellen Gesetzestext und konnte nicht dargestellt werden.",
  },
  unsupported: {
    label: "nicht dargestellt",
    title: "Änderungen an Inhaltsverzeichnissen, Anlagen oder Tabellen werden nur im Wortlaut gezeigt.",
  },
};

const TYPE_HINT = {
  Gesetz: "vom Bundestag beschlossen",
  Verordnung: "von der Bundesregierung oder einem Ministerium erlassen",
  Sonstiges: "z. B. eine Bekanntmachung oder Berichtigung",
};

// Static build (GitHub Pages): precomputed JSON files instead of the live API
const STATIC = Boolean(window.BUNDESDIFF_STATIC);
const api = {
  list: (teil) => STATIC ? `data/publications-${teil}.json` : `/api/publications?teil=${teil}`,
  publication: (teil, year, number, refresh) => STATIC
    ? `data/${teil}/${year}/${encodeURIComponent(number)}.json`
    : `/api/publications/${teil}/${year}/${encodeURIComponent(number)}${refresh ? "?refresh=true" : ""}`,
};

const state = {
  teil: "1", // only Teil I (Gesetze und Verordnungen); Teil II = international treaties is not shown
  view: localGet("view") || "split",
  onlyChanges: localGet("onlyChanges") !== "0",
  pubs: [],
  current: null, // analysis result
  currentId: null,
};

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

function localGet(key) {
  try { return localStorage.getItem("bundesdiff." + key); } catch { return null; }
}
function localSet(key, value) {
  try { localStorage.setItem("bundesdiff." + key, value); } catch { /* ignore */ }
}

function esc(text) {
  return String(text ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function el(html) {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content.firstElementChild;
}

function tr(html) {
  const body = document.createElement("tbody");
  body.innerHTML = html.trim();
  return body.firstElementChild;
}

function formatDate(iso) {
  if (!iso) return "";
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  return m ? `${m[3]}.${m[2]}.${m[1]}` : iso;
}

function plural(n, one, many) {
  return `${n} ${n === 1 ? one : many}`;
}

async function getJSON(url) {
  const res = await fetch(url);
  if (!res.ok) {
    if (STATIC && res.status === 404) throw new Error("Für diese Veröffentlichung liegen (noch) keine Daten vor.");
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch { /* ignore */ }
    throw new Error(detail);
  }
  return res.json();
}

// ---------------------------------------------------------------- list

async function loadList() {
  const list = $("#pub-list");
  list.innerHTML = `<li class="empty">Lade Veröffentlichungen …</li>`;
  try {
    state.pubs = await getJSON(api.list(state.teil));
  } catch (e) {
    list.innerHTML = `<li class="empty">Liste konnte nicht geladen werden: ${esc(e.message)}</li>`;
    return;
  }
  const types = [...new Set(state.pubs.map((p) => p.typ).filter(Boolean))].sort();
  const select = $("#type-filter");
  const keep = select.value;
  select.innerHTML = `<option value="">Alle Arten</option>` + types.map((t) => `<option>${esc(t)}</option>`).join("");
  select.value = types.includes(keep) ? keep : "";
  renderList();
}

const MONTHS = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"];

/** "heute", "gestern", "vor 3 Tagen" – then the plain date. */
function relativeDate(iso) {
  const d = new Date(iso + "T00:00:00");
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const days = Math.round((today - d) / 86400000);
  if (days === 0) return "heute";
  if (days === 1) return "gestern";
  if (days > 1 && days < 7) return `vor ${days} Tagen`;
  return formatDate(iso);
}

function renderList() {
  const q = $("#search").value.trim().toLowerCase();
  const typ = $("#type-filter").value;
  const onlyChanging = $("#only-amending").checked;
  const list = $("#pub-list");
  const items = state.pubs.filter((p) => {
    if (typ && p.typ !== typ) return false;
    if (onlyChanging && !/änder|neuregel|neuordnung|modernisier|umsetzung/i.test(p.title)) return false;
    if (!q) return true;
    return [p.title, p.number, p.fundstelle, p.initiant, p.sachgebiet].join(" ").toLowerCase().includes(q);
  });
  $("#list-count").textContent = q || typ || onlyChanging
    ? `${plural(items.length, "Treffer", "Treffer")} von ${state.pubs.length}`
    : `${plural(state.pubs.length, "Veröffentlichung", "Veröffentlichungen")}, neueste zuerst`;
  if (!items.length) {
    list.innerHTML = `<li class="empty">Nichts gefunden. Versuchen Sie einen anderen Suchbegriff.</li>`;
    return;
  }
  let lastMonth = "";
  list.innerHTML = items.map((p) => {
    const month = p.date.slice(0, 7);
    const heading = month !== lastMonth
      ? `<li class="month" aria-hidden="true">${MONTHS[+month.slice(5, 7) - 1]} ${month.slice(0, 4)}</li>` : "";
    lastMonth = month;
    return `${heading}
    <li><a href="#/${p.teil}/${p.year}/${encodeURIComponent(p.number)}" data-id="${esc(p.id)}" class="${p.id === state.currentId ? "active" : ""}">
      <div class="pub-meta">
        <span class="when">${esc(relativeDate(p.date))}</span>
        <span class="typ typ-${esc((p.typ || "").toLowerCase())}">${esc(p.typ)}</span>
        ${p.sachgebiet ? `<span class="area">${esc(p.sachgebiet.split(";")[0])}</span>` : ""}
      </div>
      <div class="pub-title">${esc(p.title)}</div>
    </a></li>`;
  }).join("");
}

function markActive() {
  $$("#pub-list a").forEach((a) => a.classList.toggle("active", a.dataset.id === state.currentId));
}

// ---------------------------------------------------------------- publication

async function openPublication(teil, year, number, refresh = false) {
  const id = `${teil}/${year}/${number}`;
  state.currentId = id;
  markActive();
  const main = $("#main");
  main.innerHTML = "";
  main.appendChild($("#tpl-loading").content.cloneNode(true));
  main.scrollTop = 0;
  try {
    const item = state.pubs.find((p) => p.id === id);
    if (STATIC && item && !item.analyzed) {
      throw new Error("Diese Veröffentlichung wurde noch nicht ausgewertet. Die Daten werden regelmäßig automatisch aktualisiert – bitte später noch einmal versuchen.");
    }
    const data = await getJSON(api.publication(teil, year, number, refresh));
    if (state.currentId !== id) return; // user navigated away meanwhile
    if (data.error) throw new Error(data.error);
    state.current = data;
    renderPublication();
  } catch (e) {
    if (state.currentId !== id) return;
    main.innerHTML = `<div class="error-box"><strong>Diese Veröffentlichung konnte nicht ausgewertet werden.</strong><br>${esc(e.message)}</div>`;
  }
}

function countStatuses(articles) {
  const c = { applied: 0, consolidated: 0, failed: 0, unsupported: 0 };
  for (const a of articles) for (const i of a.instructions || []) c[i.status] = (c[i.status] || 0) + 1;
  return c;
}

/** Drop the enactment formula and signatures that follow the last article. */
function withoutSignatures(text) {
  return text.split(/\s(?=Die verfassungsmäßigen Rechte|Das vorstehende Gesetz|Der Bundesrat hat zugestimmt|(?:Berlin|Bonn), den )/)[0];
}

const isInForce = (a) => /inkrafttreten|außerkrafttreten|geltungsdauer/i.test(a.heading || "");

function lawLabel(a) {
  const law = a.law;
  if (!law) return a.lawName || a.heading;
  const short = law.shortName && law.shortName !== law.name ? law.shortName : law.name;
  return law.abbreviation ? `${short} (${law.abbreviation})` : short;
}

function renderPublication() {
  const { publication: pub, articles } = state.current;
  const main = $("#main");
  const amendments = articles.filter((a) => a.kind === "amendment");
  const counts = countStatuses(amendments);
  const inForce = articles.filter((a) => a.kind !== "amendment" && isInForce(a));
  const typeHint = TYPE_HINT[pub.typ];
  const enacted = `${pub.typ === "Verordnung" ? "erlassen" : "beschlossen"} ${pub.date.replace(/^Vom /, "am ")}`;

  main.innerHTML = "";
  main.appendChild(el(`
    <section class="pub-header">
      <div class="fundstelle" title="So wird diese Veröffentlichung zitiert">${esc(pub.fundstelle || `BGBl. ${pub.year} I Nr. ${pub.number}`)}</div>
      <h1>${esc(pub.title)}</h1>
      <div class="date">
        ${pub.typ ? `<span class="typ typ-${esc(pub.typ.toLowerCase())}">${esc(pub.typ)}</span>${typeHint ? ` – ${esc(typeHint)}` : ""}` : ""}
      </div>

      <dl class="glance">
        <div>
          <dt>Was ändert sich?</dt>
          <dd>${amendments.length
            ? `<ul class="glance-laws">${articles.map((a, i) => a.kind === "amendment" ? `
                <li><a href="#" data-jump="art-${i}">${esc(lawLabel(a))}</a>
                  <span class="muted">– ${(a.pars || []).length
                    ? plural(a.pars.length, "Vorschrift", "Vorschriften")
                    : "nur im Wortlaut"}</span></li>` : "").join("")}</ul>`
            : `Keine Änderungen an bestehenden Gesetzen erkannt – zum Beispiel, weil es ein ganz neues Gesetz oder eine Bekanntmachung ist. Den Text finden Sie unten.`}</dd>
        </div>
        ${inForce.length ? `<div><dt>Ab wann gilt das?</dt><dd>${inForce.map((a) => esc(withoutSignatures(a.text))).join("<br>")}</dd></div>` : ""}
        <div><dt>Von wem?</dt><dd>${esc(pub.initiant || "–")}, ${esc(enacted)}${pub.issued ? `, veröffentlicht ${esc(relativeDate(pub.issued))}${/^\d/.test(relativeDate(pub.issued)) ? "" : ` (${esc(formatDate(pub.issued))})`}` : ""}</dd></div>
      </dl>

      ${amendments.length ? `<div class="summary">
        ${Object.entries(counts).filter(([, n]) => n).map(([s, n]) => `<span class="badge ${s}" title="${esc(STATUS[s].title)}">${plural(n, "Änderung", "Änderungen")}: ${esc(STATUS[s].label)}</span>`).join("")}
        <button class="linklike" data-help="status">Was bedeutet das?</button>
      </div>` : ""}
      <div class="links">
        <a href="${esc(pub.pdf)}" target="_blank" rel="noopener">Amtliches PDF öffnen ↗</a>
        <a href="${esc(pub.link)}" target="_blank" rel="noopener">Auf recht.bund.de ansehen ↗</a>
        ${STATIC ? "" : `<button class="linklike" data-action="refresh" title="Die Auswertung mit den aktuellsten Daten wiederholen">Neu auswerten</button>`}
      </div>
    </section>`));

  if (amendments.some((a) => (a.pars || []).length)) {
    main.appendChild(el(`
      <div class="color-legend" aria-label="Legende">
        <span><del>durchgestrichen</del> fällt weg</span>
        <span><ins>hinterlegt</ins> kommt neu hinzu</span>
        <span class="muted">Abschnitte ohne Änderung sind eingeklappt – ein Klick blendet sie ein.</span>
      </div>`));
  }

  articles.forEach((a, i) => {
    if (a.kind === "amendment") main.appendChild(renderAmendment(a, i));
    else if (!isInForce(a)) main.appendChild(renderOther(a, i));
  });
  main.appendChild(el(`<button class="to-top" data-action="top" title="Nach oben">↑ Nach oben</button>`));
}

function renderOther(a, i) {
  return el(`
    <article class="article" id="art-${i}">
      <details class="other">
        <summary>
          ${a.number ? `<div class="art-no">Artikel ${esc(a.number)}</div>` : ""}
          <h2>${esc(a.heading || "Text der Veröffentlichung")}</h2>
          <span class="muted">Text anzeigen</span>
        </summary>
        <div class="plain">${esc(a.text)}</div>
      </details>
    </article>`);
}

function renderAmendment(a, i) {
  const law = a.law;
  const card = el(`
    <article class="article" id="art-${i}">
      <header>
        <div class="art-no">${a.number ? `Artikel ${esc(a.number)} · ` : ""}Geändert wird</div>
        <h2>${esc(lawLabel(a))}</h2>
        ${law ? `<div class="law-line">
          ${law.shortName && law.name !== law.shortName ? `<span>${esc(law.name)}</span>` : ""}
          <span class="badge source" title="Woher der aktuelle Gesetzestext stammt">aktueller Text: ${law.source === "gii" ? "gesetze-im-internet.de" : "Rechtsinformationsportal (NeuRIS)"}, Stand ${esc(formatDate(law.version))}</span>
          <a href="${esc(law.url)}" target="_blank" rel="noopener">Ganzes Gesetz ansehen</a>
        </div>` : ""}
      </header>
      ${a.error ? `<div class="error">${esc(a.error)} Die Änderungen werden deshalb nur im Wortlaut angezeigt.</div>` : ""}
      <div class="tabs" role="tablist">
        <button data-tab="synopse" class="active" title="Gegenüberstellung von bisherigem und neuem Text">Vorher / Nachher<span class="count">${(a.pars || []).length}</span></button>
        <button data-tab="befehle" title="So steht die Änderung wörtlich im Gesetzblatt">Wortlaut im Gesetzblatt<span class="count">${(a.instructions || []).length}</span></button>
      </div>
      <div class="tab-body" data-body="synopse"></div>
      <div class="tab-body" data-body="befehle" hidden></div>
    </article>`);

  const syn = $('[data-body="synopse"]', card);
  if (a.pars && a.pars.length) a.pars.forEach((p) => syn.appendChild(renderPar(p, a)));
  else syn.appendChild(el(`<p class="no-pars">Für dieses Gesetz konnte keine Gegenüberstellung erzeugt werden. Unter „Wortlaut im Gesetzblatt“ sehen Sie die Änderungen so, wie sie veröffentlicht wurden.</p>`));
  const cmd = $('[data-body="befehle"]', card);
  cmd.appendChild(el(`<p class="tab-intro">Gesetzesänderungen werden als Anweisungen formuliert („… wird durch … ersetzt“). Hier steht jede Anweisung im Originalwortlaut – und ob bundesdiff sie anwenden konnte.</p>`));
  cmd.appendChild(renderInstructions(a.instructions || []));
  return card;
}

function renderInstructions(list) {
  const ol = el(`<ol class="instructions"></ol>`);
  for (const ins of list) {
    const st = STATUS[ins.status] || STATUS.unsupported;
    ol.appendChild(el(`
      <li>
        <span class="marker">${esc(ins.marker)}</span>
        <div>
          <div class="raw ${ins.raw.length > 400 ? "clamped" : ""}" title="${ins.raw.length > 400 ? "Klicken zum Aufklappen" : ""}">${highlightQuotes(ins.raw)}</div>
          <div class="where">${esc(ins.opLabel)}${ins.location ? ` · betrifft ${esc(ins.location)}` : ""}</div>
          ${ins.message && ins.status === "failed" ? `<div class="msg">Grund: ${esc(ins.message)}</div>` : ""}
        </div>
        <span class="badge ${esc(ins.status)}" title="${esc(st.title)}">${esc(st.label)}</span>
      </li>`));
  }
  return ol;
}

function highlightQuotes(text) {
  // mark top-level „…“ quotes (they may contain nested quotes)
  let out = "", depth = 0;
  for (const ch of text) {
    if (ch === "„") { if (depth === 0) out += "<q>"; else out += esc(ch); depth++; continue; }
    if (ch === "“" && depth > 0) { depth--; if (depth === 0) out += "</q>"; else out += esc(ch); continue; }
    out += esc(ch);
  }
  return out + (depth > 0 ? "</q>" : "");
}

function changeSummary(p) {
  if (p.isNew) return "komplett neue Vorschrift";
  if (p.isRemoved) return "Vorschrift entfällt";
  const { changed, inserted, deleted } = p.stats;
  const bits = [];
  if (changed) bits.push(plural(changed, "Abschnitt geändert", "Abschnitte geändert"));
  if (inserted) bits.push(plural(inserted, "Abschnitt neu", "Abschnitte neu"));
  if (deleted) bits.push(plural(deleted, "Abschnitt gestrichen", "Abschnitte gestrichen"));
  return bits.join(" · ") || "keine sichtbare Textänderung";
}

/** Five squares like GitHub's diffstat: share of added vs. removed lines. */
function statBar(stats) {
  const ins = stats.inserted + stats.changed, del = stats.deleted + stats.changed, total = ins + del;
  if (!total) return "";
  const nIns = Math.round((ins / total) * 5);
  const boxes = Array.from({ length: 5 }, (_, i) => `<i class="${i < nIns ? "ins" : "del"}"></i>`).join("");
  return `<span class="stat-bar" aria-hidden="true">${boxes}</span>`;
}

function renderPar(p, article) {
  const section = el(`
    <section class="par">
      <header>
        <h3>${esc(p.title)}</h3>
        <div class="par-meta">
          <span>${esc(changeSummary(p))}</span>${statBar(p.stats)}
          <button class="how" data-how="${esc(p.key)}" title="Wie wurde diese Gegenüberstellung erzeugt?">Wie ermittelt?</button>
        </div>
      </header>
      ${p.source ? `<div class="par-note">Der bisherige Text stammt aus einer älteren, archivierten Fassung (${esc(p.source)}). Sie kann auch Änderungen enthalten, die nicht aus dieser Veröffentlichung stammen.</div>` : ""}
    </section>`);
  $(".how", section).addEventListener("click", () => showHow(p, article));
  section.appendChild(renderDiff(p.rows));
  return section;
}

function segHTML(segs) {
  if (!segs) return "";
  return segs.map((sg) => {
    const text = esc(sg.s).replace(esc(UNKNOWN), `<span class="unknown">bisheriger Text nicht ermittelbar</span>`);
    if (sg.t === "del") return `<del>${text}</del>`;
    if (sg.t === "ins") return `<ins>${text}</ins>`;
    return text;
  }).join("");
}

function renderDiff(rows) {
  const split = state.view === "split";
  const table = el(`<table class="diff ${split ? "split" : "inline"}"></table>`);
  // Layout like a code review: a narrow gutter with −/+ before each text column
  table.innerHTML = split
    ? `<colgroup><col class="gutter"><col><col class="gutter"><col></colgroup>
       <thead class="diff-head"><tr><th colspan="2">Vorher · bisheriger Text</th><th colspan="2">Nachher · neuer Text</th></tr></thead>`
    : `<colgroup><col class="gutter"><col></colgroup>
       <thead class="diff-head"><tr><th colspan="2">Text mit markierten Änderungen</th></tr></thead>`;
  const cols = split ? 4 : 2;
  const tbody = document.createElement("tbody");
  table.appendChild(tbody);

  // which rows are visible when folding unchanged text
  const visible = rows.map((r) => r.op !== "equal");
  if (state.onlyChanges) {
    rows.forEach((r, i) => {
      if (r.op === "equal") return;
      for (let k = Math.max(0, i - CONTEXT); k <= Math.min(rows.length - 1, i + CONTEXT); k++) visible[k] = true;
    });
  } else {
    visible.fill(true);
  }

  const GUTTER = { equal: ["", ""], change: ["−", "+"], delete: ["−", ""], insert: ["", "+"] };
  const rowEl = (r) => {
    const cls = `d${Math.min(r.depth, 4)}`;
    const [gl, gr] = GUTTER[r.op];
    if (split) {
      const l = r.left
        ? `<td class="g l">${gl}</td><td class="text l"><span class="${cls}">${segHTML(r.left)}</span></td>`
        : `<td class="g l"></td><td class="text l empty" title="Gab es vorher nicht"></td>`;
      const rr = r.right
        ? `<td class="g r">${gr}</td><td class="text r"><span class="${cls}">${segHTML(r.right)}</span></td>`
        : `<td class="g r"></td><td class="text r empty" title="Fällt künftig weg"></td>`;
      return tr(`<tr class="${r.op}">${l}${rr}</tr>`);
    }
    const g = { equal: "", change: "±", delete: "−", insert: "+" }[r.op];
    return tr(`<tr class="${r.op}"><td class="g">${g}</td><td class="text"><span class="${cls}">${segHTML(r.inline || r.right || r.left)}</span></td></tr>`);
  };

  let i = 0;
  while (i < rows.length) {
    if (visible[i]) { tbody.appendChild(rowEl(rows[i])); i++; continue; }
    let j = i;
    while (j < rows.length && !visible[j]) j++;
    const hidden = rows.slice(i, j);
    const fold = tr(`<tr class="fold"><td colspan="${cols}"><button title="Einblenden">@@ ${plural(hidden.length, "unveränderter Abschnitt", "unveränderte Abschnitte")} – anzeigen @@</button></td></tr>`);
    $("button", fold).addEventListener("click", () => {
      const frag = document.createDocumentFragment();
      hidden.forEach((r) => frag.appendChild(rowEl(r)));
      fold.replaceWith(frag);
    });
    tbody.appendChild(fold);
    i = j;
  }
  if (!rows.length) tbody.appendChild(tr(`<tr><td class="no-pars" colspan="${cols}">Kein Text vorhanden.</td></tr>`));
  return table;
}

// ---------------------------------------------------------------- explanations

function openDialog(title, html) {
  const dlg = $("#dialog");
  $("#dialog-title").textContent = title;
  $("#dialog-body").innerHTML = html;
  dlg.showModal();
  $("#dialog-body").scrollTop = 0;
}

/** Explain, for one paragraph, how its before/after texts were obtained. */
function showHow(p, article) {
  const law = article.law || {};
  const src = law.source === "gii" ? "gesetze-im-internet.de" : "dem Rechtsinformationsportal des Bundes (NeuRIS)";
  const parLabel = p.title.split(" ").slice(0, 2).join(" "); // "§ 38"
  const related = (article.instructions || []).filter((i) => i.location === parLabel || (i.location || "").startsWith(parLabel + " "));
  let how;
  if (p.state === "post") {
    how = `<p>Der aktuelle Text von <strong>${esc(p.title)}</strong> auf ${esc(src)} (Stand ${esc(formatDate(law.version))})
      <strong>enthält diese Änderung bereits</strong>. Er bildet deshalb die rechte Spalte „Nachher“.</p>
      <p>Die linke Spalte „Vorher“ wurde <strong>zurückgerechnet</strong>: Die Anweisungen aus dem Gesetzblatt wurden rückwärts
      angewendet (aus „B ersetzt A“ wird wieder A).
      ${p.source
        ? `Wo das nicht möglich ist – etwa wenn ein ganzer Absatz neu gefasst wurde –, stammt der alte Wortlaut aus einer
           ${esc(p.source)}.`
        : "Dafür war keine ältere Fassung nötig."}</p>`;
  } else {
    how = `<p>Der aktuelle Text von <strong>${esc(p.title)}</strong> auf ${esc(src)} (Stand ${esc(formatDate(law.version))})
      <strong>enthält diese Änderung noch nicht</strong> – oft, weil sie erst später in Kraft tritt oder die Datenbank noch nicht aktualisiert wurde.
      Er bildet deshalb die linke Spalte „Vorher“.</p>
      <p>Die rechte Spalte „Nachher“ hat bundesdiff <strong>selbst berechnet</strong>, indem es die Anweisungen aus dem Gesetzblatt auf diesen Text angewendet hat.</p>`;
  }
  const list = related.length
    ? `<h3>Angewendete Anweisungen</h3><ol class="how-list">${related.map((i) =>
        `<li>${highlightQuotes(i.raw)} <span class="badge ${esc(i.status)}">${esc((STATUS[i.status] || STATUS.unsupported).label)}</span></li>`).join("")}</ol>`
    : "";
  openDialog(`Wie wurde ${parLabel} ermittelt?`, how + list +
    `<p class="muted">Ohne Gewähr – rechtsverbindlich ist allein das amtliche Bundesgesetzblatt.</p>`);
}

function showHelp(section) {
  openDialog("So funktioniert bundesdiff", $("#tpl-help").innerHTML);
  if (section) document.getElementById(`help-${section}`)?.scrollIntoView();
}

// ---------------------------------------------------------------- events & routing

function route() {
  const m = /^#\/(1)\/(\d{4})\/([^/]+)$/.exec(location.hash);
  if (m) {
    openPublication(m[1], m[2], decodeURIComponent(m[3]));
  }
}

function syncControls() {
  $$("[data-view]").forEach((b) => b.classList.toggle("active", b.dataset.view === state.view));
  $("#only-changes").checked = state.onlyChanges;
}

function rerender() {
  if (state.current && $("#main .pub-header")) renderPublication();
}

document.addEventListener("click", (ev) => {
  const t = ev.target;
  if (t.closest("#theme-toggle")) { toggleTheme(); return; }
  if (t.closest('[data-action="top"]')) { $("#main").scrollTo({ top: 0, behavior: "smooth" }); window.scrollTo({ top: 0, behavior: "smooth" }); return; }
  const view = t.closest("[data-view]");
  if (view) {
    state.view = view.dataset.view; localSet("view", state.view); syncControls(); rerender(); return;
  }
  const help = t.closest("[data-help]");
  if (help) { ev.preventDefault(); showHelp(help.dataset.help); return; }
  if (t.closest("#dialog-close")) { $("#dialog").close(); return; }
  if (t.id === "dialog") { $("#dialog").close(); return; } // click on backdrop
  const tab = t.closest(".tabs button");
  if (tab) {
    const card = tab.closest(".article");
    $$(".tabs button", card).forEach((b) => b.classList.toggle("active", b === tab));
    $$(".tab-body", card).forEach((b) => { b.hidden = b.dataset.body !== tab.dataset.tab; });
    return;
  }
  const jump = t.closest("[data-jump]");
  if (jump) {
    ev.preventDefault();
    document.getElementById(jump.dataset.jump)?.scrollIntoView({ behavior: "smooth", block: "start" });
    return;
  }
  if (t.closest('[data-action="refresh"]')) {
    const pub = state.current?.publication;
    if (pub) openPublication(pub.teil, String(pub.year), pub.number, true);
    return;
  }
  const raw = t.closest(".raw.clamped");
  if (raw) raw.classList.remove("clamped");
});

$("#only-changes").addEventListener("change", (ev) => {
  state.onlyChanges = ev.target.checked; localSet("onlyChanges", state.onlyChanges ? "1" : "0"); rerender();
});
$("#search").addEventListener("input", renderList);
$("#type-filter").addEventListener("change", renderList);
$("#only-amending").addEventListener("change", renderList);
window.addEventListener("hashchange", route);

async function showDataDate() {
  if (!STATIC) return;
  try {
    const meta = await getJSON("data/meta.json");
    $("#data-date").textContent = `Datenstand: ${formatDate(meta.generated)}, ${meta.generated.slice(11, 16)} UTC · Veröffentlichungen seit ${formatDate(meta.since)}`;
  } catch { /* optional */ }
}

// ---------------------------------------------------------------- light / dark

function currentTheme() {
  return document.documentElement.dataset.theme
    || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
}

function showThemeButton() {
  const dark = currentTheme() === "dark";
  const btn = $("#theme-toggle");
  btn.textContent = dark ? "☀ Hell" : "☾ Dunkel";
  btn.title = dark ? "Zur hellen Ansicht wechseln" : "Zur dunklen Ansicht wechseln";
}

function toggleTheme() {
  const next = currentTheme() === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  localSet("theme", next);
  showThemeButton();
}

// "/" jumps to the search field, like on many websites
document.addEventListener("keydown", (ev) => {
  if (ev.key === "/" && !/INPUT|SELECT|TEXTAREA/.test(document.activeElement.tagName) && !$("#dialog").open) {
    ev.preventDefault();
    $("#search").focus();
  }
});

syncControls();
showThemeButton();
showDataDate();
loadList().then(route);
