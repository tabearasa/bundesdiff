"""Is the content of every framed control centred in its frame?

A button, badge or logo with a visible border or its own background shows whether its text or
symbol sits in the middle. The DOM cannot tell (a glyph may be drawn off-centre inside its own
line box), so this looks at the pixels: it screenshots the inside of each frame, finds the
"ink" (pixels that differ from the frame's background) and compares the gaps on both sides.
"""

from __future__ import annotations

import pymupdf

# Visible elements that draw a frame: a border all round or a background of their own.
# Only frames whose padding is equal on both sides are checked in that direction.
FRAMES_JS = r"""
() => {
  const px = v => parseFloat(v) || 0;
  const visible = c => c && c !== "transparent" && !/rgba\(.*,\s*0\)$/.test(c);
  const bgOf = e => { for (; e; e = e.parentElement) { const c = getComputedStyle(e).backgroundColor;
                      if (visible(c)) return c; } return "rgb(255, 255, 255)"; };
  const out = [];
  for (const e of document.querySelectorAll("button, a, summary, .badge, .brand-mark, .knob, [role=button]")) {
    const s = getComputedStyle(e), r = e.getBoundingClientRect();
    if (!r.width || !r.height || s.visibility === "hidden" || r.height > 90 || r.width > 420) continue;
    if (!e.innerText.trim() && !e.querySelector("svg")) continue;
    // covered (e.g. behind an open dialog): what is seen there is not this element
    const top = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
    if (!top || !(e === top || e.contains(top))) continue;
    const bordered = ["Top", "Right", "Bottom", "Left"].every(
      side => px(s[`border${side}Width`]) >= 1 && visible(s[`border${side}Color`]));
    const filled = visible(s.backgroundColor) && s.backgroundColor !== bgOf(e.parentElement);
    if (!bordered && !filled) continue;
    // a single line of content, not text wrapped inside a wide box
    const range = document.createRange(); range.selectNodeContents(e);
    const lines = new Set([...range.getClientRects()].filter(q => q.width > 1).map(q => Math.round(q.top)));
    if (lines.size !== 1) continue;
    const content = range.getBoundingClientRect();
    const b = side => px(s[`border${side}Width`]), p = side => px(s[`padding${side}`]);
    const inner = r.width - b("Left") - b("Right") - p("Left") - p("Right");
    const centredText = s.textAlign === "center" || s.justifyContent === "center"
                        || s.placeItems.includes("center") || content.width >= inner - 2;
    const label = (e.id ? "#" + e.id : e.tagName.toLowerCase() + (e.className ? "." + [...e.classList].join(".") : ""))
                  + ` "${e.innerText.trim().slice(0, 30)}"`;
    out.push({ label, x: r.left + b("Left"), y: r.top + b("Top"),
               w: r.width - b("Left") - b("Right"), h: r.height - b("Top") - b("Bottom"),
               checkX: centredText && Math.abs(p("Left") - p("Right")) <= 1,
               checkY: Math.abs(p("Top") - p("Bottom")) <= 1 });
  }
  return out;
}
"""

# How far the ink may be off the middle. Letters are not symmetric (a "g" hangs below the
# line), so vertically a little more is allowed than horizontally.
TOLERANCE_X = 2.5
TOLERANCE_Y = 3.0


def _ink_box(png: bytes, css_width: float) -> tuple[float, float, float, float] | None:
    """Left, top, right, bottom (in CSS px) of the pixels that differ from the most common colour."""
    pix = pymupdf.Pixmap(png)
    scale = pix.width / css_width
    n, w, h, data = pix.n, pix.width, pix.height, pix.samples
    counts: dict[bytes, int] = {}
    for i in range(0, len(data), n):
        key = data[i:i + 3]
        counts[key] = counts.get(key, 0) + 1
    bg = max(counts, key=counts.get)
    left, top, right, bottom = w, h, -1, -1
    for y in range(h):
        row = y * w * n
        for x in range(w):
            i = row + x * n
            if abs(data[i] - bg[0]) + abs(data[i + 1] - bg[1]) + abs(data[i + 2] - bg[2]) > 90:
                left, right = min(left, x), max(right, x)
                top, bottom = min(top, y), max(bottom, y)
    return None if right < 0 else (left / scale, top / scale, (right + 1) / scale, (bottom + 1) / scale)


def off_centre(page) -> list[str]:
    """Framed controls in the viewport whose content is not in the middle of the frame."""
    page.mouse.move(0, 0)  # no hover colours
    page.evaluate("document.activeElement && document.activeElement.blur()")
    vw, vh = page.viewport_size["width"], page.viewport_size["height"]
    issues = []
    for f in page.evaluate(FRAMES_JS):
        # 2 px inset: a border on a half pixel is anti-aliased into the next pixel; not content
        x, y, w, h = f["x"] + 2, f["y"] + 2, f["w"] - 4, f["h"] - 4
        if x < 0 or y < 0 or x + w > vw or y + h > vh or w < 4 or h < 4:
            continue  # not fully on screen; checked where it is (other pages, sizes)
        ink = _ink_box(page.screenshot(clip={"x": x, "y": y, "width": w, "height": h}), w)
        if not ink:
            continue
        left, top, right, bottom = ink
        dx = (left - (w - right)) / 2
        dy = (top - (h - bottom)) / 2
        if f["checkX"] and abs(dx) > TOLERANCE_X:
            issues.append(f"{f['label']}: {abs(dx):.1f}px too far {'right' if dx > 0 else 'left'} (ink {left:.1f}–{right:.1f} in {w:.1f})")
        if f["checkY"] and abs(dy) > TOLERANCE_Y:
            issues.append(f"{f['label']}: {abs(dy):.1f}px too {'low' if dy > 0 else 'high'}")
    return issues
