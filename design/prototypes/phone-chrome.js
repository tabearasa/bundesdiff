// Mock-up only (spec 004/005/007): laid over the real app in the prototype site.
// No navbar; round buttons at the bottom: back to the timeline and menu on the left,
// help and search on the right. Help and search open the app's own windows.
(() => {
  "use strict";
  const TIMELINE = "../phone-timeline.html";
  const route = () => location.hash.replace(/^#\/?/, "");
  // the start page of the prototype is the phone timeline
  if (!route()) { location.replace(TIMELINE); return; }

  const X = '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M5.5 5.5l9 9M14.5 5.5l-9 9"/></svg>';
  document.body.insertAdjacentHTML("beforeend", `
    <div class="fab-bar">
      <a class="fab" id="proto-back" href="${TIMELINE}" aria-label="Zurück zur Zeitleiste">
        <svg viewBox="0 0 22 22" aria-hidden="true"><path d="M17.5 11H5M10 6l-5 5 5 5"/></svg>
      </a>
      <button class="fab" id="proto-menu-open" aria-label="Menü" aria-haspopup="dialog" aria-expanded="false">
        <svg viewBox="0 0 22 22" aria-hidden="true"><path d="M5 8.5h12M5 13.5h12"/></svg>
      </button>
      <span class="spacer"></span>
      <button class="fab" id="proto-help" aria-label="So funktioniert's" aria-haspopup="dialog"><span class="q" aria-hidden="true">?</span></button>
      <button class="fab" id="proto-search" aria-label="Suchen" aria-haspopup="dialog">
        <svg viewBox="0 0 22 22" aria-hidden="true"><circle cx="9.4" cy="9.4" r="5.6"/><path d="M13.6 13.6l4.6 4.6"/></svg>
      </button>
    </div>
    <dialog class="proto-menu" id="proto-menu" aria-label="Menü">
      <div class="win-head">
        <a class="brand-p" href="${TIMELINE}"><span class="brand-mark-p" aria-hidden="true">§</span><span class="brand-text-p">bundesdiff</span></a>
        <button class="proto-close" data-close aria-label="Schließen">${X}</button>
      </div>
      <ul>
        <li><a href="${TIMELINE}">Veröffentlichungen</a></li>
        <li><a href="#/ueber" data-close>Über bundesdiff</a></li>
      </ul>
      <div class="theme">
        <span id="proto-theme-label">Dunkle Ansicht</span>
        <button class="proto-switch" id="proto-theme" role="switch" aria-checked="false" aria-labelledby="proto-theme-label">
          <span class="track" aria-hidden="true"><span class="knob">
            <svg class="sun" viewBox="0 0 16 16"><circle cx="8" cy="8" r="2.6"/><path d="M8 1.6v1.8M8 12.6v1.8M1.6 8h1.8M12.6 8h1.8M3.47 3.47l1.27 1.27M11.26 11.26l1.27 1.27M3.47 12.53l1.27-1.27M11.26 4.74l1.27-1.27"/></svg>
            <svg class="moon" viewBox="0 0 16 16"><path d="M7.68 2.41A5.6 5.6 0 1 0 13.50 9.45A4.6 4.6 0 0 1 7.68 2.41Z"/></svg>
          </span></span>
        </button>
      </div>
    </dialog>`);

  // back goes to the timeline, centred on the publication the reader came from
  const back = document.getElementById("proto-back");
  const syncBack = () => {
    const m = route().match(/^(\d)\/(\d{4})\/([^/?]+)/);
    back.href = m ? `${TIMELINE}#${m[1]}/${m[2]}/${m[3]}` : TIMELINE;
  };
  syncBack();
  addEventListener("hashchange", () => { if (!route()) location.replace(TIMELINE); syncBack(); });

  // menu
  const menu = document.getElementById("proto-menu");
  const menuBtn = document.getElementById("proto-menu-open");
  menuBtn.addEventListener("click", () => { menu.showModal(); menuBtn.setAttribute("aria-expanded", "true"); });
  menu.addEventListener("close", () => menuBtn.setAttribute("aria-expanded", "false"));
  menu.addEventListener("click", (ev) => {
    const r = menu.getBoundingClientRect();
    const outside = ev.target === menu && (ev.clientX < r.left || ev.clientX > r.right || ev.clientY < r.top || ev.clientY > r.bottom);
    if (outside || ev.target.closest("[data-close]")) menu.close();
  });

  // light/dark: the same setting as the app (localStorage "bundesdiff.theme")
  const sw = document.getElementById("proto-theme");
  const isDark = () => document.documentElement.dataset.theme === "dark" ||
    (!document.documentElement.dataset.theme && matchMedia("(prefers-color-scheme: dark)").matches);
  sw.setAttribute("aria-checked", isDark());
  sw.addEventListener("click", () => {
    const t = isDark() ? "light" : "dark";
    document.documentElement.dataset.theme = t;
    sw.setAttribute("aria-checked", t === "dark");
    try { localStorage.setItem("bundesdiff.theme", t); } catch {}
  });

  // help and search: the app's own windows, opened by its (hidden) navbar buttons
  document.getElementById("proto-help").addEventListener("click", () => document.getElementById("nav-help").click());
  document.getElementById("proto-search").addEventListener("click", () => document.getElementById("search-open").click());

  // "Schließen" of the app's windows becomes a drawn x (SHAPE-7)
  for (const id of ["dialog-close", "search-close"]) {
    const b = document.getElementById(id);
    if (!b) continue;
    b.className = "proto-close";
    b.setAttribute("aria-label", "Schließen");
    b.innerHTML = X;
  }
})();
