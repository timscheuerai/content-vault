#!/usr/bin/env python3
"""Brand conformance: no un-branded value may reach the screen.

Static graphics have a human reviewing them against BRAND.md. Motion graphics are drawn by
code at 30fps, so the only thing standing between the brand and a hardcoded `#00ff00` is a
check. This parses the ACTUAL token table out of BRAND.md and compares it to the constants
the renderers use. If the brand changes, this fails until the code follows.

It also enforces the one rule BRAND.md states and no compiler can: **exactly one accent**.
"the one green. Use sparingly." A second emerald element is a brand violation, not a bug.

    python brand_lint.py          # exits 1 on any drift
"""
import re
import sys

import numpy as np

from assets import BRAND_MD as BRAND   # set SHORTS_BRAND_MD to point at yours


def brand_tokens():
    """Parse the colour table straight out of BRAND.md — never hardcode it here."""
    if not BRAND.exists():
        print(f"  ! BRAND.md not found at {BRAND}")
        return {}
    toks = {}
    for line in BRAND.read_text().splitlines():
        m = re.match(r"\|\s*`--([\w-]+)`\s*\|\s*`(#[0-9a-fA-F]{6})`", line.strip())
        if m:
            toks[m.group(1)] = m.group(2).lower()
    return toks


def hexof(rgb):
    return "#%02x%02x%02x" % tuple(rgb[:3])


def main():
    t = brand_tokens()
    if not t:
        return 1
    print(f"BRAND.md tokens: {len(t)} parsed\n")

    import motion
    import caption_render as cr
    import tierboard as tb
    import polish

    fails = 0

    # 1. every colour the renderers use must BE a brand token
    checks = [
        ("motion.SURFACE", hexof(motion.SURFACE), t.get("surface")),
        ("motion.INK", hexof(motion.INK), t.get("ink")),
        ("motion.MUTED", hexof(motion.MUTED), t.get("muted")),
        ("motion.LINE", hexof(motion.LINE), t.get("line")),
        ("motion.ACCENT", hexof(motion.ACCENT), t.get("accent")),
        ("tierboard.CHIP_INK", hexof(tb.CHIP_INK), t.get("ink")),
    ]
    for label, got, want in checks:
        ok = got == want
        fails += 0 if ok else 1
        print(f"  [{'ok  ' if ok else 'FAIL'}] {label:22} {got}"
              + ("" if ok else f"  != BRAND {want}"))

    # 2. the caption face must be the brand's font-sans
    src = BRAND.read_text()
    m = re.search(r"--font-sans:\s*'([^']+)'", src)
    want_face = m.group(1) if m else None
    got_face = "Helvetica Neue" if "HelveticaNeue" in cr.FONT_PATH else cr.FONT_PATH
    ok = want_face and want_face.lower() in got_face.lower()
    fails += 0 if ok else 1
    print(f"  [{'ok  ' if ok else 'FAIL'}] caption font          {got_face}"
          + ("" if ok else f"  != BRAND {want_face}"))

    # 3. THE ONE GREEN. BRAND.md: "the one green. Use sparingly."
    #    Render each primitive and count distinct accent regions. More than one is a
    #    brand violation that no type checker will ever catch.
    print()
    accent = np.array(motion.ACCENT)
    # Every primitive that can draw goes in here. Three of them shipped outside this list
    # once, which meant the one-green rule was enforced on the four oldest renderers and
    # silently not enforced on the newest — the ones most likely to get it wrong.
    _flow_lanes = [
        {"badge": "TIER 1", "to": "Sales team", "sub": "handed over", "focal": True, "_at": 0},
        {"badge": "TIER 2", "to": "Sequence", "_at": 10},
        {"badge": "TIER 3", "to": "Nurture", "sub": "content", "_at": 20},
    ]
    for label, img in [
        ("stat",  motion.stat(30, 90, kicker="the goal", value="300", label="users")),
        ("steps", motion.steps(40, 120, kicker="the system", items=["One", "Two", "Three"])),
        ("tier",  motion.tier(30, 90, kicker="channel 04", label="LinkedIn", grade="S")),
        ("label", motion.label(20, 60, text="Score against ICP")),
        ("chips", motion.chips(40, 120, items=["Post engagers", "Profile viewers"])),
        ("leads", motion.leads(60, 180, title="inbound", count=214, rows=[
            {"name": "A Person", "headline": "Head of Growth", "score": "A"}])),
        ("flow",  motion.flow(120, 300, kicker="routing", source="214 leads",
                              lanes=_flow_lanes)),
    ]:
        a = np.asarray(img).astype(int)
        hit = ((np.abs(a[:, :, :3] - accent).sum(axis=2) < 30) & (a[:, :, 3] > 200))
        # count connected blobs cheaply: distinct rows-of-pixels clusters
        ys, xs = np.nonzero(hit)
        blobs = 0
        if len(ys):
            seen = np.zeros_like(hit)
            from collections import deque
            for y, x in zip(ys, xs):
                if seen[y, x]:
                    continue
                blobs += 1
                q = deque([(y, x)])
                seen[y, x] = 1
                while q:
                    cy, cx = q.popleft()
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            ny, nx = cy + dy, cx + dx
                            if (0 <= ny < hit.shape[0] and 0 <= nx < hit.shape[1]
                                    and hit[ny, nx] and not seen[ny, nx]):
                                seen[ny, nx] = 1
                                q.append((ny, nx))
        if label == "flow":
            # A routing board marks its focal lane with ONE path drawn in three pieces —
            # badge outline, connector, arrowhead — separated by the gaps the layout puts
            # between them. Blob-counting reads that as three violations when it is one
            # accent with one meaning. What must not happen is the green spreading to a
            # second lane, so that is what gets asserted: the accent stays inside a single
            # lane-height band.
            span = int(ys.max() - ys.min()) if len(ys) else 0
            ok = len(ys) > 0 and span <= 66 * motion.S
            note = f"accent inside one {span // motion.S}px lane band ({blobs} pieces)"
        else:
            ok = blobs <= 1
            note = f"{blobs} accent element(s)"
        fails += 0 if ok else 1
        print(f"  [{'ok  ' if ok else 'FAIL'}] one-green: {label:6} {note}"
              + ("" if ok else "  <-- BRAND.md: 'the one green. Use sparingly.'"))

    print("\n" + "=" * 56)
    print("BRAND: conformant" if not fails else f"BRAND: {fails} violation(s)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
