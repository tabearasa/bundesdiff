"use strict";

const UNKNOWN = "⟪frühere Fassung nicht ermittelbar⟫";
const CONTEXT = 1; // unchanged lines shown around changes when folding
// no animated scrolling for readers who turned motion off in their system settings
const SCROLL = () => matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";

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
  // bills (spec 016)
  bills: () => STATIC ? "data/entwuerfe.json" : "/api/entwuerfe",
  bill: (wp, number) => STATIC ? `data/entwurf/${wp}/${number}.json` : `/api/entwuerfe/${wp}/${number}`,
  billInfo: (wp, number) => STATIC ? `data/entwurf/${wp}/${number}-info.json` : `/api/entwuerfe/${wp}/${number}/info`,
};

const state = {
  lastRead: null, // the publication read last: marked in the timeline (NAV-5)
  timeline: "#/", // the timeline as the reader left it, with its filter and view: the back arrow leads there (PTL-11)
  teil: "1", // only Teil I (Gesetze und Verordnungen); Teil II = international treaties is not shown
  view: localGet("view") || "split",
  onlyChanges: localGet("onlyChanges") !== "0",
  pubs: [],
  current: null, // analysis result – of a publication, or of a bill (then with .draft)
  currentId: null,
  bills: null, // the list of bills, once loaded
  info: null, // Vorblatt and Begründung of the bill on screen, once asked for (a promise) …
  infoParts: null, // … and once loaded
};

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const PUBLICATION_ROUTE = /^#\/(1)\/(\d{4})\/([^/]+)$/;
const ABOUT_ROUTE = "#/ueber";
const BILLS_ROUTE = "#/entwuerfe";
const BILL_ROUTE = /^#\/entwurf\/(\d{1,2})\/(\d{1,5})$/;

function localGet(key) {
  try { return localStorage.getItem("bundesdiff." + key); } catch { return null; }
}
function localSet(key, value) {
  try { localStorage.setItem("bundesdiff." + key, value); } catch { /* ignore */ }
}

