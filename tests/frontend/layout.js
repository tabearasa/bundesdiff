// Finds visual layout problems on the current page. Returns [{check, element, detail}].
// Evaluated by test_layout.py in the browser; only visible elements are checked.
(() => {
  const issues = [];
  const vw = document.documentElement.clientWidth;

  const visible = (el) => {
    const s = getComputedStyle(el);
    if (s.display === "none" || s.visibility === "hidden" || +s.opacity === 0) return false;
    // text only for screen readers (status messages): clipped to nothing on purpose
    for (let a = el; a; a = a.parentElement) if (getComputedStyle(a).clipPath === "inset(50%)") return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && !el.closest("[hidden], dialog:not([open]), template");
  };
  const name = (el) => {
    let s = el.tagName.toLowerCase();
    if (el.id) s += "#" + el.id;
    else if (el.classList.length) s += "." + [...el.classList].join(".");
    const text = (el.innerText || el.value || el.getAttribute("aria-label") || "").trim().replace(/\s+/g, " ");
    return text ? `${s} „${text.slice(0, 40)}“` : s;
  };
  const report = (check, el, detail) => issues.push({ check, element: name(el), detail });
  // an ancestor that scrolls or clips horizontally contains the overflow on purpose
  const clippedByAncestor = (el) => {
    for (let a = el.parentElement; a && a !== document.body; a = a.parentElement) {
      const o = getComputedStyle(a).overflowX;
      if (o !== "visible") return a;
    }
    return null;
  };

  // the parts of an element that are really on screen, i.e. not scrolled away inside a scroll box
  const shownRects = (el) => {
    let rects = [...el.getClientRects()];
    for (let a = el.parentElement; a && a !== document.body; a = a.parentElement) {
      if (getComputedStyle(a).overflow === "visible") continue;
      const c = a.getBoundingClientRect();
      rects = rects.map((r) => new DOMRect(Math.max(r.left, c.left), Math.max(r.top, c.top),
        Math.min(r.right, c.right) - Math.max(r.left, c.left), Math.min(r.bottom, c.bottom) - Math.max(r.top, c.top)))
        .filter((r) => r.width > 0 && r.height > 0);
    }
    return rects;
  };

  // while a modal dialog is open, the page behind it cannot be used: check only the dialog
  const root = document.querySelector("dialog[open]") || document.body;
  const all = [...root.querySelectorAll("*")].filter(visible);

  // 1. nothing sticks out of the screen sideways (no horizontal scrolling)
  if (document.documentElement.scrollWidth > vw + 1) {
    report("horizontal-scroll", document.documentElement, `page is ${document.documentElement.scrollWidth}px wide, screen ${vw}px`);
  }
  // wide screens scroll only the text column: content escaping it would make jumps scroll
  // the whole page and push the navbar off screen
  const html = document.documentElement;
  if (getComputedStyle(html).overflowY === "hidden" && html.scrollHeight > html.clientHeight + 1) {
    report("hidden-overflow", html, `page is ${html.scrollHeight}px high but does not scroll (${html.clientHeight}px)`);
  }
  for (const el of all) {
    const r = el.getBoundingClientRect();
    if ((r.right > vw + 1 || r.left < -1) && !clippedByAncestor(el)) {
      report("off-screen", el, `spans ${Math.round(r.left)}–${Math.round(r.right)}px, screen ${vw}px`);
    }
  }

  // 2. text that does not fit its box (cut off or spilling over)
  for (const el of all) {
    const s = getComputedStyle(el);
    if (s.display === "inline" || s.display === "contents") continue;
    if (["auto", "scroll"].includes(s.overflowX) || s.textOverflow === "ellipsis") continue;
    if (["HTML", "BODY", "TABLE", "TBODY", "THEAD", "TR", "COLGROUP", "SVG"].includes(el.tagName)) continue;
    if (el.scrollWidth > el.clientWidth + 2 && el.clientWidth > 0) {
      report("text-overflow", el, `content ${el.scrollWidth}px wide, box ${el.clientWidth}px`);
    }
    // a box with a fixed height whose content spills out below it (over the next content);
    // text shortened on purpose with "…" (line-clamp) is fine
    const clamped = s.webkitLineClamp && s.webkitLineClamp !== "none";
    if (!["auto", "scroll"].includes(s.overflowY) && !clamped && el.clientHeight > 0 && el.scrollHeight > el.clientHeight + 2) {
      report("text-overflow", el, `content ${el.scrollHeight}px high, box ${el.clientHeight}px`);
    }
  }

  // 2b. the chosen value of a list (<select>) cut off inside it: browsers clip it without overflow,
  // e.g. Firefox does not widen a list for wider letter spacing. Measured in a copy of its font.
  for (const el of all.filter((e) => e.matches("select"))) {
    const s = getComputedStyle(el), text = el.selectedOptions[0]?.textContent || "";
    const probe = document.createElement("span");
    probe.textContent = text;
    // the shorthand "font" reads as "" in browsers: copy the parts, or the span gets the body's font
    for (const p of ["fontFamily", "fontSize", "fontWeight", "fontStyle", "fontStretch", "fontVariant", "fontFeatureSettings",
                     "fontVariationSettings", "fontKerning", "letterSpacing", "wordSpacing", "textTransform"]) probe.style[p] = s[p];
    probe.style.position = "absolute"; probe.style.whiteSpace = "pre"; probe.style.visibility = "hidden";
    document.body.appendChild(probe);
    const room = el.clientWidth - parseFloat(s.paddingLeft) - parseFloat(s.paddingRight) - 16; // 16: the arrow
    if (probe.getBoundingClientRect().width > room + 1) {
      report("text-overflow", el, `chosen value „${text}“ is ${Math.round(probe.getBoundingClientRect().width)}px wide, room ${Math.round(room)}px`);
    }
    probe.remove();
  }

  // bars that stay on top while scrolling (navbar, contents bar): once the page is scrolled,
  // text passing underneath them is intended, so they are left out of the overlap and covered
  // checks. Unscrolled, nothing may be under the sticky ones.
  // Fixed elements float over the page by design (the round buttons of the phone layout,
  // spec 004): the text always passes underneath them. That the end of every page can be
  // scrolled out from under them is checked by test_phone.py (PTL-A1).
  const scrolled = scrollY > 0 || (document.querySelector("main")?.scrollTop ?? 0) > 0;
  const pinned = (el) => {
    for (let a = el; a && a !== document.body; a = a.parentElement) {
      const position = getComputedStyle(a).position;
      if (position === "fixed" || (scrolled && position === "sticky")) return true;
    }
    return false;
  };

  // 3. controls must not overlap each other
  const controls = all.filter((el) => el.matches("button, a, input, select, summary, label, .badge"));
  const isPinned = controls.map(pinned);
  const rects = controls.map(shownRects);
  for (let i = 0; i < controls.length; i++) {
    for (let j = i + 1; j < controls.length; j++) {
      const a = controls[i], b = controls[j];
      if (a.contains(b) || b.contains(a) || isPinned[i] !== isPinned[j]) continue;
      const hit = rects[i].some((p) => rects[j].some((q) =>
        Math.min(p.right, q.right) - Math.max(p.left, q.left) > 2 &&
        Math.min(p.bottom, q.bottom) - Math.max(p.top, q.top) > 2));
      if (hit) report("overlap", a, `overlaps ${name(b)}`);
    }
  }

  // 3b. controls on screen must be clickable, not covered by another element
  for (let i = 0; i < controls.length; i++) {
    const r = rects[i][0];
    if (!r) continue;
    const x = r.left + r.width / 2, y = r.top + Math.min(r.height / 2, 8);
    if (x < 0 || y < 0 || x > vw || y > innerHeight) continue;
    const top = document.elementFromPoint(x, y);
    if (top && !controls[i].contains(top) && !top.contains(controls[i]) && (isPinned[i] || !pinned(top))) {
      report("covered", controls[i], `covered by ${name(top)}`);
    }
  }

  // 4. click targets at least 24×24 px (WCAG 2.5.8); links inside running text are exempt
  for (const el of all.filter((e) => e.matches("button, select, input:not([type=hidden]), summary"))) {
    const target = el.closest("label") || el;
    const r = target.getBoundingClientRect();
    if (r.width < 24 || r.height < 24) report("target-size", el, `${Math.round(r.width)}×${Math.round(r.height)}px`);
  }

  // 5. readable text: at least 12 px
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const small = new Set();
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    const el = n.parentElement;
    if (!n.textContent.trim() || small.has(el) || !visible(el)) continue;
    const size = parseFloat(getComputedStyle(el).fontSize);
    if (size < 12) { small.add(el); report("font-size", el, `${size}px`); }
  }

  // 6. no word torn apart without a hyphen ("Nebeneinande / r"): happens when a box is too
  // narrow and overflow-wrap breaks the word. Hyphenation (hyphens: auto) adds a hyphen and is fine.
  const words = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const torn = new Set();
  for (let n = words.nextNode(); n; n = words.nextNode()) {
    const el = n.parentElement;
    if (torn.has(el) || !visible(el) || getComputedStyle(el).hyphens === "auto") continue;
    for (const m of n.textContent.matchAll(/[\p{L}\p{N}]{2,}/gu)) {
      const range = document.createRange();
      range.setStart(n, m.index);
      range.setEnd(n, m.index + m[0].length);
      const lines = new Set([...range.getClientRects()].filter((r) => r.width > 0).map((r) => Math.round(r.top)));
      if (lines.size > 1) { torn.add(el); report("torn-word", el, `„${m[0]}“ is split across lines`); break; }
    }
  }

  return issues;
})()