function esc(text) {
  return String(text ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// Domain names in text from the data („Archivfassung von gesetze-im-internet.de vom …“) are
// never hyphenated (see .domain in style.css); a long one may also break after a dot.
const DOMAIN = /(?<![\p{L}\d.-])[a-z\d-]+(?:\.[a-z\d-]+)*\.(?:de|org|eu)(?![\p{L}\d])/gu;
function escWithDomains(text) {
  return esc(text).replace(DOMAIN, (d) => `<span class="domain">${d.replace(/\.(?=[^.]*\.)/g, ".<wbr>")}</span>`);
}

// Where an old text came from, as the object of „stammt aus …“, in plain words. The analysis
// writes „Archivfassung von gesetze-im-internet.de vom 15.06.2024 (Internet Archive)“ or
// „lokal gespeicherte Fassung vom 01.02.2026 (gesetze-im-internet.de)“.
function oldSource(source) {
  // „15.06.2024“ → „15. Juni 2024“, as dates are written in running text; never torn apart or
  // hyphenated („Septem-/ber“), see .whole-date
  const day = (d) => `<span class="whole-date">${esc(fullDate(d.split(".").reverse().join("-")))}</span>`;
  const archived = /^Archivfassung von (\S+) vom (\d\d\.\d\d\.\d{4}) \(Internet Archive\)$/.exec(source);
  if (archived) {
    return `einer Kopie von ${escWithDomains(archived[1])}, die das Internet Archive am ${day(archived[2])} gespeichert hat`;
  }
  const stored = /^lokal gespeicherte Fassung vom (\d\d\.\d\d\.\d{4}) \((NeuRIS|\S+)\)$/.exec(source);
  if (stored) {
    const site = stored[2] === "NeuRIS" ? "vom Rechtsinformationsportal des Bundes" : `von ${escWithDomains(stored[2])}`;
    return `einer Fassung ${site}, die <span class="name">bundesdiff</span> am ${day(stored[1])} gespeichert hat`;
  }
  return `einer anderen Fassung (${escWithDomains(source)})`;
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

/** "20. Oktober 2026" – how dates are written in running text. */
function fullDate(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || "");
  return m ? `${+m[3]}. ${["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September",
    "Oktober", "November", "Dezember"][+m[2] - 1]} ${m[1]}` : iso || "";
}

function formatDate(iso) {
  if (!iso) return "";
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  return m ? `${m[3]}.${m[2]}.${m[1]}` : iso;
}

/** "… Nr. 326 vom 30.10.2026": "vom" is not left alone at the end of a line (A11Y-5). */
const keepDate = (citation) => citation.replace(/ vom /, " vom\u00a0");

function plural(n, one, many) {
  return `${n}\u00a0${n === 1 ? one : many}`;  // number and noun never on different lines
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

// ---------------------------------------------------------------- timeline (spec 002)

async function loadList() {
  try {
    state.pubs = await getJSON(api.list(state.teil));
  } catch (e) {
    state.listError = e.message;
    return;
  }
  buildSearchIndex();
}

const MONTHS = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"];
const WEEKDAYS = ["Sonntag", "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag"];
const DAY = 86400000;

/** Like Map.groupBy, which older phones (iOS before 17.4) do not have; keeps the order. */
function groupBy(items, key) {
  const groups = new Map();
  for (const item of items) {
    const k = key(item);
    if (!groups.has(k)) groups.set(k, []);
    groups.get(k).push(item);
  }
  return groups;
}

function today() {
  const d = new Date(); d.setHours(0, 0, 0, 0);
  return d;
}

const isoDay = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

/** "heute", "gestern", "vor 3 Tagen", "morgen", "in 3 Tagen" – nothing for dates further away. */
function relativeDay(iso) {
  const days = Math.round((new Date(iso + "T00:00:00") - today()) / DAY);
  if (days === 0) return "heute";
  if (days === -1) return "gestern";
  if (days === 1) return "morgen";
  if (days < 0 && days > -7) return `vor ${-days} Tagen`;
  if (days > 0 && days < 7) return `in ${days} Tagen`;
  return "";
}

/** "Freitag, 30. Oktober" (with the year where the heading above has none). */
function longDate(iso, withYear) {
  const d = new Date(iso + "T00:00:00");
  return `${WEEKDAYS[d.getDay()]}, ${d.getDate()}. ${MONTHS[d.getMonth()]}${withYear ? ` ${d.getFullYear()}` : ""}`;
}

const pubHref = (p) => `#/${p.teil}/${p.year}/${encodeURIComponent(p.number)}`;

/** Filters and view of the timeline live in the address, so a view can be shared (TL-4). */
function timelineParams() {
  const params = new URLSearchParams(location.hash.split("?")[1] || "");
  params.delete("nur"); // the removed filter "nur Gesetzesänderungen": old links show everything
  return params;
}

/** The back arrow and "Veröffentlichungen" lead to the timeline as the reader left it (PTL-11, NAV-1);
 *  the logo leads to the plain start page. On that timeline already, "Veröffentlichungen" goes to its top. */
function rememberTimeline(hash) {
  state.timeline = hash;
  for (const a of $$('#fab-back, [data-nav="list"]')) a.setAttribute("href", hash);
}

document.addEventListener("click", (ev) => {
  const link = ev.target.closest?.('[data-nav="list"]');
  if (!link || link.getAttribute("href") !== (location.hash || "#/")) return;
  if (ev.button !== 0 || ev.ctrlKey || ev.metaKey || ev.shiftKey || ev.altKey) return; // a new tab or window
  ev.preventDefault(); // the same address: no hashchange would happen, and the link would seem broken
  scrollTo({ top: 0, behavior: REDUCED.matches ? "auto" : "smooth" });
});

function setTimelineParams(params, keepFilters = false) {
  const query = params.toString();
  rememberTimeline(query ? `#/?${query}` : "#/");
  history.replaceState(null, "", state.timeline);
  renderTimeline(keepFilters);
}

function changesLabel(p) {
  if (p.failed) return "konnte nicht ausgewertet werden";
  if (!p.analyzed) return "noch nicht ausgewertet";
  const n = (p.laws || []).length;
  return n ? `ändert ${plural(n, "Gesetz", "Gesetze")}` : "ändert kein Gesetz";
}

function renderTimeline(keepFilters = false) {
  const params = timelineParams();
  const upcoming = params.get("ansicht") === "demnaechst";
  const types = [...new Set(state.pubs.map((p) => p.typ).filter(Boolean))].sort();
  // a type from a link in other letters is the same type; an unknown one is ignored
  const wanted = (params.get("art") || "").toLowerCase();
  const typ = types.find((t) => t.toLowerCase() === wanted) || "";
  const pubs = state.pubs.filter((p) => !typ || p.typ === typ);
  const focused = document.activeElement?.id || document.activeElement?.dataset?.order;

  const main = $("#main");
  const shown = $(".timeline-page");
  if (!keepFilters || !shown) {
    main.innerHTML = "";
    main.appendChild($("#tpl-intro").content.cloneNode(true));
  }
  if (state.listError) {
    main.appendChild(el(`<div class="error-box"><strong>Die Liste der Veröffentlichungen konnte nicht geladen werden.</strong><br>${esc(state.listError)}<br>Bitte laden Sie die Seite später noch einmal.</div>`));
    return;
  }
  if (!keepFilters || !shown) {
    const notice = oldDataNotice();
    if (notice) main.appendChild(notice);
  }
  const months = [...new Set(pubs.map((p) => p.date.slice(0, 7)))];
  const section = el(`
    <section class="timeline-page" aria-label="Veröffentlichungen">
      <div class="tl-controls">
        <div class="segmented tl-order" role="group" aria-label="Reihenfolge">
          <button data-order="published" class="${upcoming ? "" : "active"}" aria-pressed="${!upcoming}">Nach Veröffentlichung</button>
          <button data-order="upcoming" class="${upcoming ? "active" : ""}" aria-pressed="${upcoming}">Was ändert sich demnächst?</button>
        </div>
        <div class="tl-filters">
          <span class="tl-type"><label for="type-filter">Art</label>
            <select id="type-filter">
              <option value="">Alle Arten</option>
              ${types.map((t) => `<option${t === typ ? " selected" : ""}>${esc(t)}</option>`).join("")}
            </select>
          </span>
          <p class="hidden-status" role="status"></p>
        </div>
        ${upcoming || months.length < 2 ? "" : `
        <nav class="tl-months" aria-label="Monate">
          ${months.map((m) => `<a href="#/" data-month="m-${m}">${MONTHS[+m.slice(5, 7) - 1]} ${m.slice(0, 4)}</a>`).join("")}
        </nav>`}
      </div>
      ${upcoming ? renderUpcoming(pubs, typ) : renderPublished(pubs)}
      <p class="data-date" id="data-date">${esc(state.dataDate || "")}</p>
    </section>`);
  if (keepFilters && shown) {
    // the filter stays the same element: Safari on the iPhone opened the list of "Art" a
    // second time when the open list was replaced and the new one got the focus
    const filters = $(".tl-filters", shown), controls = filters.parentElement;
    for (const node of [...shown.children]) if (node !== controls) node.remove();
    for (const node of [...controls.children]) if (node !== filters) node.remove();
    const fresh = $(".tl-controls", section), parts = [...fresh.children];
    const at = parts.indexOf($(".tl-filters", fresh));
    filters.before(...parts.slice(0, at));
    filters.after(...parts.slice(at + 1));
    fresh.remove();
    shown.append(...section.children);
    // the focus stays on the list: a status message says that the timeline changed
    const of = typ ? `der Art „${typ}“` : "aller Arten";
    // the upcoming view: the coming dates under "Demnächst", as the page counts them
    const dates = $$(".timeline.upcoming > .tl-month:first-child .tl-day:not(.tl-undated)", shown).length;
    $("[role=status]", filters).textContent = !upcoming
      ? `${plural(pubs.length, "Veröffentlichung", "Veröffentlichungen")} ${of}`
      : dates ? `${plural(dates, "kommender Termin", "kommende Termine")} für Veröffentlichungen ${of}`
      : `Keine kommenden Termine für Veröffentlichungen ${of}`;
    initLens();
    return;
  }
  main.appendChild(section);
  if (focused) (document.getElementById(focused) || $(`[data-order="${focused}"]`))?.focus();
  initLens();
}

function renderPublished(pubs) {
  if (!pubs.length) return `<p class="tl-empty">Keine Veröffentlichung dieser Art.</p>`;
  const byMonth = groupBy(pubs, (p) => p.date.slice(0, 7));
  return `
    <p class="list-count">${plural(pubs.length, "Veröffentlichung", "Veröffentlichungen")}, neueste zuerst</p>
    <ol class="timeline">${[...byMonth].map(([month, inMonth]) => `
      <li class="tl-month">
        <h2 id="m-${month}" tabindex="-1">${MONTHS[+month.slice(5, 7) - 1]} ${month.slice(0, 4)}</h2>
        <ol class="tl-days">${[...groupBy(inMonth, (p) => p.date)].map(([day, onDay]) => `
          <li class="tl-day">
            ${dayHeading(day, false)}
            <ol class="tl-entries">${onDay.map((p) => `
              <li>${entryLink(p, `<span class="tl-changes">${esc(changesLabel(p))}</span>`,
                topicsLine(p))}</li>`).join("")}
            </ol>
          </li>`).join("")}
        </ol>
      </li>`).join("")}
    </ol>`;
}

function dayHeading(iso, withYear) {
  const rel = relativeDay(iso);
  return `<span class="tl-mark" aria-hidden="true"></span><h3 class="tl-date"><time datetime="${iso}">${longDate(iso, withYear)}</time>${rel ? ` <span class="tl-rel">${rel}</span>` : ""}</h3>`;
}

/** The topics of a publication, set so that "und -zwangsverfahren" and "Deutsche Telekom AG"
 * keep the hyphen and "AG" with their words: a no-break space before them, a word joiner after
 * the hyphen. Also in the search results. */
function topicList(p) {
  return (p.sachgebiet || "").split(";")
    .map((t) => t.trim().replace(/ (?=-\p{L}|AG\b)/gu, "\u00a0").replace(/\u00a0-(?=\p{L})/gu, "\u00a0-\u2060"))
    .filter(Boolean);
}

/** Up to four topics; of more the first three and "· 9 weitere Sachgebiete": some publications
 * have a dozen (PTL-2). Not cut off with "…", which would leave a word torn before it ("Ver-…").
 * No-break spaces: a line never starts with "·", and the count stays with its word. */
function topicsLine(p) {
  const topics = topicList(p);
  if (!topics.length) return "";
  const shown = topics.length > 4 ? [...topics.slice(0, 3), `${topics.length - 3}\u00a0weitere Sachgebiete`] : topics;
  return `<span class="tl-topics">${esc(shown.join("\u00a0· "))}</span>`;
}

function entryLink(p, meta, extra) {
  return `<a class="tl-entry${p.id === state.lastRead ? " last-read" : ""}" href="${pubHref(p)}" data-id="${esc(p.id)}">
    <span class="tl-meta"><span class="typ">${esc(p.typ)}</span>${meta}</span>
    <span class="tl-title">${esc(p.title)}</span>${extra}
  </a>`;
}

const ACT = {
  Gesetz: ["das ganze Gesetz", "die übrigen Teile des Gesetzes"],
  Verordnung: ["die ganze Verordnung", "die übrigen Teile der Verordnung"],
};

/** What takes effect, in plain words: "die ganze Verordnung", "Artikel 2 – Tabaksteuerverordnung". */
function inForceWhat(p, e) {
  // a sentence whose subject could not be read: say only that, the wording stands below (TL-7)
  if (e.kind === "unclear") return "Was in Kraft oder außer Kraft tritt, steht im Wortlaut";
  const act = ACT[p.typ] || ["die ganze Veröffentlichung", "die übrigen Teile der Veröffentlichung"];
  let what;
  if (e.whole) what = act[e.rest ? 1 : 0];
  else if (e.articles?.length) {
    what = e.articles.map((n) => {
      const law = (p.laws || []).find((l) => l.articles.includes(n));
      return law ? `Artikel ${n} – ${law.name}` : `Artikel ${n}`;
    }).join("; ");
  } else what = e.subject || "ein Teil der Veröffentlichung";
  const past = e.date && e.date < isoDay(today());
  const verb = e.kind === "out" ? (past ? "ist außer Kraft getreten" : "tritt außer Kraft")
    : (past ? "ist in Kraft getreten" : "tritt in Kraft");
  return `${verb}: ${what}${e.retroactive ? " (rückwirkend)" : ""}`;
}

function renderUpcoming(pubs, typ = "") {
  const now = isoDay(today());
  const monthAgo = isoDay(new Date(today() - 30 * DAY));
  const events = pubs.flatMap((p) => (p.inForce || []).map((e) => ({ p, e })));
  const soon = events.filter(({ e }) => e.date && e.date >= now).sort((a, b) => a.e.date.localeCompare(b.e.date));
  const recent = events.filter(({ e }) => e.date && e.date < now && e.date >= monthAgo)
    .sort((a, b) => b.e.date.localeCompare(a.e.date));
  const unclear = events.filter(({ e }) => !e.date);
  const section = (title, list, empty) => `
    <li class="tl-month">
      <h2>${title}</h2>
      ${list.length ? `<ol class="tl-days">${[...groupBy(list, ({ e }) => e.date || "")].map(([day, onDay]) => `
        <li class="tl-day${day ? "" : " tl-undated"}">
          ${day ? dayHeading(day, true) : ""}
          <ol class="tl-entries">${onDay.map(({ p, e }) => `
            <li>${entryLink(p, "", `<span class="tl-what">${esc(inForceWhat(p, e))}</span>`)}
              ${day ? `<details class="tl-source"><summary>Wortlaut</summary><p>${esc(e.sentence)}</p></details>`
                    : `<p class="tl-sentence">„${esc(e.sentence)}“</p>`}</li>`).join("")}
          </ol>
        </li>`).join("")}
      </ol>` : `<p class="tl-empty">${empty}</p>`}
    </li>`;
  return `
    <p class="tl-note">Die Daten werden automatisch aus dem Wortlaut der Vorschriften über das Inkrafttreten gelesen
      und gelten nur für Veröffentlichungen, die <span class="name">bundesdiff</span> schon ausgewertet hat – verbindlich ist allein das Bundesgesetzblatt.</p>
    <ol class="timeline upcoming">
      ${section("Demnächst", soon, `${typ ? `Für Veröffentlichungen der Art <span class="keep">„${esc(typ)}“</span> sind` : "Es sind"} keine kommenden Termine bekannt, an denen etwas in Kraft oder außer Kraft tritt.`)}
      ${recent.length ? section(recent.some(({ e }) => e.kind === "out") ? "Kürzlich in Kraft oder außer Kraft getreten" : "Kürzlich in Kraft getreten", recent) : ""}
      ${unclear.length ? section("Datum nicht sicher erkannt", unclear) : ""}
    </ol>`;
}

/** Coming back from a publication: show and focus its entry (NAV-5); in the timeline it is the card (PTL-11). */
function showLastRead() {
  const entry = state.lastRead && $(`.tl-entry[data-id="${CSS.escape(state.lastRead)}"]`);
  if (!entry) return false;
  if (lens.entries.includes(entry)) {
    setLensFocus(entry);
    glideToMiddle(entry, "auto");
  } else entry.scrollIntoView({ block: "center" });
  entry.focus({ preventScroll: true });
  return true;
}

// ---------------------------------------------------------------- the lens (PTL-2, PTL-8)

const PHONE = matchMedia("(max-width: 599px) and (min-height: 480px)"); // PTL-1, also in style.css
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)");
// pos: where every entry is on the page (from its top). The lens only scales them, around their
// left middle, so that does not change while scrolling: measured once, not in every frame.
// hold: the entry reached with the keyboard, the card while the page glides to it.
const lens = { entries: [], pos: [], focus: null, frame: 0, hold: null, width: innerWidth };
const watchTimeline = new ResizeObserver(() => { measureLens(); drawLens(); });

function lensActive() {
  return lens.entries.length > 0;
}

/** After rendering the timeline: in the order "Nach Veröffentlichung" the newest entry is the card. */
function initLens() {
  watchTimeline.disconnect();
  lens.focus = null;
  lens.entries = $$(".timeline:not(.upcoming) .tl-entry");
  if (!lens.entries.length) return;
  measureLens();
  watchTimeline.observe($(".timeline:not(.upcoming)")); // its entries
  watchTimeline.observe(document.body); // and everything above it
  setLensFocus(entryAtMiddle() || lens.entries[0]);
}

/** Every entry with the half of the gaps to its neighbours (cell): the middle of the screen is
 * always in exactly one cell, and where two cells meet both entries are drawn at full size,
 * so the card can change without either of them jumping in size. */
function measureLens() {
  const boxes = lens.entries.map((e) => {
    const r = e.getBoundingClientRect(), mid = r.top + r.height / 2 + scrollY, height = e.offsetHeight;
    return { mid, height, top: mid - height / 2, bottom: mid + height / 2 };
  });
  lens.pos = boxes.map((b, i) => ({
    ...b,
    from: i ? (boxes[i - 1].bottom + b.top) / 2 : b.top,
    to: i < boxes.length - 1 ? (b.bottom + boxes[i + 1].top) / 2 : b.bottom,
  }));
}

/** How far the cell of an entry is from the middle of the screen: 0 while it holds the middle. */
function distanceFromMiddle(i) {
  const { from, to } = lens.pos[i], mid = scrollY + innerHeight / 2;
  return Math.max(0, from - mid, mid - to);
}

/** The card is drawn at full size; every other entry shrinks smoothly with its distance from
 * the middle of the screen, to 88 % – in every frame while scrolling, so nothing pops up later. */
function drawLens() {
  lens.frame = 0;
  const reach = Math.max(120, innerHeight * 0.22);
  lens.entries.forEach((e, i) => {
    let scale = ""; // written only when it changes: far away every entry stays at 88 %
    if (e !== lens.focus && !REDUCED.matches) {
      const t = Math.max(0, 1 - distanceFromMiddle(i) / reach);
      scale = `scale(${(0.88 + 0.12 * t * t * (3 - 2 * t)).toFixed(3)})`;
    }
    if (e.style.transform !== scale) e.style.transform = scale;
  });
}

/** Makes `entry` the card. Card and other entries are equally high: the page never jumps. */
function setLensFocus(entry) {
  if (!entry) return;
  if (entry !== lens.focus) {
    lens.focus?.classList.remove("tl-focus");
    lens.focus = entry;
    entry.classList.add("tl-focus");
  }
  drawLens();
}

/** Glides the card into the middle – as far as it fits between the navbar or the top and the
 * round buttons. Only after an action of the reader: an entry reached with the keyboard, back from
 * a publication, turning the phone (PTL-2, PTL-A1, PTL-11). */
function glideToMiddle(entry, behavior) {
  const at = lens.pos[lens.entries.indexOf(entry)];
  if (!at) return; // the timeline is gone meanwhile: a publication opened before the frame ran
  const { mid, height } = at;
  const styles = getComputedStyle(document.documentElement);
  const above = (parseFloat(styles.getPropertyValue("--topbar-h")) || 0) + 12;
  const below = innerHeight - ((parseFloat(styles.scrollPaddingBottom) || 0) + 8);
  const place = Math.max(above, Math.min(innerHeight / 2 - height / 2, below - height));
  const top = Math.max(0, mid - height / 2 - place);
  if (Math.abs(top - scrollY) < 2) return;
  window.scrollTo({ top, behavior: behavior || (REDUCED.matches ? "auto" : "smooth") });
}

/** The entry whose cell holds the middle of the screen; at the very top the newest entry.
 * While the page glides to an entry reached with the keyboard, that entry stays the card – else
 * the entries it passes would light up on the way (PTL-2). */
function entryAtMiddle() {
  if (lens.hold) {
    const h = lens.entries.indexOf(lens.hold);
    if (h >= 0 && document.activeElement === lens.hold && performance.now() < lens.holdUntil) {
      if (distanceFromMiddle(h) === 0) lens.hold = null; // arrived
      return lens.entries[h];
    }
    lens.hold = null;
  }
  if (scrollY < 8) return lens.entries[0];
  let best = 0;
  for (let i = 1; i < lens.entries.length; i++) if (distanceFromMiddle(i) < distanceFromMiddle(best)) best = i;
  return lens.entries[best];
}

// in every frame while the reader scrolls: the entry in the middle is the card. The page never
// moves by itself here, so the lens can never fight the reader's own scrolling (PTL-2).
document.addEventListener("scroll", () => {
  if (!lensActive() || lens.frame) return;
  lens.frame = requestAnimationFrame(() => {
    lens.frame = 0;
    if (lensActive()) setLensFocus(entryAtMiddle()); // the timeline may be gone: a publication opened
  });
}, { passive: true });
// the reader scrolls on: the keyboard's card is not held any longer
for (const type of ["wheel", "touchstart", "pointerdown"]) document.addEventListener(type, () => { lens.hold = null; }, { passive: true });
document.addEventListener("keydown", (ev) => { if (ev.key !== "Tab") lens.hold = null; });

// keyboard: the entry with the focus is the card and glides into view. Not on a press with mouse
// or finger: the entry would slide away before it is released, and the tap would open nothing (PTL-4).
document.addEventListener("focusin", (ev) => {
  const entry = ev.target.closest?.(".tl-entry");
  if (!entry || !lensActive() || !lens.entries.includes(entry) || !entry.matches(":focus-visible")) return;
  lens.hold = entry;
  lens.holdUntil = performance.now() + 1500; // a glide never takes longer
  // then the entry in the middle is the card again, also when nothing scrolls any more
  setTimeout(() => { if (lens.hold === entry) { lens.hold = null; if (lensActive()) setLensFocus(entryAtMiddle()); } }, 1500);
  setLensFocus(entry);
  // after the browser's own scrolling to the focus, which would cancel the glide (Firefox)
  requestAnimationFrame(() => requestAnimationFrame(() => { if (lensActive()) glideToMiddle(entry); }));
});

// a narrower or wider screen (turning the phone, resizing the window): the text flows anew, the
// same entry stays the card and comes back to the middle. Only the height changed (also the
// address bar of a phone browser while scrolling): the entry now in the middle is the card.
window.addEventListener("resize", () => {
  if (!lensActive()) return;
  const card = lens.focus, wider = innerWidth !== lens.width;
  lens.width = innerWidth;
  measureLens();
  if (wider && card && scrollY >= 8) {
    glideToMiddle(card, "auto");
    setLensFocus(card);
  } else setLensFocus(entryAtMiddle());
});

/** "← Ältere / Neuere Veröffentlichung →" at the end of a publication (TL-2). */
function renderPager(id) {
  const i = state.pubs.findIndex((p) => p.id === id);
  if (i < 0) return null;
  const older = state.pubs[i + 1], newer = state.pubs[i - 1];
  const link = (p, cls, label) => p ? `<a class="${cls}" href="${pubHref(p)}">
      <span class="pager-dir">${label}</span><span class="pager-title">${esc(p.title)}</span></a>` : "";
  return el(`<nav class="pub-pager" aria-label="Weiterlesen">
    ${link(older, "older", "← Ältere Veröffentlichung")}${link(newer, "newer", "Neuere Veröffentlichung →")}
  </nav>`);
}

// ---------------------------------------------------------------- publication

async function openPublication(teil, year, number, refresh = false) {
  const id = `${teil}/${year}/${number}`;
  state.currentId = id;
  state.lastRead = id;
  const main = $("#main");
  main.innerHTML = "";
  showContents(null);
  main.appendChild($("#tpl-loading").content.cloneNode(true));
  main.scrollTop = 0;
  window.scrollTo(0, 0); // small screens scroll the whole page
  try {
    const item = state.pubs.find((p) => p.id === id);
    if (STATIC && item && !item.analyzed && !item.failed) {
      main.innerHTML = `<div class="error-box"><strong>Diese Veröffentlichung ist noch nicht ausgewertet.</strong><br>Die Daten werden einmal täglich am Abend aktualisiert – bitte morgen noch einmal versuchen. Den amtlichen Text finden Sie schon jetzt auf <span class="domain">recht.bund.de</span>.</div>`;
      const pager = renderPager(id);
      if (pager) main.appendChild(pager);
      return;
    }
    const data = await getJSON(api.publication(teil, year, number, refresh));
    if (state.currentId !== id) return; // user navigated away meanwhile
    if (data.error) throw new Error(data.error);
    state.current = data;
    try {
      renderPublication();
    } catch (e) {
      console.error(e);
      main.innerHTML = `<div class="error-box"><strong>Diese Seite konnte wegen eines Fehlers in <span class="name">bundesdiff</span> nicht angezeigt werden.</strong><br>Bitte versuchen Sie es später noch einmal. Den amtlichen Text finden Sie auf <span class="domain">recht.bund.de</span>.</div>`;
    }
  } catch (e) {
    if (state.currentId !== id) return;
    main.innerHTML = `<div class="error-box"><strong>Diese Veröffentlichung konnte nicht ausgewertet werden.</strong><br>${esc(e.message)}</div>`;
    const pager = renderPager(id);
    if (pager) main.appendChild(pager);
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

/** The same as markup: the abbreviation is never hyphenated ("(In-/VorG)", "(32. BIm-/SchV)"). */
function lawLabelHTML(a) {
  const law = a.law;
  if (!law) return esc(a.lawName || a.heading);
  const short = law.shortName && law.shortName !== law.name ? law.shortName : law.name;
  return law.abbreviation ? `${esc(short)} <span class="abbr">(${esc(law.abbreviation)})</span>` : esc(short);
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
  showContents(amendments.length > 1 ? renderContents(articles) : null);
  main.appendChild(el(`
    <section class="pub-header">
      <div class="fundstelle" title="So wird diese Veröffentlichung zitiert">${esc(keepDate(pub.fundstelle || `BGBl. ${pub.year} I Nr. ${pub.number}`))}</div>
      <h1 tabindex="-1">${esc(pub.title)}</h1>
      <div class="date">
        ${pub.typ ? `<span class="typ typ-${esc(pub.typ.toLowerCase())}">${esc(pub.typ)}</span>${typeHint ? ` – ${esc(typeHint)}` : ""}` : ""}
      </div>

      <dl class="glance">
        <div>
          <dt>Was ändert sich?</dt>
          <dd>${amendments.length
            ? `<ul class="glance-laws">${articles.map((a, i) => a.kind === "amendment" ? `
                <li><a href="#" data-jump="art-${i}">${lawLabelHTML(a)}</a>
                  <span class="muted count">– ${(a.pars || []).length
                    ? plural(a.pars.length, "Vorschrift", "Vorschriften")
                    : "nur im Wortlaut"}</span></li>` : "").join("")}</ul>`
            : `Keine Änderungen an bestehenden Gesetzen erkannt – zum Beispiel, weil es ein ganz neues Gesetz oder eine Bekanntmachung ist. Den Text finden Sie unten.`}</dd>
        </div>
        ${inForce.length ? `<div><dt>Ab wann gilt das?</dt><dd>${inForce.map((a) => esc(withoutSignatures(a.text))).join("<br>")}</dd></div>` : ""}
        <div><dt>Von wem?</dt><dd>${esc(pub.initiant || "–")}, ${esc(enacted)}${pub.issued ? `, veröffentlicht ${relativeDay(pub.issued) ? `${relativeDay(pub.issued)} (${esc(fullDate(pub.issued))})` : `am ${esc(fullDate(pub.issued))}`}` : ""}</dd></div>
      </dl>

      ${amendments.length ? `<div class="summary">
        ${Object.entries(counts).filter(([, n]) => n).map(([s, n]) => `<span class="badge ${s}" title="${esc(STATUS[s].title)}">${plural(n, "Änderung", "Änderungen")}: ${esc(STATUS[s].label)}</span>`).join("")}
        <button class="linklike" data-help="status">Was bedeutet das?</button>
      </div>` : ""}
      <div class="links">
        <a href="${esc(pub.pdf)}" target="_blank" rel="noopener">Amtliches PDF öffnen</a>
        <a href="${esc(pub.link)}" target="_blank" rel="noopener">Auf <span class="domain">recht.bund.de</span> ansehen</a>
        ${STATIC ? "" : `<button class="linklike" data-action="refresh" title="Die Auswertung mit den aktuellsten Daten wiederholen">Neu auswerten</button>`}
      </div>
    </section>`));

  if (amendments.some((a) => (a.pars || []).length)) main.appendChild(renderReadingSettings());

  articles.forEach((a, i) => {
    if (a.kind === "amendment") main.appendChild(renderAmendment(a, i));
    else if (!isInForce(a)) main.appendChild(renderOther(a, i));
  });
  if (!amendments.length) main.appendChild(el(`<button class="to-top" data-action="top">↑ Zum Anfang der Veröffentlichung</button>`));
  const pager = renderPager(pub.id);
  if (pager) main.appendChild(pager);
  updateStickyHeight();
  followReader();
}

/** How the comparison is shown – only where there is one to show. */
function renderReadingSettings() {
  const split = state.view === "split";
  return el(`
    <div class="reading-settings">
      <div class="segmented" role="group" aria-label="Darstellung der Änderungen">
        <button data-view="split" class="${split ? "active" : ""}" aria-pressed="${split}" title="Alter Text links, neuer Text rechts">Nebeneinander</button>
        <button data-view="inline" class="${split ? "" : "active"}" aria-pressed="${!split}" title="Ein einziger Text, Änderungen markiert">Im Text markiert</button>
      </div>
      <label class="toggle" title="Abschnitte ohne Änderung einklappen"><input type="checkbox" id="only-changes" ${state.onlyChanges ? "checked" : ""}> Unverändertes ausblenden</label>
      <div class="color-legend">
        <span><del class="sample">durchgestrichen</del> fällt weg</span>
        <span><ins class="sample">unterstrichen</ins> kommt neu hinzu</span>
      </div>
    </div>`);
}

function articleLabel(a) {
  return `${a.number ? `Artikel ${a.number} · ` : ""}${lawLabel(a)}`;
}

/** Contents bar for publications that change several laws: which law is on screen, and a list to jump. */
function renderContents(articles) {
  const items = articles.map((a, i) => a.kind !== "amendment" ? "" : `
    <li><a href="#art-${i}" data-jump="art-${i}">${esc(articleLabel(a))}
      <span class="muted count">– ${(a.pars || []).length ? plural(a.pars.length, "Vorschrift", "Vorschriften") : "nur im Wortlaut"}</span></a></li>`);
  const first = articles.find((a) => a.kind === "amendment");
  return el(`
    <nav class="toc-bar" aria-label="${words().contents}">
      <div class="toc-row">
        <span class="toc-label">Sie lesen:</span>
        <span class="toc-current">${esc(articleLabel(first))}</span>
        <button class="toc-toggle" aria-expanded="false" aria-controls="toc-list">Inhalt<span aria-hidden="true"> ▾</span></button>
      </div>
      <ol class="toc-list" id="toc-list" hidden>${items.join("")}</ol>
    </nav>`);
}

/** The contents bar sits right above the text column, outside the scrolling area. */
function showContents(bar) {
  $(".toc-bar")?.remove();
  if (bar) $("#main").before(bar);
}

function toggleContents(open) {
  const button = $(".toc-toggle");
  if (!button) return;
  button.setAttribute("aria-expanded", open);
  $("#toc-list").hidden = !open;
}

/** Height of the bars that stay on top while scrolling, so jump targets are not hidden behind them. */
function updateStickyHeight() {
  const bars = [$(".topbar"), $(".toc-bar")]
    .filter((b) => b && getComputedStyle(b).position === "sticky");
  const height = bars.reduce((sum, b) => sum + b.getBoundingClientRect().height, 0);
  document.documentElement.style.setProperty("--sticky-h", `${Math.round(height)}px`);
}

/** The contents bar names the law currently on screen (NAV-8). */
function followReader() {
  const bar = $(".toc-bar");
  if (!bar) return;
  const line = bar.getBoundingClientRect().bottom + 40;
  const laws = $$("#toc-list a").map((a) => document.getElementById(a.dataset.jump)).filter(Boolean);
  const current = laws.filter((art) => art.getBoundingClientRect().top <= line).pop() || laws[0];
  if (!current) return;
  const article = state.current.articles[+current.id.slice(4)];
  $(".toc-current", bar).textContent = articleLabel(article);
  $$("#toc-list a").forEach((a) => {
    if (a.dataset.jump === current.id) a.setAttribute("aria-current", "location");
    else a.removeAttribute("aria-current");
  });
}

let followPending = false;
document.addEventListener("scroll", () => {
  if (followPending) return;
  followPending = true;
  requestAnimationFrame(() => { followPending = false; followReader(); });
}, { capture: true, passive: true });
window.addEventListener("resize", updateStickyHeight);

/** Scroll to an element and give it the keyboard focus (headings get tabindex="-1"). */
function goTo(target) {
  target.scrollIntoView({ behavior: SCROLL(), block: "start" });
  target.focus({ preventScroll: true });
}

function renderOther(a, i) {
  return el(`
    <article class="article" id="art-${i}">
      <details class="other">
        <summary>
          ${a.number ? `<div class="art-no">Artikel ${esc(a.number)}</div>` : ""}
          <h2>${esc(a.heading || words().text)}</h2>
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
        <div class="art-no">${a.number ? `Artikel ${esc(a.number)} · ` : ""}${words().changed}</div>
        <h2 tabindex="-1">${lawLabelHTML(a)}</h2>
        ${law ? `<div class="law-line">
          ${law.shortName && law.name !== law.shortName ? `<span>${esc(law.name)}</span>` : ""}
          ${isDraft() ? "" : `<span class="badge source" title="Woher der aktuelle Gesetzestext stammt">aktueller Text: ${law.source === "gii" ? `<span class="domain">gesetze-im-internet.de</span>` : "Rechtsinformationsportal (NeuRIS)"}, Stand ${esc(formatDate(law.version))}</span>`}
          <a href="${esc(law.url)}" target="_blank" rel="noopener">Ganzes Gesetz ansehen</a>
        </div>` : ""}
        ${law && isDraft() ? `<p class="compared">Verglichen mit der Fassung vom\u00a0${esc(formatDate(law.version))}.${law.newerThanDraft ? " Das Gesetz wurde nach dem Entwurf noch geändert. Einzelne Änderungen passen deshalb vielleicht nicht mehr." : ""}</p>` : ""}
      </header>
      ${a.error ? `<div class="error">${esc(a.error)} Die Änderungen werden deshalb nur im Wortlaut angezeigt.</div>` : ""}
      <div class="tabs" role="tablist">
        <button role="tab" id="tab-${i}-synopse" aria-controls="body-${i}-synopse" aria-selected="true" data-tab="synopse" class="active" title="Gegenüberstellung von bisherigem und neuem Text">${words().compareTab}<span class="count">${(a.pars || []).length}</span></button>
        <button role="tab" id="tab-${i}-befehle" aria-controls="body-${i}-befehle" aria-selected="false" tabindex="-1" data-tab="befehle" title="${words().wordingTitle}">${words().wordingTab}<span class="count">${(a.instructions || []).length}</span></button>
      </div>
      <div class="tab-body" role="tabpanel" id="body-${i}-synopse" aria-labelledby="tab-${i}-synopse" data-body="synopse"></div>
      <div class="tab-body" role="tabpanel" id="body-${i}-befehle" aria-labelledby="tab-${i}-befehle" data-body="befehle" hidden></div>
    </article>`);

  const syn = $('[data-body="synopse"]', card);
  if (a.pars && a.pars.length) a.pars.forEach((p) => syn.appendChild(renderPar(p, a)));
  else syn.appendChild(el(`<p class="no-pars">${words().noPars}</p>`));
  const cmd = $('[data-body="befehle"]', card);
  cmd.appendChild(el(`<p class="tab-intro">${words().wordingIntro}</p>`));
  cmd.appendChild(renderInstructions(a.instructions || []));
  card.appendChild(el(`<a class="to-start" href="#" data-action="top">${words().top}</a>`));
  return card;
}

function renderInstructions(list) {
  const ol = el(`<ol class="instructions"></ol>`);
  for (const ins of list) {
    const st = statusOf(ins.status);
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
      ${p.source ? `<div class="par-note">Der bisherige Text stammt aus ${oldSource(p.source)}. Sie kann auch Änderungen enthalten, die nicht aus dieser Veröffentlichung stammen.</div>` : ""}
    </section>`);
  $(".how", section).addEventListener("click", () => showHow(p, article));
  section.appendChild(renderDiff(p.rows));
  return section;
}

// screen readers skip punctuation: a change of only "," or ":" would be read as an empty "neu" (A11Y-7)
const MARK_NAMES = {
  ":": "Doppelpunkt", ",": "Komma", ".": "Punkt", ";": "Semikolon", "-": "Bindestrich", "–": "Gedankenstrich",
  "(": "Klammer auf", ")": "Klammer zu", "„": "Anführungszeichen", "“": "Anführungszeichen", "\"": "Anführungszeichen",
  "?": "Fragezeichen", "!": "Ausrufezeichen", "/": "Schrägstrich", "§": "Paragraf",
};

/** The punctuation of a changed piece in words, or "" if it has a word or number of its own. */
function markNames(s) {
  if (!s) return "";
  if (!s.trim()) return "Leerzeichen";
  if (/[\p{L}\p{N}]/u.test(s)) return "";
  const names = [...s].filter((c) => c.trim()).map((c) => MARK_NAMES[c] || "Satzzeichen");
  return names.join(" ");
}

function segHTML(segs) {
  if (!segs) return "";
  return segs.map((sg) => {
    const text = esc(sg.s).replace(esc(UNKNOWN), `<span class="unknown">bisheriger Text nicht ermittelbar</span>`);
    if (sg.t !== "del" && sg.t !== "ins") return text;
    const say = markNames(sg.s);
    return `<${sg.t}${say ? ` data-say="${esc(say)}"` : ""}>${text}</${sg.t}>`;
  }).join("");
}

function renderDiff(rows) {
  const split = state.view === "split";
  const table = el(`<table class="diff ${split ? "split" : "inline"}"></table>`);
  // Layout like a code review: a narrow gutter with −/+ before each text column
  table.innerHTML = split
    ? `<colgroup><col class="gutter"><col><col class="gutter"><col></colgroup>
       <thead class="diff-head"><tr><th colspan="2">${words().before}</th><th colspan="2">${words().after}</th></tr></thead>`
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

// ---------------------------------------------------------------- bills (spec 016)

/** A bill (Gesetzentwurf) is on screen: the comparison then speaks of the bill, not of a publication. */
const isDraft = () => Boolean(state.current?.draft);

// What the comparison is called for a publication and for a bill (ENT-7)
const WORDS = {
  publication: {
    before: "Vorher · bisheriger Text", after: "Nachher · neuer Text",
    compareTab: "Vorher / Nachher", wordingTab: "Wortlaut im Gesetzblatt", wordingTitle: "So steht die Änderung wörtlich im Gesetzblatt",
    wordingIntro: "Gesetzesänderungen werden als Anweisungen formuliert („… wird durch … ersetzt“). Hier steht jede Anweisung im Originalwortlaut – und ob <span class=\"name\">bundesdiff</span> sie anwenden konnte.",
    noPars: "Für dieses Gesetz konnte keine Gegenüberstellung erzeugt werden. Unter „Wortlaut im Gesetzblatt“ sehen Sie die Änderungen so, wie sie veröffentlicht wurden.",
    top: "↑ Zum Anfang der Veröffentlichung", contents: "Inhalt dieser Veröffentlichung", text: "Text der Veröffentlichung",
    changed: "Geändert wird",
  },
  draft: {
    before: "Geltender Text", after: "Text nach dem Entwurf",
    compareTab: "Geltend / Entwurf", wordingTab: "Wortlaut im Entwurf", wordingTitle: "So steht die Änderung wörtlich im Entwurf",
    wordingIntro: "Gesetzesänderungen werden als Anweisungen formuliert („… wird durch … ersetzt“). Hier steht jede Anweisung im Originalwortlaut des Entwurfs – und ob <span class=\"name\">bundesdiff</span> sie anwenden konnte.",
    noPars: "Für dieses Gesetz konnte kein Vergleich erzeugt werden. Unter „Wortlaut im Entwurf“ sehen Sie die Änderungen so, wie sie im Entwurf stehen.",
    top: "↑ Zum Anfang des Entwurfs", contents: "Inhalt dieses Entwurfs", text: "Text des Entwurfs",
    changed: "Soll geändert werden",
  },
};
const words = () => WORDS[isDraft() ? "draft" : "publication"];

// For a bill nothing is calculated backwards (ENT-8), and "das Gesetz im Internet" is the law in force
const DRAFT_STATUS = {
  applied: {
    label: "im Vergleich gezeigt",
    title: "bundesdiff hat diese Änderung in den geltenden Gesetzestext eingearbeitet.",
  },
  failed: {
    label: "nicht anwendbar",
    title: "Diese Änderung passte nicht zum geltenden Gesetzestext und konnte nicht dargestellt werden.",
  },
  unsupported: STATUS.unsupported,
};
const statusOf = (s) => (isDraft() ? DRAFT_STATUS[s] : STATUS[s]) || STATUS.unsupported;

const billHref = (b) => `#/entwurf/${b.wp}/${b.number}`;
/** 21/6588 → …/btd/21/065/2106588.pdf: the address of a Drucksache follows from its number. */
const billPdf = (wp, number) => `https://dserver.bundestag.de/btd/${wp}/${String(number).padStart(5, "0").slice(0, 3)}/${wp}${String(number).padStart(5, "0")}.pdf`;
const billPdfLink = (wp, number) => `<a href="${esc(billPdf(wp, number))}" target="_blank" rel="noopener">Drucksache beim Deutschen Bundestag (PDF, externe Seite)</a>`;
/** "Gesetzentwurf der Bundesregierung" */
const billKind = (b) => [b.kind || "Gesetzentwurf", b.author].filter(Boolean).join(" ");

function startPage(id) {
  state.currentId = id;
  state.current = null;
  showContents(null);
  const main = $("#main");
  main.innerHTML = "";
  main.scrollTop = 0;
  window.scrollTo(0, 0);
  return main;
}

/** The list of bills (ENT-2, ENT-3). */
async function openBills() {
  const main = startPage("entwuerfe");
  const page = el(`
    <section class="welcome bills">
      <h1 tabindex="-1">Gesetzentwürfe</h1>
      <p class="lead">Ein Gesetzentwurf ist ein Vorschlag für ein neues Gesetz. Er gilt noch nicht. Der Bundestag kann ihn ändern oder ablehnen.</p>
      <p><span class="name">bundesdiff</span> zeigt, was ein Entwurf an den geltenden Gesetzen ändern würde: den geltenden Text und den Text nach dem Entwurf nebeneinander. Bisher ist das ein Versuch mit einem einzigen Entwurf.</p>
      <div class="bills-body"><p class="loading-line" role="status">Die Liste wird geladen …</p></div>
    </section>`);
  main.appendChild(page);
  const body = $(".bills-body", page);
  let bills;
  try {
    bills = state.bills || (state.bills = await getJSON(api.bills()));
  } catch (e) {
    if (state.currentId !== "entwuerfe") return;
    body.innerHTML = `<div class="error-box"><strong>Die Liste der Gesetzentwürfe konnte nicht geladen werden.</strong><br>Bitte laden Sie die Seite später noch einmal.</div>`;
    return;
  }
  if (state.currentId !== "entwuerfe") return;
  body.innerHTML = bills.length ? `
    <p class="list-count">${plural(bills.length, "Gesetzentwurf", "Gesetzentwürfe")}</p>
    <ol class="bill-list">${bills.map((b) => `
      <li>
        <p class="bill-meta">Drucksache\u00a0${esc(b.wp)}/${esc(b.number)}${b.date ? `\u00a0· ${esc(formatDate(b.date))}` : ""}${b.analyzed ? `\u00a0· ${esc(billKind(b))}` : ""}</p>
        <a class="bill-title" href="${billHref(b)}">${esc(b.title || `Drucksache ${b.wp}/${b.number}`)}</a>
        ${b.analyzed
          ? ((b.laws || []).length ? `<p class="bill-laws">Würde ändern: ${b.laws.map((l) => esc(l.name)).join(" · ")}</p>` : "")
          : `<p class="bill-laws">Dieser Entwurf ist noch nicht ausgewertet.</p>`}
      </li>`).join("")}
    </ol>` : `<p class="tl-empty">Zurzeit zeigt <span class="name">bundesdiff</span> keinen Gesetzentwurf.</p>`;
}

/** The page of one bill. */
async function openBill(wp, number) {
  const id = `entwurf/${wp}/${number}`;
  const main = startPage(id);
  main.appendChild(el(`<div class="loading"><div class="spinner" aria-hidden="true"></div><p role="status">Der Gesetzentwurf wird geladen …</p></div>`));
  let data;
  try {
    data = await getJSON(api.bill(wp, number));
    if (data.error || !data.draft) throw new Error(data.error || "keine Daten");
  } catch (e) {
    const problem = await billProblem(wp, number);
    if (state.currentId === id) main.innerHTML = problem;
    return;
  }
  if (state.currentId !== id) return;
  state.current = data;
  state.info = null;
  state.infoParts = null;
  try {
    renderDraft();
  } catch (e) {
    console.error(e);
    main.innerHTML = `<div class="error-box"><strong>Diese Seite konnte wegen eines Fehlers in <span class="name">bundesdiff</span> nicht angezeigt werden.</strong><br>Bitte versuchen Sie es später noch einmal. Den Entwurf selbst finden Sie hier: ${billPdfLink(wp, number)}</div>`;
  }
}

/** Why a bill cannot be shown – what happened, and what the reader can do (ENT-15). */
async function billProblem(wp, number) {
  let listed = null; // not known while the list cannot be loaded either
  try {
    state.bills = state.bills || await getJSON(api.bills());
    listed = state.bills.some((b) => +b.wp === wp && +b.number === number);
  } catch { /* the bill itself may still be there */ }
  // an address that is none of the bills shown here (mistyped, or the bill was taken off the list)
  if (listed === false) return `<div class="error-box"><strong>Diesen Gesetzentwurf zeigt <span class="name">bundesdiff</span> nicht.</strong><br>Bisher sind hier nur einzelne Gesetzentwürfe zu sehen. <a href="${BILLS_ROUTE}">Zur Liste der Gesetzentwürfe</a></div>`;
  return `<div class="error-box"><strong>Dieser Gesetzentwurf kann gerade nicht angezeigt werden.</strong><br>Bitte versuchen Sie es später noch einmal. Den Entwurf selbst finden Sie hier: ${billPdfLink(wp, number)}</div>`;
}

function renderDraft() {
  const { draft, articles, counts } = state.current;
  const main = $("#main");
  const amendments = articles.filter((a) => a.kind === "amendment");
  const inForce = articles.filter((a) => a.kind !== "amendment" && isInForce(a));
  // ENT-13: a bill has placeholders instead of dates ("am … [einsetzen: Datum …]")
  const undated = inForce.some((a) => /\[einsetzen|…|\.\.\./.test(a.text || ""));
  const open = new Set($$(".bill-info details[open]").map((d) => d.dataset.info)); // kept when a reading setting changes

  main.innerHTML = "";
  showContents(amendments.length > 1 ? renderContents(articles) : null);
  main.appendChild(el(`
    <section class="pub-header bill-header">
      <div class="fundstelle" title="So wird dieser Entwurf zitiert">Drucksache ${esc(draft.wp)}/${esc(draft.number)}</div>
      <h1 tabindex="-1">${esc(draft.title)}</h1>
      <div class="date"><span class="typ typ-entwurf">Entwurf</span> – ${esc(billKind(draft))}${draft.date ? ` vom ${esc(formatDate(draft.date))}` : ""}</div>
      <p class="draft-notice"><strong>Dies ist ein Entwurf.</strong> Er gilt nicht. Der Bundestag kann ihn noch ändern oder ablehnen. <span class="name">bundesdiff</span> zeigt den Stand${draft.date ? ` vom ${esc(formatDate(draft.date))}` : " der Drucksache"} und verfolgt nicht, was danach mit dem Entwurf geschehen ist.</p>

      <dl class="glance">
        <div>
          <dt>Was würde sich ändern?</dt>
          <dd>${amendments.length
            ? `<ul class="glance-laws">${articles.map((a, i) => a.kind === "amendment" ? `
                <li><a href="#" data-jump="art-${i}">${lawLabelHTML(a)}</a>
                  <span class="muted count">– ${(a.pars || []).length
                    ? plural(a.pars.length, "Vorschrift", "Vorschriften")
                    : "nur im Wortlaut"}</span></li>` : "").join("")}</ul>`
            : `Keine Änderungen an bestehenden Gesetzen erkannt – zum Beispiel, weil der Entwurf ein ganz neues Gesetz vorschlägt. Den Text finden Sie unten.`}</dd>
        </div>
        ${inForce.length ? `<div><dt>Ab wann würde das gelten?</dt><dd>${undated
          ? "Im Entwurf steht noch kein Datum. Es wird erst eingesetzt, wenn das Gesetz beschlossen und verkündet ist."
          : inForce.map((a) => esc(withoutSignatures(a.text))).join("<br>")}</dd></div>` : ""}
        <div><dt>Von wem?</dt><dd>${esc(billKind(draft))}${draft.date ? ` vom ${esc(fullDate(draft.date))}` : ""}</dd></div>
      </dl>

      ${counts && counts.total ? `<p class="shown-count">${esc(counts.shown)} von ${plural(counts.total, "Änderung wird", "Änderungen werden")} im Vergleich gezeigt.${counts.shown < counts.total ? " Die übrigen finden Sie bei jedem Gesetz unter „Wortlaut im Entwurf“." : ""}</p>` : ""}
      <div class="links">${billPdfLink(draft.wp, draft.number)}</div>
      <p class="binding">Maßgeblich ist allein die Drucksache des Deutschen Bundestages.</p>
    </section>`));

  const info = renderInfoList(open);
  if (info) main.appendChild(info);
  if (amendments.some((a) => (a.pars || []).length)) main.appendChild(renderReadingSettings());
  articles.forEach((a, i) => main.appendChild(a.kind === "amendment" ? renderAmendment(a, i) : renderOther(a, i)));
  if (!amendments.length) main.appendChild(el(`<button class="to-top" data-action="top">${words().top}</button>`));
  updateStickyHeight();
  followReader();
}

/** "Allgemeine Informationen" (ENT-12): Vorblatt and Begründung, apart from the comparison, closed at first.
 *  `open`: the parts that were open before the page was drawn anew. */
function renderInfoList(open = new Set()) {
  const { draft, info } = state.current;
  if (!info || !info.length) return null;
  const section = el(`
    <section class="bill-info" aria-labelledby="bill-info-title">
      <h2 id="bill-info-title">Allgemeine Informationen</h2>
      <p class="info-note">Zu jedem Gesetzentwurf gehören eine Zusammenfassung und eine Begründung. Sie stehen hier im Wortlaut: Text ${esc(draft.author || "der Verfasser des Entwurfs")}, nicht von <span class="name">bundesdiff</span>. Tabellen und Fußnoten fehlen hier; vollständig stehen sie in der Drucksache.</p>
      ${info.map((p) => `<details data-info="${esc(p.id)}"><summary><span class="info-title">${esc(p.title)}</span></summary><div class="info-body"></div></details>`).join("")}
    </section>`);
  for (const part of $$("details", section)) {
    if (open.has(part.dataset.info)) {
      part.open = true;
      // at once, not after the next request: the reader's place on the page must not move (A11Y-8)
      if (state.infoParts) showInfo(part, state.infoParts);
    }
    part.addEventListener("toggle", () => { if (part.open) fillInfo(part); });
  }
  return section;
}

const infoMissing = (draft) => `<p class="info-missing">Dieser Text konnte nicht geladen werden. Sie finden ihn hier: ${billPdfLink(draft.wp, draft.number)}</p>`;

/** The text of one part, loaded when the reader opens it: together the parts are larger than the comparison. */
async function fillInfo(part) {
  const body = $(".info-body", part);
  if (body.dataset.filled) return;
  const { draft } = state.current;
  const id = state.currentId;
  if (!state.infoParts) {
    body.innerHTML = `<p class="loading-line" role="status">Der Text wird geladen …</p>`;
    try {
      state.info = state.info || getJSON(api.billInfo(draft.wp, draft.number));
      const data = await state.info;
      if (state.currentId !== id) return; // the reader went on to another page meanwhile
      if (!data || !Array.isArray(data.parts)) throw new Error("keine Daten");
      state.infoParts = data.parts;
    } catch (e) {
      if (state.currentId !== id) return;
      state.info = null; // opening the part again tries again
      body.innerHTML = infoMissing(draft);
      return;
    }
  }
  showInfo(part, state.infoParts);
}

function showInfo(part, parts) {
  const body = $(".info-body", part);
  const found = parts.find((p) => p.id === part.dataset.info);
  if (!found || !Array.isArray(found.sections)) {
    body.innerHTML = infoMissing(state.current.draft);
    return;
  }
  // headings below "Allgemeine Informationen" (h2): the highest rank of the part is h3
  const top = Math.min(...found.sections.filter((s) => s.heading).map((s) => s.level), 6);
  // escWithDomains: an address in the text ("https://doi.org/…") is never hyphenated (A11Y-5)
  body.innerHTML = found.sections.map((s) => {
    const h = Math.min(3 + Math.max(0, s.level - top), 6);
    return `${s.heading ? `<h${h}>${escWithDomains(s.heading)}</h${h}>` : ""}${(s.paragraphs || []).map((p) => `<p>${escWithDomains(p)}</p>`).join("")}`;
  }).join("");
  body.dataset.filled = "1";
}

// ---------------------------------------------------------------- explanations

/** The button or link the reader last pressed: windows give the focus back to it when they close. */
let lastPressed = null;
document.addEventListener("click", (ev) => { lastPressed = ev.target.closest?.("button, a") || null; }, true);
const shown = (e) => e && e.isConnected && e.getClientRects().length > 0;

function returnFocus(to, fallbacks = []) {
  const target = [to, ...fallbacks].find(shown);
  target?.focus();
}

function openDialog(title, html) {
  const dlg = $("#dialog");
  closeMenu(true);
  dlg.opener = lastPressed && !dlg.contains(lastPressed) ? lastPressed : document.activeElement;
  $("#dialog-title").innerHTML = esc(title).replace(/\bbundesdiff\b/g, '<span class="name">bundesdiff</span>');
  $("#dialog-body").innerHTML = html;
  dlg.showModal();
  $("#dialog-body").scrollTop = 0;
}

/** Explain, for one paragraph, how its before/after texts were obtained. */
function showHow(p, article) {
  const law = article.law || {};
  // fixed markup, not data: inserted without esc()
  const src = law.source === "gii" ? `<span class="domain">gesetze-im-internet.de</span>` : "dem Rechtsinformationsportal des Bundes (NeuRIS)";
  const parLabel = p.title.split(" ").slice(0, 2).join(" "); // "§ 38"
  const related = (article.instructions || []).filter((i) => i.location === parLabel || (i.location || "").startsWith(parLabel + " "));
  let how;
  if (isDraft()) {
    how = `<p>Der geltende Text von <strong>${esc(p.title)}</strong> stammt von ${src} (Stand ${esc(formatDate(law.version))}).
      Er bildet die linke Spalte „Geltender Text“.</p>
      <p>Die rechte Spalte „Text nach dem Entwurf“ hat <span class="name">bundesdiff</span> <strong>selbst berechnet</strong>, indem es die Anweisungen aus dem Entwurf auf diesen Text angewendet hat.</p>`;
  } else if (p.state === "post") {
    how = `<p>Der aktuelle Text von <strong>${esc(p.title)}</strong> auf ${src} (Stand ${esc(formatDate(law.version))})
      <strong>enthält diese Änderung bereits</strong>. Er bildet deshalb die rechte Spalte „Nachher“.</p>
      <p>Die linke Spalte „Vorher“ wurde <strong>zurückgerechnet</strong>: Die Anweisungen aus dem Gesetzblatt wurden rückwärts
      angewendet (aus „B ersetzt A“ wird wieder A).
      ${p.source
        ? `Wo das nicht möglich ist – etwa wenn ein ganzer Absatz neu gefasst wurde –, stammt der alte Wortlaut aus
           ${oldSource(p.source)}.`
        : "Dafür war keine ältere Fassung nötig."}</p>`;
  } else {
    how = `<p>Der aktuelle Text von <strong>${esc(p.title)}</strong> auf ${src} (Stand ${esc(formatDate(law.version))})
      <strong>enthält diese Änderung noch nicht</strong> – oft, weil sie erst später in Kraft tritt oder die Datenbank noch nicht aktualisiert wurde.
      Er bildet deshalb die linke Spalte „Vorher“.</p>
      <p>Die rechte Spalte „Nachher“ hat <span class="name">bundesdiff</span> <strong>selbst berechnet</strong>, indem es die Anweisungen aus dem Gesetzblatt auf diesen Text angewendet hat.</p>`;
  }
  const list = related.length
    ? `<h3>Angewendete Anweisungen</h3><ol class="how-list">${related.map((i) =>
        `<li>${highlightQuotes(i.raw)} <span class="badge ${esc(i.status)}">${esc(statusOf(i.status).label)}</span></li>`).join("")}</ol>`
    : "";
  openDialog(`Wie wurde ${parLabel} ermittelt?`, how + list +
    (isDraft() ? `<p class="muted">Ohne Gewähr. Maßgeblich ist allein die Drucksache des Deutschen Bundestages.</p>`
      : `<p class="muted">Ohne Gewähr – rechtsverbindlich ist allein das amtliche Bundesgesetzblatt.</p>`));
}

function showHelp(section) {
  openDialog("So funktioniert bundesdiff", $("#tpl-help").innerHTML);
  if (section) document.getElementById(`help-${section}`)?.scrollIntoView();
}

// ---------------------------------------------------------------- events & routing

function route() {
  const m = PUBLICATION_ROUTE.exec(location.hash);
  const about = location.hash === ABOUT_ROUTE;
  const bill = BILL_ROUTE.exec(location.hash);
  const bills = location.hash === BILLS_ROUTE;
  const other = about || bill || bills;
  markCurrentNav(m ? null : about ? "about" : bill || bills ? "bills" : "list"); // ENT-1
  $("#fab-back").hidden = !(m || other); // PTL-11: back to the timeline, as the reader left it
  if (!m && !other) rememberTimeline(location.hash.startsWith("#/?") ? location.hash : "#/");
  if (m || other) { lens.entries = []; watchTimeline.disconnect(); }
  if (m) {
    openPublication(m[1], m[2], decodeURIComponent(m[3]));
    return;
  }
  if (bill) { openBill(+bill[1], +bill[2]); return; }
  if (bills) { openBills(); return; }
  state.currentId = null;
  state.current = null;
  showContents(null);
  if (about) $("#main").innerHTML = $("#tpl-about").innerHTML;
  else renderTimeline();
  if (about || !showLastRead()) window.scrollTo(0, 0);
}

function markCurrentNav(which) {
  $$("[data-nav]").forEach((a) => {
    if (a.dataset.nav === which) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
}

/** Draws the publication anew after a reading setting changed. The reader stays where they were:
 * the control they used keeps the keyboard focus at the same place on the screen, and an article
 * switched to "Wortlaut im Gesetzblatt" stays on that tab (A11Y-8). */
function rerender() {
  if (!(state.current && $("#main .pub-header"))) return;
  const active = document.activeElement;
  const selector = active?.id ? `#${CSS.escape(active.id)}`
    : active?.dataset?.view ? `[data-view="${CSS.escape(active.dataset.view)}"]` : null;
  const top = selector ? active.getBoundingClientRect().top : null;
  const tabs = $$('#main .tabs [role="tab"][aria-selected="true"]:not([data-tab="synopse"])').map((b) => b.id);
  if (isDraft()) renderDraft(); else renderPublication();
  for (const id of tabs) {
    const tab = document.getElementById(id);
    if (tab) selectTab(tab);
  }
  const again = selector && $(selector);
  if (!again) return;
  again.focus({ preventScroll: true });
  window.scrollBy({ top: again.getBoundingClientRect().top - top, behavior: "instant" });
}

document.addEventListener("click", (ev) => {
  const t = ev.target;
  if (t.closest(".theme-switch")) { toggleTheme(); return; }
  const menuButton = t.closest("#fab-menu, #nav-menu");
  if (menuButton) { openMenu(menuButton); return; }
  if (t.closest('[data-action="skip"]')) { ev.preventDefault(); $("#main").focus(); return; }
  const order = t.closest("[data-order]");
  if (order) {
    const params = timelineParams();
    if (order.dataset.order === "upcoming") params.set("ansicht", "demnaechst"); else params.delete("ansicht");
    setTimelineParams(params);
    return;
  }
  const month = t.closest("[data-month]");
  if (month) { ev.preventDefault(); goTo(document.getElementById(month.dataset.month)); return; }
  if (t.closest("#search-open, #fab-search")) { openSearch(); return; }
  if (t.closest('[data-action="top"]')) {
    ev.preventDefault();
    const title = $("#main .pub-header h1");
    if (title) goTo(title);
    return;
  }
  const toc = t.closest(".toc-toggle");
  if (toc) { toggleContents(toc.getAttribute("aria-expanded") !== "true"); return; }
  if (!t.closest(".toc-bar")) toggleContents(false); // a click elsewhere closes the contents list
  const view = t.closest("[data-view]");
  if (view) {
    state.view = view.dataset.view; localSet("view", state.view); rerender(); return;
  }
  const help = t.closest("[data-help]");
  if (help) { ev.preventDefault(); showHelp(help.dataset.help); return; }
  if (t.closest("#dialog-close")) { $("#dialog").close(); return; }
  if (t.id === "dialog") { $("#dialog").close(); return; } // click on backdrop
  const tab = t.closest(".tabs button");
  if (tab) { selectTab(tab); return; }
  const jump = t.closest("[data-jump]");
  if (jump) {
    ev.preventDefault();
    toggleContents(false);
    const heading = $(`#${jump.dataset.jump} h2`);
    if (heading) goTo(heading);
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

function selectTab(tab) {
  const card = tab.closest(".article");
  $$(".tabs button", card).forEach((b) => {
    const on = b === tab;
    b.classList.toggle("active", on);
    b.setAttribute("aria-selected", on);
    b.tabIndex = on ? 0 : -1;
  });
  $$(".tab-body", card).forEach((b) => { b.hidden = b.dataset.body !== tab.dataset.tab; });
}

// arrow keys move between tabs (ARIA tabs pattern)
document.addEventListener("keydown", (ev) => {
  const tab = ev.target.closest?.(".tabs button");
  if (!tab || !["ArrowLeft", "ArrowRight"].includes(ev.key)) return;
  const tabs = $$("button", tab.parentElement);
  const next = tabs[(tabs.indexOf(tab) + (ev.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length];
  selectTab(next);
  next.focus();
});

document.addEventListener("change", (ev) => {
  if (ev.target.id === "type-filter") {
    const params = timelineParams();
    const typ = ev.target.value;
    if (typ) params.set("art", typ); else params.delete("art");
    params.delete("nur"); // the removed filter "nur Gesetzesänderungen"
    setTimelineParams(params, true);
    return;
  }
  if (ev.target.id !== "only-changes") return;
  state.onlyChanges = ev.target.checked; localSet("onlyChanges", state.onlyChanges ? "1" : "0"); rerender();
});

// Escape closes the contents list and returns to its button
document.addEventListener("keydown", (ev) => {
  if (ev.key !== "Escape" || $("#toc-list")?.hidden !== false) return;
  toggleContents(false);
  $(".toc-toggle").focus();
});
window.addEventListener("hashchange", route);

async function showDataDate() {
  if (!STATIC) return;
  try {
    const meta = await getJSON("data/meta.json");
    // when the list of publications was last fetched from recht.bund.de, not when the site was built
    // (RES-4); an unreadable time is never shown: then the build time, or no time at all
    const fetched = [meta.listFetched, meta.generated].map(utcTime).find(Number.isFinite);
    state.listFetched = fetched ?? null;
    // no-break spaces: "07:23 Uhr" and "seit 27.10.2025" stay together, "·" never starts a line
    const parts = [fetched === undefined ? "Datenstand unbekannt"
      : `Datenstand: ${germanDate(fetched)}, ${germanClock(fetched)}\u00a0Uhr`];
    if (Number.isFinite(utcTime(`${meta.since}T00:00`))) parts.push(`Veröffentlichungen seit\u00a0${formatDate(meta.since)}`);
    parts.push("Aktualisierung einmal\u00a0täglich"); // never „täglich“ alone on the last line
    state.dataDate = parts.join("\u00a0· ");
    const line = $("#data-date");
    if (line) line.textContent = state.dataDate;
    const timeline = $(".timeline-page");
    if (timeline && !$(".old-data")) {
      const notice = oldDataNotice();
      if (notice) timeline.before(notice);
    }
  } catch { /* optional */ }
}

const OLD_DATA_HOURS = 36; // one missed evening run and some slack (RES-5)
const BERLIN = { timeZone: "Europe/Berlin" };

/** "2026-10-30T06:23" (UTC, as bundesdiff writes it) → milliseconds; NaN if it is not such a time. */
function utcTime(text) {
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?(Z|[+-]\d{2}:\d{2})?$/.exec(typeof text === "string" ? text : "");
  if (!m) return NaN;
  const [y, mo, d, h, mi, sec] = m.slice(1, 7).map((n) => +(n || 0));
  // a day or hour that does not exist (30 February, 24:00) is unreadable, not rolled over
  const t = new Date(Date.UTC(y, mo - 1, d, h, mi, sec));
  if (t.getUTCFullYear() !== y || t.getUTCMonth() !== mo - 1 || t.getUTCDate() !== d
      || t.getUTCHours() !== h || t.getUTCMinutes() !== mi || t.getUTCSeconds() !== sec) return NaN;
  const zone = /^([+-])(\d{2}):(\d{2})$/.exec(m[7] || "");
  if (zone && (+zone[2] > 23 || +zone[3] > 59)) return NaN; // "+25:99" is no time zone
  return t.getTime() - (zone ? (zone[1] === "-" ? -1 : 1) * (+zone[2] * 60 + +zone[3]) * 60000 : 0);
}

// German time, so the notice and the "Datenstand" line name the same day (23:30 UTC is already the next day)
const germanDay = (ms) => new Date(ms).toLocaleDateString("de-DE", { ...BERLIN, day: "numeric", month: "long", year: "numeric" });
const germanDate = (ms) => new Date(ms).toLocaleDateString("de-DE", { ...BERLIN, day: "2-digit", month: "2-digit", year: "numeric" });
const germanClock = (ms) => new Date(ms).toLocaleTimeString("de-DE", { ...BERLIN, hour: "2-digit", minute: "2-digit" });

/** The notice above the timeline when the list of publications is old, or null (RES-5, RES-A1). */
function oldDataNotice() {
  if (state.listFetched === null || state.listFetched === undefined) return null;
  if (!(Date.now() - state.listFetched > OLD_DATA_HOURS * 3600 * 1000)) return null;
  return el(`<p class="old-data">Die Liste der Veröffentlichungen ist vom <span class="keep">${esc(germanDay(state.listFetched))}</span>.
    Neuere Veröffentlichungen fehlen hier vielleicht noch, weil <span class="domain">recht.bund.de</span> zuletzt nicht erreichbar war.
    Auf <a href="https://www.recht.bund.de/"><span class="domain">recht.bund.de</span></a> finden Sie immer die amtlichen Texte.</p>`);
}

// ---------------------------------------------------------------- search (spec 002, SRCH-*)

/** Lower case, ä→ae ö→oe ü→ue ß→ss, accents and punctuation removed: "BGBl. 2026 I" → "bgbl 2026 i". */
function normalize(text) {
  return (text || "").toLowerCase()
    .replace(/ä/g, "ae").replace(/ö/g, "oe").replace(/ü/g, "ue").replace(/ß/g, "ss")
    .normalize("NFD").replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9]+/g, " ").trim();
}

const search = { pubs: [], laws: [], options: [], selected: -1 };
const RECENT_KEY = "recentSearches";

function buildSearchIndex() {
  const laws = new Map();
  search.pubs = state.pubs.map((p) => {
    for (const law of p.laws || []) {
      const known = laws.get(law.name) || { ...law, pubs: [] };
      known.pubs.push(p);
      laws.set(law.name, known);
    }
    const lawWords = (p.laws || []).map((l) => `${l.name} ${l.abbr} ${l.full}`).join(" ");
    return {
      p, title: ` ${normalize(p.title)}`,
      text: ` ${normalize([p.title, p.typ, p.initiant, p.sachgebiet, p.fundstelle, `${p.year} I ${p.number}`, lawWords].join(" "))}`,
    };
  });
  search.laws = [...laws.values()].map((l) => ({ l, text: ` ${normalize(`${l.name} ${l.abbr} ${l.full}`)}` }));
}

/** Matches of all words, best first: words in the title, at the start of a word, count more. */
function findMatches(words) {
  const score = (item) => words.reduce((sum, w) =>
    sum + (item.title?.includes(` ${w}`) ? 4 : item.title?.includes(w) ? 3 : item.text.includes(` ${w}`) ? 2 : 1), 0);
  const ranked = (items) => items.filter((it) => words.every((w) => it.text.includes(w)))
    .map((it, i) => ({ it, s: score(it), i })).sort((a, b) => b.s - a.s || a.i - b.i).map((x) => x.it);
  return { laws: ranked(search.laws).slice(0, 8), pubs: ranked(search.pubs).slice(0, 30) };
}

/** The text with every match in <mark> – also "ä" for "ae" and the other way round (SRCH-6). */
function highlight(text, words) {
  if (!words.length) return esc(text);
  const alt = { ae: "(?:ae|ä)", oe: "(?:oe|ö)", ue: "(?:ue|ü)", ss: "(?:ss|ß)" };
  const pattern = words.map((w) => w.replace(/ae|oe|ue|ss|./g, (c) => alt[c] || c)).sort((a, b) => b.length - a.length);
  return text.split(new RegExp(`(${pattern.join("|")})`, "gi"))
    .map((part, i) => i % 2 ? `<mark>${esc(part)}</mark>` : esc(part)).join("");
}

function recentSearches() {
  try { return JSON.parse(localGet(RECENT_KEY) || "[]"); } catch { return []; }
}

function rememberSearch(query) {
  const q = query.trim();
  if (!q) return;
  localSet(RECENT_KEY, JSON.stringify([q, ...recentSearches().filter((r) => r !== q)].slice(0, 5)));
}

function openSearch() {
  const dialog = $("#search-dialog");
  if (dialog.open) return;
  search.opener = lastPressed?.closest("#search-open, #fab-search") || document.activeElement;
  lastPressed = null;
  if ($("#dialog").open) $("#dialog").close();
  closeMenu(true);
  $("#search-input").value = "";
  renderSearch();
  dialog.showModal();
  $("#search-input").focus();
}

function closeSearch() {
  $("#search-dialog").close();
}

function renderSearch() {
  const query = $("#search-input").value;
  const words = normalize(query).split(" ").filter(Boolean);
  const box = $("#search-results");
  const status = $("#search-status");
  search.options = [];
  search.selected = -1;
  const option = (html, data) => {
    const id = `so-${search.options.length}`;
    search.options.push({ id, ...data });
    return `<div role="option" id="${id}" class="search-option" aria-selected="false">${html}</div>`;
  };
  const group = (key, title, items) => items.length
    ? `<div role="group" aria-labelledby="sg-${key}"><div class="search-group-title" id="sg-${key}" role="presentation">${title}</div>${items.join("")}</div>` : "";

  if (!words.length) {
    const recent = recentSearches();
    box.innerHTML = group("recent", "Zuletzt gesucht",
      recent.map((r) => option(`<span class="so-title">${esc(r)}</span>`, { query: r })));
    status.textContent = "Suchen Sie nach einem Thema, dem Namen oder der Abkürzung eines Gesetzes oder einer Fundstelle.";
    $("#search-history").hidden = !recent.length;
  } else {
    const { laws, pubs } = findMatches(words);
    const lawOptions = laws.flatMap(({ l }) => l.pubs.slice(0, 3).map((p) => option(`
      <span class="so-title">${highlight(l.name, words)}${l.abbr ? ` (${highlight(l.abbr, words)})` : ""}</span>
      <span class="so-detail">geändert durch: ${esc(p.title)} · ${esc(formatDate(p.date))}</span>`,
      { href: pubHref(p), query })));
    const pubOptions = pubs.map(({ p }) => option(`
      <span class="so-meta"><span class="typ">${esc(p.typ)}</span> ${esc(formatDate(p.date))} · ${highlight(p.fundstelle.replace(/ vom .*/, ""), words)}</span>
      <span class="so-title">${highlight(p.title, words)}</span>
      ${p.sachgebiet ? `<span class="so-detail">${highlight(topicList(p).join("\u00a0· "), words)}</span>` : ""}`,
      { href: pubHref(p), query }));
    box.innerHTML = group("laws", "Gesetze", lawOptions) + group("pubs", "Veröffentlichungen", pubOptions);
    const n = lawOptions.length + pubOptions.length;
    status.textContent = n ? `${n} Treffer`
      : `Nichts gefunden für „${query.trim()}“. Versuchen Sie ein kürzeres Wort, die Abkürzung eines Gesetzes (z. B. EStG) oder ein Thema (z. B. Steuer).`;
    $("#search-history").hidden = true;
  }
  const field = $("#search-input");
  field.setAttribute("aria-expanded", search.options.length > 0);
  field.removeAttribute("aria-activedescendant");
}

function selectOption(index) {
  if (!search.options.length) return;
  search.selected = Math.max(0, Math.min(index, search.options.length - 1));
  search.options.forEach((o, i) => document.getElementById(o.id).setAttribute("aria-selected", i === search.selected));
  const chosen = document.getElementById(search.options[search.selected].id);
  chosen.scrollIntoView({ block: "nearest" });
  $("#search-input").setAttribute("aria-activedescendant", chosen.id);
}

function activateOption(index) {
  const o = search.options[index];
  if (!o) return;
  if (o.href) {
    rememberSearch(o.query);
    search.leaving = true;
    closeSearch();
    location.hash = o.href;
  } else {
    $("#search-input").value = o.query;
    renderSearch();
    $("#search-input").focus();
  }
}

$("#search-input").addEventListener("input", renderSearch);
$("#search-input").addEventListener("keydown", (ev) => {
  if (ev.key === "ArrowDown") { ev.preventDefault(); selectOption(search.selected + 1); }
  else if (ev.key === "ArrowUp") { ev.preventDefault(); selectOption(search.selected - 1); }
  else if (ev.key === "Enter") { ev.preventDefault(); activateOption(Math.max(search.selected, 0)); }
  else if (ev.key === "Escape") { ev.preventDefault(); closeSearch(); }
});
$("#search-results").addEventListener("click", (ev) => {
  const o = ev.target.closest("[role=option]");
  if (o) activateOption(search.options.findIndex((x) => x.id === o.id));
});
$("#search-close").addEventListener("click", closeSearch);
$("#search-history").addEventListener("click", () => {
  localSet(RECENT_KEY, "[]");
  renderSearch();
  $("#search-input").focus();
});
$("#search-dialog").addEventListener("click", (ev) => { if (ev.target.id === "search-dialog") closeSearch(); });
// back where the reader was – unless a result was opened, which moves on to the new page
$("#search-dialog").addEventListener("close", () => {
  if (!search.leaving) returnFocus(search.opener, [$("#search-open"), $("#fab-search")]);
  search.leaving = false;
});

// Strg K / ⌘ K and "/" open the search (SRCH-2); "/" not while typing somewhere else
document.addEventListener("keydown", (ev) => {
  if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === "k") {
    ev.preventDefault();
    openSearch();
    return;
  }
  const typing = /INPUT|SELECT|TEXTAREA/.test(document.activeElement.tagName) || document.activeElement.isContentEditable;
  if (ev.key === "/" && !typing && !$("#dialog").open && !$("#search-dialog").open) {
    ev.preventDefault();
    openSearch();
  }
});
if (/Mac|iPhone|iPad/.test(navigator.platform)) $("#search-open kbd").textContent = "⌘ K";

// ---------------------------------------------------------------- light / dark

function currentTheme() {
  return document.documentElement.dataset.theme
    || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
}

/** Two switches, one setting: in the navbar and in the menu of the phone layout (PTL-6). */
function showThemeButton() {
  const dark = currentTheme() === "dark";
  for (const btn of $$(".theme-switch")) {
    btn.setAttribute("aria-checked", dark);
    btn.title = dark ? "Zur hellen Ansicht wechseln" : "Zur dunklen Ansicht wechseln";
  }
}

function toggleTheme() {
  const next = currentTheme() === "dark" ? "light" : "dark";
  $$(".theme-switch").forEach((b) => b.classList.add("animate"));
  document.documentElement.dataset.theme = next;
  localSet("theme", next);
  showThemeButton();
}

// the system turns dark or light while the page is open: as long as the reader has not picked a
// theme, the page follows it – and so must the switches (A11Y-10)
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", showThemeButton);

// ---------------------------------------------------------------- the menu of the phone layout (PTL-6)

/** `opener`: the round button of the phone layout, or "Menü" in a navbar too narrow for the names of the pages (NAV-3). */
function openMenu(opener = $("#fab-menu")) {
  const menu = $("#menu");
  if (menu.open) return;
  menu.opener = opener;
  menu.classList.toggle("from-navbar", opener.id === "nav-menu"); // then at the top, where the navbar is
  menu.showModal();
  opener.setAttribute("aria-expanded", "true");
}

/** Closes the menu; `quietly` when another window opens or a page is chosen: the focus moves on. */
function closeMenu(quietly = false) {
  const menu = $("#menu");
  if (!menu.open) return;
  menu.quietly = quietly;
  menu.close();
}

$("#menu").addEventListener("close", () => {
  const opener = $("#menu").opener || $("#fab-menu");
  opener.setAttribute("aria-expanded", "false");
  if (!$("#menu").quietly) returnFocus(opener, [$("#fab-menu"), $("#nav-menu")]);
  $("#menu").quietly = false;
});
$("#menu").addEventListener("click", (ev) => {
  if (ev.target.closest("#menu-close")) { closeMenu(); return; }
  if (ev.target.closest("a")) { closeMenu(true); return; } // the link leads on
  const r = $("#menu").getBoundingClientRect();
  const outside = ev.clientX < r.left || ev.clientX > r.right || ev.clientY < r.top || ev.clientY > r.bottom;
  if (ev.target.id === "menu" && outside) closeMenu(); // a tap on the blurred page
});
$("#dialog").addEventListener("close", () => returnFocus($("#dialog").opener));

/* A11Y-3: with the wider letter spacing a reader may set, the full navbar can be wider than the
   media queries in style.css expect (Firefox, about 960–1135 px). Then the name next to the logo
   gives way, and if that is not enough, the long labels give way to the short ones – as on
   narrower screens. Measured again whenever an entry changes its size; in the next frame, so the
   change of size this causes does not start a loop. */
const navbar = $(".navbar");
function fitNavbar() {
  navbar.classList.remove("tight", "tighter", "tightest");
  // the name next to the logo goes, then the long labels, then the pages move into the menu (NAV-3)
  for (const step of ["tight", "tighter", "tightest"]) {
    if (navbar.scrollWidth <= navbar.clientWidth) break;
    navbar.classList.add(step);
  }
}
let navbarFrame = 0;
const watchNavbar = new ResizeObserver(() => {
  cancelAnimationFrame(navbarFrame);
  navbarFrame = requestAnimationFrame(fitNavbar);
});
watchNavbar.observe(navbar);
for (const item of navbar.children) watchNavbar.observe(item);

showThemeButton();
showDataDate();
loadList().then(route);
