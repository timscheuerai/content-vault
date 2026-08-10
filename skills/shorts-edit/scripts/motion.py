#!/usr/bin/env python3
"""Stage 3 of 3 — render on-brand motion graphics, drawn per frame at 30fps.

The pipeline already composites a per-frame RGBA sequence, which means it is already a
motion-graphics engine: anything drawable in PIL can be animated at frame resolution with
no extra ffmpeg input and no extra encode.

TWO RULES, learned the hard way:

1. DEFAULT TO AN OVERLAY PANEL, NOT A FULL-SCREEN CARD. On a talking-head short the face
   is what carries it. A full-screen card doesn't add a graphic, it removes the presenter.
   The panel sits in the lower 40% and leaves him on camera. Full-screen is reserved for a
   genuine chapter break.

2. THE MOTION IS THE POINT. A card that fades in is a slide. A number that counts up, a
   list that builds as he names each item, a tier chip that fills — those track what he is
   SAYING, which is what makes a graphic feel authored instead of pasted on.

BRAND (gtm-production/brand/BRAND.md — do not invent values):
    surface #ffffff · ink #0a0a0a · muted #71717a · line #e4e4e7 · accent #10b981 (once)
    font-sans Helvetica Neue · radius 6/10/14/20 · no shadows, no gradients.
"""
import math
import os

from PIL import Image, ImageDraw, ImageFont

from paths import S

from assets import FONT_PATH as FONT, REGULAR, BOLD, MEDIUM

SURFACE = (255, 255, 255)
INK = (10, 10, 10)
MUTED = (113, 113, 122)
LINE = (228, 228, 231)
ACCENT = (16, 185, 129)

W, H = 360, 640
PAD = 20


def _f(sz, face=MEDIUM):
    """`sz` is logical (360x640) — the font rasterizes at OUT resolution (paths.S)."""
    return ImageFont.truetype(FONT, sz * S, index=face)


def ease_out(t):
    return 1 - (1 - min(max(t, 0.0), 1.0)) ** 3


def spring(i, delay=0.0, settle=12.0):
    """Damped-spring step 0->1 over frames: one ~5% overshoot, settled by ~`settle`
    frames. Editor motion (AE / CapCut defaults) is spring-based; a cubic ease that
    just decelerates reads as a slide deck. Use for POSITION and SCALE; keep plain
    ease_out for opacity — opacity that overshoots flickers."""
    t = (i - delay) / settle
    if t <= 0.0:
        return 0.0
    return 1.0 - math.exp(-7.0 * t) * math.cos(6.44 * t)


def _lerp(c1, c2, t):
    t = min(max(t, 0.0), 1.0)
    return tuple(int(round(a + (b - a) * t)) for a, b in zip(c1, c2))


class _SD:
    """Scaled-draw proxy: layout code thinks in logical 360x640 px, the raster is OUT
    (1080x1920). Coordinates, radii and stroke widths multiply by S on the way through;
    fonts from _f() are already real-sized; textlength converts back to logical so layout
    math stays consistent. Float logical coords land on 1/S-px boundaries — which is what
    makes slow slides and settles look fluid instead of quantized to source pixels."""

    def __init__(self, d):
        self._d = d

    @staticmethod
    def _xy(xy):
        return [v * S for v in xy]

    def text(self, xy, *a, **k):
        self._d.text((xy[0] * S, xy[1] * S), *a, **k)

    def textlength(self, *a, **k):
        return self._d.textlength(*a, **k) / S

    def rectangle(self, box, **k):
        self._d.rectangle(self._xy(box), **self._wk(k))

    def rounded_rectangle(self, box, radius=0, **k):
        self._d.rounded_rectangle(self._xy(box), radius=radius * S, **self._wk(k))

    def ellipse(self, box, **k):
        self._d.ellipse(self._xy(box), **k)

    def line(self, xy, **k):
        self._d.line(self._xy(xy), **self._wk(k))

    @staticmethod
    def _wk(k):
        if "width" in k:
            k = {**k, "width": k["width"] * S}
        return k


def _new_layer():
    """Draw EVERYTHING at full opacity on its own layer, then fade the layer.

    ImageDraw with a partial-alpha fill OVERWRITES pixels, it does not composite. Drawing
    a fading chip straight onto the panel therefore punches a transparent HOLE through it
    and the video shows through — the selected tier chip rendered as a black box instead
    of a green one. Never draw with a variable alpha; vary the layer's alpha instead.
    """
    lay = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
    return lay, _SD(ImageDraw.Draw(lay))


def _fade(img, lay, a):
    if a < 255:
        alpha = lay.getchannel("A").point(lambda v: v * a // 255)
        lay.putalpha(alpha)
    img.alpha_composite(lay)
    return img


def _panel(d, top, height, radius=14):
    """The white card the content sits on. Hairline, no shadow — 'ink, surface, line'.

    `height` HUGS the content: a panel that always runs to the bottom of the frame leaves a
    dead white void under the last row, which reads as a broken layout.
    """
    d.rounded_rectangle([PAD, top, W - PAD, top + height], radius=radius,
                        fill=SURFACE + (255,), outline=LINE + (255,), width=1)


def _kicker(d, x, y, text, dot=True):
    """`dot` draws THE one green. Pass dot=False when the graphic already spends its accent
    on its payload (the live step row, the filled tier chip).

    BRAND.md: "the one green. Use sparingly." Two accents in one graphic is a brand
    violation — brand_lint.py counts the accent blobs and fails the build. The accent
    belongs on the thing the viewer is meant to look at, not on the label."""
    if not text:
        return y
    kf = _f(10, MEDIUM)
    d.text((x, y), text.upper(), font=kf, fill=MUTED + (255,), anchor="ls")
    if dot:
        kw = d.textlength(text.upper(), font=kf)
        d.ellipse([x + kw + 6, y - 7, x + kw + 10, y - 3], fill=ACCENT + (255,))
    return y + 22


# --------------------------------------------------------------------------- primitives

def stat(i, n, kicker="", value="", label="", full=False):
    """A hard number counting up. Use for '300 users', '14% reply rate', '11k followers'.

    full=True is the whole-frame white hook card (approved on the 16-12-00 lead magnet
    hook, 2026-07-19): the value enormous and centred, `label` as the payoff word with THE
    accent dot as its full stop, `kicker` as the muted subline. It removes the presenter,
    so it stays reserved for the hook / a genuine chapter break — and because place()
    composites over the caption frames, a full-opacity card also hides the captions for
    exactly its window; the card IS the text there.
    """
    img = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
    lay, d = _new_layer()
    intro = ease_out(i / 6)
    a = int(255 * min(intro, ease_out((n - i) / 5)))

    # the number counts up INTO the cue word and lands on it
    head, tail = _split_num(value)
    grow = ease_out(min(max(i - PAYLOAD + 10, 0) / 12, 1.0))
    shown = f"{int(round(head * grow)):,}{tail}" if head is not None else value

    if full:
        d.rectangle([0, 0, W, H], fill=SURFACE + (255,))
        dt = i - PAYLOAD

        # Choreography, not a fade: the number springs up from 96%, pops as it lands on
        # the word, then BREATHES (nothing on screen is ever frozen — a static frame is
        # the tell of a slide), and recedes 1.5% on exit. Label, subline and hairline
        # arrive staggered 2/5/8 frames after the land, each on its own faded layer.
        sc = 0.96 + 0.04 * spring(i, settle=12)
        if dt >= 0:
            sc *= 1.0 + 0.06 * math.exp(-dt / 2.8) * math.cos(dt * 0.9)
        if dt > 10:
            sc *= 1.0 + 0.004 * math.sin((dt - 10) / 7.2)
        sc *= 1.0 - 0.015 * ease_out(max(0, i - (n - 6)) / 5)
        d.text((W / 2, 300), shown, font=_f(max(8, int(150 * sc)), BOLD),
               fill=INK + (255,), anchor="mm")

        def _grp(alpha, fn):
            if alpha <= 0:
                return
            g, gd = _new_layer()   # fade as a layer — never draw with variable alpha
            fn(gd)
            _fade(lay, g, int(255 * alpha))

        rise = 10 * (1 - spring(dt, delay=2, settle=10))

        def _label(gd):
            lf = _f(40, BOLD)
            gd.text((W / 2, 408 + rise), label, font=lf, fill=INK + (255,), anchor="mm")
            tw = gd.textlength(label, font=lf)
            gd.ellipse([W / 2 + tw / 2 + 9, 419 + rise, W / 2 + tw / 2 + 16, 426 + rise],
                       fill=ACCENT + (255,))

        def _sub(gd):
            gd.text((W / 2, 448), kicker.upper(), font=_f(15, MEDIUM),
                    fill=MUTED + (255,), anchor="mm")

        def _rule(gd):
            half = 40 * ease_out(min(max(dt - 8, 0) / 6, 1.0))
            if half > 1:
                gd.line([W / 2 - half, 482, W / 2 + half, 482],
                        fill=LINE + (255,), width=1)

        _grp(ease_out(min(max(dt - 2, 0) / 6, 1.0)), _label)
        if kicker:
            _grp(ease_out(min(max(dt - 5, 0) / 6, 1.0)), _sub)
        _grp(ease_out(min(max(dt - 8, 0) / 6, 1.0)), _rule)
        return _fade(img, lay, a)

    ph = 132 + (20 if label else 0) + (22 if kicker else 0)
    top = H - PAD - ph + 14 * (1 - spring(i, settle=11))
    _panel(d, top, ph)

    x, y = PAD + 18, top + 34
    y = _kicker(d, x, y, kicker)
    d.text((x, y + 44), shown, font=_f(46, BOLD), fill=INK + (255,), anchor="ls")

    if label:
        d.text((x, y + 70), label, font=_f(14, MEDIUM), fill=MUTED + (255,), anchor="ls")
    return _fade(img, lay, a)


def _split_num(v):
    """'11,000' -> (11000, '') ; '14%' -> (14, '%') ; '2x' -> (2, 'x')"""
    m = "".join(c for c in v if c.isdigit())
    if not m:
        return None, v
    tail = v[v.rfind(m[-1]) + 1:] if m else ""
    return int(m), tail


def steps(i, n, kicker="", items=(), full=False):
    """A list that BUILDS — one row lands every 5 frames, tracking what he's naming."""
    img = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
    lay, d = _new_layer()
    intro = ease_out(i / 6)
    a = int(255 * min(intro, ease_out((n - i) / 5)))
    ph = 56 + (22 if kicker else 0) + 30 * len(items)
    top = H - PAD - ph + 14 * (1 - spring(i, settle=11))
    _panel(d, top, ph)

    x, y = PAD + 18, top + 34
    y = _kicker(d, x, y, kicker, dot=False)      # the accent goes to the live row

    for k, it in enumerate(items):
        ri = ease_out((i - PAYLOAD - k * 5) / 6)    # first row lands on the cue
        if ri <= 0:
            continue
        # a row that is still arriving fades from the panel white, not from transparent —
        # fading toward transparent would punch through the panel (see _new_layer)
        yy = y + 26 + k * 30 - 8 * (1 - spring(i, delay=PAYLOAD + k * 5, settle=8))
        live = (i - PAYLOAD - k * 5) < 12            # the row currently landing
        dot = _lerp(SURFACE, ACCENT if live else MUTED, ri)
        txt = _lerp(SURFACE, INK, ri)
        d.ellipse([x, yy - 9, x + 6, yy - 3], fill=dot + (255,))
        d.text((x + 16, yy), it, font=_f(17, BOLD if live else MEDIUM),
               fill=txt + (255,), anchor="ls")
    return _fade(img, lay, a)


def tier(i, n, kicker="", label="", grade="B", scale=("S", "A", "B", "C", "F")):
    """A ranking. Chips sit greyed; the called grade fills emerald and scales up ON the word."""
    img = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
    lay, d = _new_layer()
    intro = ease_out(i / 6)
    a = int(255 * min(intro, ease_out((n - i) / 5)))
    ph = 128 + (22 if kicker else 0)
    top = H - PAD - ph + 14 * (1 - spring(i, settle=11))
    _panel(d, top, ph)

    x, y = PAD + 18, top + 34
    y = _kicker(d, x, y, kicker, dot=False)      # the accent goes to the filled chip
    d.text((x, y + 22), label, font=_f(19, BOLD), fill=INK + (255,), anchor="ls")

    cw, gap, cy = 44, 8, y + 44
    # Centre the pop ON the word: start filling 3 frames early so it is mid-fill as he
    # says the grade and lands just after. Starting exactly AT the cue means the chip
    # is still blank at the instant that matters.
    hit = ease_out((i - PAYLOAD + 3) / 7)
    for k, g in enumerate(scale):
        cx = x + k * (cw + gap)
        on = (g.upper() == grade.upper())
        pop = 3 * spring(i, delay=PAYLOAD - 3, settle=8) if on else 0
        box = [cx - pop, cy - pop, cx + cw + pop, cy + 34 + pop]
        if on:
            # LERP the fill from panel-white to emerald. Filling with a variable ALPHA
            # would punch a hole through the panel and render the chip black.
            d.rounded_rectangle(box, radius=8, fill=_lerp(SURFACE, ACCENT, hit) + (255,),
                                outline=_lerp(LINE, ACCENT, hit) + (255,), width=1)
            col = _lerp(MUTED, SURFACE, hit)
        else:
            d.rounded_rectangle(box, radius=8, outline=LINE + (255,), width=1)
            col = MUTED
        d.text(((box[0] + box[2]) // 2, (box[1] + box[3]) // 2), g,
               font=_f(18, BOLD), fill=col + (255,), anchor="mm")
    return _fade(img, lay, a)


def label(i, n, kicker="", text=""):
    """A lower-third chip. The lightest touch — barely covers anything, keeps him framed.

    `kicker` is ACCEPTED AND DELIBERATELY NOT DRAWN. The chip is one line by design; a
    kicker row would make it a panel. It stays in the signature so a plan can carry the
    same shape for every primitive, but if you want the kicker seen, put it in `text`
    ("01 · Build in public"). Silently dropping it once cost a whole batch of step numbers.
    """
    img = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
    lay, d = _new_layer()
    intro = ease_out(i / 5)
    a = int(255 * min(intro, ease_out((n - i) / 4)))

    f = _f(15, BOLD)
    tw = d.textlength(text, font=f)
    x = PAD
    y = int(H * 0.86) + 10 * (1 - spring(i, settle=9))
    box = [x, y, x + tw + 46, y + 34]
    d.rounded_rectangle(box, radius=8, fill=SURFACE + (255,), outline=LINE + (255,), width=1)
    d.ellipse([x + 14, y + 15, x + 20, y + 21], fill=ACCENT + (255,))
    d.text((x + 30, y + 24), text, font=f, fill=INK + (255,), anchor="ls")
    return _fade(img, lay, a)


KINDS = {"stat": stat, "steps": steps, "tier": tier, "label": label}

LEAD = 0.7          # seconds the panel is on screen BEFORE the payload lands
PAYLOAD = round(LEAD * 30)   # frame index at which the grade fills / number lands


def resolve_cue(name, cue, fps=30):
    """Find when a phrase is actually SPOKEN, on the finished timeline.

    Graphics must be anchored to the WORDS, not to a time someone typed. Hand-placed
    timestamps put the "F" on screen 5.7s before he said it — and in a tier list the grade
    IS the punchline, so revealing it early destroys the moment. This is the difference
    between a graphic that feels authored and one that feels pasted on.
    """
    from make_captions import build_events
    events, _ = build_events(name)
    words = [w.lower().strip(".,?!") for _, _, w in events]
    starts = [a for a, _, _ in events]
    toks = [t for t in cue.lower().split() if t]
    for i in range(len(words) - len(toks) + 1):
        if words[i:i + len(toks)] == toks:
            return starts[i]
    return None


def resolve_plan(plan, name, fps=30):
    """Resolve cues -> frame windows, and refuse to let two graphics overlap.

    Overlapping panels stack on top of each other and the older one is simply overwritten
    mid-animation, which looks like a rendering fault. Clip the earlier one instead.
    """
    out = []
    for g in plan:
        if g.get("cue"):
            t = resolve_cue(name, g["cue"], fps)
            if t is None:
                print(f"    !! cue not found, skipping: {g['cue']!r}")
                continue
            f0 = max(0, round((t - float(g.get("lead", LEAD))) * fps))
        else:
            f0 = round(float(g["at"]) * fps)

        # NESTED CUES. A graphic that stays up across several beats (the routing
        # flowchart: tier 1 at 28.0s, tier 2 at 30.1s, tier 3 at 34.3s) needs each ROW
        # anchored to its own word, not to a stagger counted from the panel's entrance.
        # A fixed stagger drifts the moment the speech does, which is the exact failure
        # that put a tier grade on screen 5.7s early. Resolved here, stored as `_at`
        # frames RELATIVE to the window, so the primitive only ever sees local time.
        for key in ("lanes", "items", "rows"):
            for it in (g.get(key) or []):
                if isinstance(it, dict) and it.get("cue"):
                    ct = resolve_cue(name, it["cue"], fps)
                    if ct is None:
                        print(f"    !! nested cue not found: {it['cue']!r}")
                        continue
                    it["_at"] = max(0, round(ct * fps) - f0)

        # A SECOND cue on the same graphic, for a panel whose payload is a separate beat
        # from its entrance. `score_cue` on the lead table is the case this exists for:
        # the rows arrive when he says "put them into a table", but the ICP grades must
        # not land until he says "score them against their ICP" eight seconds later.
        # Any `<name>_cue` key resolves to `_at_<name>` frames, relative to the window.
        for k in [k for k in g if k.endswith("_cue")]:
            ct = resolve_cue(name, g[k], fps)
            if ct is None:
                print(f"    !! {k} not found: {g[k]!r}")
                continue
            g["_at_" + k[:-4]] = max(0, round(ct * fps) - f0)

        out.append([f0, f0 + round(float(g.get("dur", 2.8)) * fps), g])

    out.sort(key=lambda r: r[0])
    # Clip within a screen REGION, derived from where the graphic actually DRAWS —
    # never from its kind. An earlier version exempted `logo` because it sat at 0.11H;
    # the mark was later moved down to the caption line and the stale exemption let it
    # render on top of a profile card. Asking for the position keeps the two in step.
    def region(g):
        if g["kind"] == "logo" and float(g.get("y_frac") or 1) <= 0.3:
            return "top"
        return "bottom"

    for reg in ("top", "bottom"):
        idx = [i for i, r in enumerate(out) if region(r[2]) == reg]
        for a, b in zip(idx, idx[1:]):
            if out[a][1] > out[b][0]:
                out[a][1] = out[b][0]          # clip, never stack
    return out


def place(frames_dir, plan, fps=30, name=None):
    """plan = [{cue|at, dur, kind, ...}]. `cue` is a phrase from the transcript."""
    for f0, f1, g in resolve_plan(plan, name, fps):
        n = f1 - f0
        fn = KINDS[g["kind"]]
        args = {k: v for k, v in g.items()
                if k not in ("at", "cue", "dur", "kind", "lead")}
        import inspect
        wants_base = "base" in inspect.signature(fn).parameters
        for i in range(n):
            p = frames_dir / f"f_{f0 + i:06d}.png"
            if not p.exists():
                continue
            base = Image.open(p).convert("RGBA")
            base.alpha_composite(fn(i, n, base=base, **args) if wants_base
                                 else fn(i, n, **args))
            os.unlink(p)                 # break the hardlink before writing
            base.save(p)


def load_plan(name):
    import json
    from paths import EDIT
    p = EDIT / "motion.json"
    if not p.exists():
        return []
    return json.loads(p.read_text()).get(name, [])


# ---------------------------------------------------------------------------
# Added for the Lovable clip. All four follow the house contract:
#   fn(i, n, **args) -> RGBA layer, drawn at FULL opacity then faded as a layer
#   (never draw with a variable alpha — see _new_layer).
# ---------------------------------------------------------------------------

_IMG_CACHE = {}


def _asset(src, w, h):
    """Load a logo asset scaled to logical w x h (rasterised at OUT resolution).

    Cached: a logo firing on four separate cues would otherwise re-decode per frame.
    """
    key = (src, w, h)
    if key not in _IMG_CACHE:
        im = Image.open(os.path.expanduser(src)).convert("RGBA")
        im.thumbnail((w * S, h * S), Image.LANCZOS)
        _IMG_CACHE[key] = im
    return _IMG_CACHE[key]


def _chip_alpha(i, n):
    """In fast, hold, out fast — the standard chip envelope."""
    return int(255 * min(ease_out(i / 6.0), ease_out((n - i) / 6.0)))



def _glass(base, box, radius=16, tint=0.86, blur=22):
    """A REAL glass surface: sample what is behind the panel, blur it, tint it white.

    A flat white card is not glassmorphism — the whole effect is that the video shows
    through, softened. Sampling `base` is why this primitive takes the frame.
    """
    from PIL import ImageFilter
    x0, y0, x1, y1 = [int(v * S) for v in box]
    crop = base.crop((max(0, x0), max(0, y0), min(base.width, x1), min(base.height, y1)))
    crop = crop.convert("RGB").filter(ImageFilter.GaussianBlur(blur * S / 3))
    white = Image.new("RGB", crop.size, (255, 255, 255))
    crop = Image.blend(crop, white, tint).convert("RGBA")
    mask = Image.new("L", crop.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, crop.size[0] - 1, crop.size[1] - 1],
                                           radius=int(radius * S), fill=255)
    crop.putalpha(mask)
    return crop, (max(0, x0), max(0, y0))


def _avatar(src, d_px):
    """Circular profile picture, the LinkedIn way."""
    key = ("av", src, d_px)
    if key not in _IMG_CACHE:
        im = Image.open(os.path.expanduser(src)).convert("RGBA")
        n = d_px * S
        im = im.resize((n, n), Image.LANCZOS)
        mask = Image.new("L", (n, n), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, n - 1, n - 1], fill=255)
        im.putalpha(mask)
        _IMG_CACHE[key] = im
    return _IMG_CACHE[key]


def logo(i, n, src, size=58, y_frac=None):
    """Brand mark ONLY — no wordmark — sitting just above the caption band.

    Captions live at 0.78H (y=499); this parks its baseline at y=478 so the logo reads
    as a header to the line being spoken rather than a chip stuck in the corner.
    """
    img, d = _new_layer()
    im = _asset(src, size, size)
    lw, lh = im.size[0] / S, im.size[1] / S
    x = (W - lw) / 2
    # default: just above the caption line. y_frac lifts it clear of a panel when the
    # speech is too dense to give the mark its own moment down there.
    base_y = 478 - lh if y_frac is None else H * y_frac
    y = base_y - 10 * (1 - spring(i, settle=9))
    img.paste(im, (int(x * S), int(y * S)), im)
    return _fade(Image.new("RGBA", img.size, (0, 0, 0, 0)), img, _chip_alpha(i, n))


def people(i, n, rows, kicker="Their organic reach", base=None):
    """Real LinkedIn profile cards on glass: actual avatar, name, headline, followers.

    The follower number counts up and lands, staggered per row, so it reads as a lookup
    happening live instead of a static credit.
    """
    img, d = _new_layer()
    fk, fn_, fh, fc = _f(11, MEDIUM), _f(17, BOLD), _f(12, MEDIUM), _f(14, BOLD)
    rh, gap, av = 56, 8, 42
    height = 30 + len(rows) * (rh + gap)
    top = 470 - height
    if base is not None:
        g, at = _glass(base, [PAD, top, W - PAD, top + height], radius=18, tint=0.88, blur=24)
        img.paste(g, at, g)
    d.rounded_rectangle([PAD, top, W - PAD, top + height], radius=18,
                        outline=(255, 255, 255, 190), width=1)
    d.text((PAD + 16, top + 21), kicker.upper(), font=fk, fill=(10, 10, 10, 150), anchor="ls")
    for r, row in enumerate(rows):
        ry = top + 28 + r * (rh + gap)
        live = spring(i, delay=r * 4, settle=11)
        if live <= 0.01:
            continue
        if row.get("avatar"):
            a = _avatar(row["avatar"], av)
            img.paste(a, (int((PAD + 14) * S), int((ry + 7) * S)), a)
        tx = PAD + 14 + av + 12
        d.text((tx, ry + 25), row["name"], font=fn_, fill=INK + (255,), anchor="ls")
        if row.get("headline"):
            d.text((tx, ry + 41), row["headline"][:34], font=fh, fill=(10, 10, 10, 145), anchor="ls")
        t = ease_out((i - PAYLOAD - r * 4) / 15.0)
        d.text((W - PAD - 16, ry + 34), f"{int(row['followers'] * t):,}",
               font=fc, fill=INK + (255,), anchor="rs")
        d.text((W - PAD - 16, ry + 48), "followers", font=fh, fill=(10, 10, 10, 130), anchor="rs")
    return _fade(Image.new("RGBA", img.size, (0, 0, 0, 0)), img,
                 int(255 * min(ease_out(i / 7.0), ease_out((n - i) / 7.0))))


def cards(i, n, items, kicker=None, base=None):
    """Glass cards that build one at a time as he names each source."""
    img, d = _new_layer()
    fk, ft, fs = _f(11, MEDIUM), _f(15, BOLD), _f(12, MEDIUM)
    ch, gap = 52, 8
    height = (26 if kicker else 6) + len(items) * (ch + gap)
    top = 470 - height
    for c, it in enumerate(items):
        cy = top + (30 if kicker else 6) + c * (ch + gap)
        live = spring(i, delay=c * 6, settle=11)
        if live <= 0.01:
            continue
        dx = 14 * (1 - live)
        box = [PAD + dx, cy, W - PAD + dx, cy + ch]
        if base is not None:
            g, at = _glass(base, box, radius=14, tint=0.86, blur=20)
            img.paste(g, at, g)
        on = i >= PAYLOAD + c * 6
        d.rounded_rectangle(box, radius=14,
                            outline=(ACCENT + (210,)) if on else (255, 255, 255, 185), width=1)
        d.text((PAD + 16 + dx, cy + 24), it["title"], font=ft, fill=INK + (255,), anchor="ls")
        if it.get("sub"):
            d.text((PAD + 16 + dx, cy + 41), it["sub"], font=fs, fill=(10, 10, 10, 150), anchor="ls")
    if kicker:
        d.text((PAD + 4, top + 18), kicker.upper(), font=fk, fill=(10, 10, 10, 160), anchor="ls")
    return _fade(Image.new("RGBA", img.size, (0, 0, 0, 0)), img,
                 int(255 * min(ease_out(i / 7.0), ease_out((n - i) / 7.0))))


def table(i, n, title, count, rows, columns=("COMPANY", "CONTACT", "SCORE")):
    """FULL-FRAME table — a genuine chapter break, not a lower third.

    Reserved for the one beat where the table IS the subject. Rows stream in the way the
    real product fills a table, so it reads as the app working rather than a screenshot.
    """
    img, d = _new_layer()
    fh, fc, fr = _f(17, BOLD), _f(10, MEDIUM), _f(14, MEDIUM)
    d.rectangle([0, 0, W, H], fill=(252, 252, 253, 255))
    top = int(H * 0.24)
    d.rounded_rectangle([PAD, top, W - PAD, top + 40 + len(rows) * 44 + 14], radius=16,
                        fill=SURFACE + (255,), outline=LINE + (255,), width=1)
    d.text((PAD + 18, top + 27), title, font=fh, fill=INK + (255,), anchor="ls")
    cnt = int(count * ease_out((i - PAYLOAD) / 18.0))
    d.text((W - PAD - 18, top + 27), f"{cnt:,} rows", font=fr, fill=MUTED + (255,), anchor="rs")
    d.line([PAD, top + 40, W - PAD, top + 40], fill=LINE + (255,), width=1)
    xs = (PAD + 18, PAD + 150, W - PAD - 52)
    for c, col in enumerate(columns):
        d.text((xs[c], top + 60), col, font=fc, fill=MUTED + (255,), anchor="ls")
    for r, row in enumerate(rows):
        ry = top + 74 + r * 44
        live = spring(i, delay=8 + r * 4, settle=10)
        if live <= 0.01:
            continue
        if r:
            d.line([PAD + 14, ry - 8, W - PAD - 14, ry - 8], fill=LINE + (255,), width=1)
        d.text((xs[0], ry + 18), row["company"], font=fr, fill=INK + (255,), anchor="ls")
        d.text((xs[1], ry + 18), row["contact"], font=fr, fill=MUTED + (255,), anchor="ls")
        d.ellipse([xs[2], ry + 11, xs[2] + 6, ry + 17], fill=ACCENT + (255,))
        d.text((xs[2] + 12, ry + 18), row["score"], font=fr, fill=INK + (255,), anchor="ls")
    return _fade(Image.new("RGBA", img.size, (0, 0, 0, 0)), img,
                 int(255 * min(ease_out(i / 8.0), ease_out((n - i) / 8.0))))


KINDS.update({"logo": logo, "people": people, "cards": cards, "table": table})


# ---------------------------------------------------------------------------
# Lovable clip, 2026-08-03 revision. Three primitives, written against review
# notes on the previous cut:
#
#   chips  <- `cards`  "smaller cards, left to right, just the titles, no green"
#   leads  <- `table`  "make it a real LinkedIn lead table with profile pics"
#   flow   <- (new)    "a flowchart: tier 1 to sales, tier 2 to a sequence"
#
# `flow` is the first primitive whose rows each land on their OWN cue, 12 seconds
# apart. See the nested-cue resolution in resolve_plan().
# ---------------------------------------------------------------------------

SURFACE_ALT = (245, 245, 247)      # BRAND.md --surface-alt #f5f5f7


def _wrap(d, text, font, maxw):
    """Greedy wrap, measured in LOGICAL px (the _SD proxy converts for us)."""
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = f"{cur} {w}".strip()
        if cur and d.textlength(t, font=font) > maxw:
            lines.append(cur)
            cur = w
        else:
            cur = t
    if cur:
        lines.append(cur)
    return lines


def chips(i, n, items=(), base=None):
    """A left-to-right ROW of small, title-only cards.

    Replaces the stacked `cards` panel on this clip. Four sources stacked vertically ate
    the lower half of the frame, and each card carried a subtitle that nobody reads in the
    1.3s it is on screen. A strip of four small chips carries the same list, keeps him on
    camera, and — because they land left to right — the build matches the order he says
    them in.

    Deliberately has NO accent. This is a list of nouns, not a result; BRAND.md spends the
    one green on the thing the viewer is meant to look at, and here that is his face.
    """
    img, d = _new_layer()
    ft = _f(10, MEDIUM)
    k = max(1, len(items))
    gap = 7
    cw = (W - 2 * PAD - gap * (k - 1)) / k
    ch = 58
    top = 470 - ch

    for c, it in enumerate(items):
        live = spring(i, delay=c * 4, settle=12)
        if live <= 0.01:
            continue
        x0 = PAD + c * (cw + gap)
        dy = 14 * (1 - live)                  # rises into place, springs, settles
        box = [x0, top + dy, x0 + cw, top + ch + dy]
        if base is not None:
            g, at = _glass(base, box, radius=12, tint=0.90, blur=20)
            img.paste(g, at, g)
        d.rounded_rectangle(box, radius=12, outline=(255, 255, 255, 200), width=1)

        lines = _wrap(d, it, ft, cw - 12)[:2]
        lh = 13
        y = top + dy + (ch - lh * (len(lines) - 1)) / 2 + 4
        for li, ln in enumerate(lines):
            d.text((x0 + cw / 2, y + li * lh), ln, font=ft,
                   fill=INK + (255,), anchor="ms")

    return _fade(Image.new("RGBA", img.size, (0, 0, 0, 0)), img,
                 int(255 * min(ease_out(i / 7.0), ease_out((n - i) / 7.0))))


def leads(i, n, title="", count=0, rows=(), kicker="LEAD", score_col="ICP",
          score_cue=None, _at_score=None):
    """A LinkedIn lead table that ENRICHES itself on screen.

    The previous `table` was a full-frame white card holding four company names. It read
    as a spreadsheet, not as leads, and it removed the presenter for five seconds to show
    almost nothing. Two changes, both from review:

    1. **Faces.** These are people scraped off LinkedIn, so the row is a person: profile
       picture, name, title at company. That single change is what makes a viewer read it
       as "leads from LinkedIn" rather than "a table".
    2. **It fills in.** Rows stream, and then each ICP score resolves a beat later — the
       cell sits blank with a scanning bar, then the grade lands. That two-stage build is
       the enrichment, and it is why this is a graphic rather than a screenshot.

    Panel, not full frame: it hangs off the same y=470 baseline as `people`, so the
    caption band underneath stays clear and he is still in shot.
    """
    img, d = _new_layer()
    ftitle, fcount, fcol = _f(14, BOLD), _f(11, MEDIUM), _f(9, MEDIUM)
    fname, fhead, fscore = _f(12, BOLD), _f(9, MEDIUM), _f(12, BOLD)

    rh, av = 44, 30
    height = 36 + 18 + len(rows) * rh + 10
    top = 470 - height
    _panel(d, top, height, radius=16)

    # header — title left, live row count right. THE one green is the pulse next to the
    # count: it is the only thing on the panel that means "this is running right now".
    d.text((PAD + 16, top + 24), title, font=ftitle, fill=INK + (255,), anchor="ls")
    # Never opens on "0 rows" — a table that is visibly full while its header claims it
    # is empty is a small lie the eye catches. The count-up starts already loaded, and it
    # climbs across most of the window rather than snapping in under a second: it is the
    # only thing moving between the rows arriving and the grades landing, and a panel
    # that sits perfectly still for three seconds reads as a screenshot.
    cnt = max(1, int(count * (0.15 + 0.85 * ease_out((i - PAYLOAD) / (n * 0.55)))))
    ctext = f"{cnt:,} rows"
    d.text((W - PAD - 16, top + 24), ctext, font=fcount, fill=MUTED + (255,), anchor="rs")
    pw = d.textlength(ctext, font=fcount)
    pulse = 2.0 + 0.9 * math.sin(i / 5.0)
    d.ellipse([W - PAD - 22 - pw - pulse, top + 20 - pulse,
               W - PAD - 22 - pw + pulse, top + 20 + pulse], fill=ACCENT + (255,))

    d.line([PAD, top + 36, W - PAD, top + 36], fill=LINE + (255,), width=1)
    d.text((PAD + 16, top + 50), kicker.upper(), font=fcol, fill=MUTED + (255,), anchor="ls")
    d.text((W - PAD - 16, top + 50), score_col.upper(), font=fcol,
           fill=MUTED + (255,), anchor="rs")

    for r, row in enumerate(rows):
        ry = top + 54 + r * rh
        live = spring(i, delay=8 + r * 7, settle=11)
        if live <= 0.01:
            continue
        dx = 10 * (1 - live)
        if r:
            d.line([PAD + 14, ry, W - PAD - 14, ry], fill=LINE + (255,), width=1)
        if row.get("avatar"):
            a = _avatar(row["avatar"], av)
            img.paste(a, (int((PAD + 14 + dx) * S), int((ry + 7) * S)), a)
        tx = PAD + 14 + av + 10 + dx
        d.text((tx, ry + 22), row["name"], font=fname, fill=INK + (255,), anchor="ls")
        if row.get("headline"):
            d.text((tx, ry + 34), row["headline"][:32], font=fhead,
                   fill=MUTED + (255,), anchor="ls")

        # The enrichment beat: the cell scans, then the grade lands. Anchored to
        # `score_cue` when the plan gives one, because the grades ARE the payoff and they
        # have to arrive on "score them against their ICP" — not four seconds early on
        # the panel's own entrance, which is where a fixed offset put them.
        base_at = PAYLOAD + 14 if _at_score is None else _at_score
        st = i - (base_at + r * 7)
        cx1, cy0, cy1 = W - PAD - 14, ry + 11, ry + 33
        cw_ = 30
        if st < 0:
            d.rounded_rectangle([cx1 - cw_, cy0, cx1, cy1], radius=7,
                                fill=SURFACE_ALT + (255,))
            bw = 10 + 4 * math.sin(i / 3.0)
            mx = (cx1 - cw_ / 2)
            d.rounded_rectangle([mx - bw / 2, cy0 + 9, mx + bw / 2, cy0 + 12],
                                radius=2, fill=LINE + (255,))
        else:
            pop = 2.0 * math.exp(-st / 3.0) * math.cos(st * 0.9)
            d.rounded_rectangle([cx1 - cw_ - pop, cy0 - pop, cx1 + pop, cy1 + pop],
                                radius=7, fill=SURFACE_ALT + (255,))
            tone = _lerp(SURFACE_ALT, INK, ease_out(st / 7.0))
            d.text((cx1 - cw_ / 2, cy1 - 7), str(row.get("score", "A")),
                   font=fscore, fill=tone + (255,), anchor="ms")

    return _fade(Image.new("RGBA", img.size, (0, 0, 0, 0)), img,
                 int(255 * min(ease_out(i / 8.0), ease_out((n - i) / 8.0))))


def flow(i, n, lanes=(), kicker="", source=""):
    """A routing FLOWCHART whose lanes each land on their own cue.

    Everything else in this engine fires one graphic per phrase. This beat is twelve
    seconds of one idea — the table splits three ways — so it gets the tier-board shape
    instead: the board is up for the whole beat, and each lane fills the instant he names
    it. A viewer watches the routing get decided.

    Built to the /process-flowchart component language: badge, orthogonal connector with
    an arrowhead, destination node, real provider tiles in the node that has channels.
    The connector DRAWS left to right rather than fading, because a wire that fades in is
    a picture of a flowchart and a wire that draws is a flowchart.

    One focal emerald, on the lane marked `focal` — tier 1, the only lane where a human
    picks the lead up. Everything else is ink, surface and line.
    """
    img, d = _new_layer()
    fk, fb, ft, fs = _f(9, MEDIUM), _f(9, BOLD), _f(13, BOLD), _f(9, MEDIUM)

    lh, gap = 62, 6
    head = 34 if (kicker or source) else 8
    height = head + len(lanes) * lh + (len(lanes) - 1) * gap + 12
    top = 470 - height
    _panel(d, top, height, radius=16)

    if kicker or source:
        d.text((PAD + 16, top + 22), kicker.upper(), font=fk, fill=MUTED + (255,), anchor="ls")
        if source:
            d.text((W - PAD - 16, top + 22), source, font=fk, fill=MUTED + (255,), anchor="rs")
        d.line([PAD, top + 32, W - PAD, top + 32], fill=LINE + (255,), width=1)

    bx0, bx1 = PAD + 14, PAD + 60          # badge
    wx0, wx1 = PAD + 66, PAD + 96          # connector run
    dx0, dx1 = PAD + 100, W - PAD - 14     # destination node

    for li, lane in enumerate(lanes):
        ly = top + head + li * (lh + gap)
        at = int(lane.get("_at", li * 30))
        t = i - at
        fill = ease_out(t / 9.0)            # 0 before the cue, 1 after it lands
        focal = bool(lane.get("focal"))
        on = fill > 0.02

        # badge — pending is line-grey, live is ink (emerald on the focal lane)
        edge = _lerp(LINE, ACCENT if focal else INK, fill)
        d.rounded_rectangle([bx0, ly + 18, bx1, ly + 44], radius=7,
                            outline=edge + (255,), width=1)
        d.text(((bx0 + bx1) / 2, ly + 35), lane.get("badge", ""), font=fb,
               fill=_lerp(LINE, INK, fill) + (255,), anchor="ms")

        # connector — draws left to right, arrowhead once it arrives
        cy = ly + 31
        p = ease_out(t / 10.0)
        if p > 0.01:
            xe = wx0 + (wx1 - wx0) * p
            wcol = _lerp(LINE, ACCENT if focal else MUTED, fill)
            d.line([wx0, cy, xe, cy], fill=wcol + (255,), width=1)
            if p > 0.85:
                d.line([xe - 4, cy - 3, xe, cy], fill=wcol + (255,), width=1)
                d.line([xe - 4, cy + 3, xe, cy], fill=wcol + (255,), width=1)
        else:
            d.line([wx0, cy, wx1, cy], fill=LINE + (255,), width=1)

        # destination node
        slide = 6 * (1 - spring(t, settle=11)) if on else 6
        nb = [dx0 + slide, ly + 8, dx1 + slide, ly + 54]
        ncol = _lerp(LINE, ACCENT, fill) if focal else LINE
        d.rounded_rectangle(nb, radius=11, outline=ncol + (255,), width=1)

        tiles = lane.get("tiles") or []
        # Channel tiles sit on the SAME line as the label, right-aligned, instead of
        # stacked under it. Stacked they had 17 logical px of headroom and rendered as
        # three unreadable smudges — the whole point of the lane is that a viewer can
        # name the channels. Beside the label they get 24px and read cleanly.
        d.text((dx0 + 14 + slide, ly + 36), lane.get("to", ""), font=ft,
               fill=_lerp(LINE, INK, fill) + (255,), anchor="ls")
        if tiles:
            tw, tg = 24, 6
            span = len(tiles) * tw + (len(tiles) - 1) * tg
            tx0 = dx1 + slide - 12 - span
            for k, src in enumerate(tiles):
                tl = ease_out((t - 6 - k * 3) / 8.0)
                if tl <= 0.02:
                    continue
                im = _asset(src, tw, tw)
                tile = im if tl >= 0.99 else _dim(im, tl)
                img.paste(tile, (int((tx0 + k * (tw + tg)) * S), int((ly + 19) * S)), tile)
        elif lane.get("sub"):
            d.text((dx0 + 14 + slide, ly + 47), lane["sub"], font=fs,
                   fill=_lerp(LINE, MUTED, fill) + (255,), anchor="ls")

    return _fade(Image.new("RGBA", img.size, (0, 0, 0, 0)), img,
                 int(255 * min(ease_out(i / 8.0), ease_out((n - i) / 8.0))))


def _dim(im, a):
    """Fade a pasted asset by scaling ITS alpha channel — never by drawing it at partial
    alpha, which would punch through the panel underneath (see _new_layer)."""
    out = im.copy()
    out.putalpha(out.getchannel("A").point(lambda v: int(v * max(0.0, min(a, 1.0)))))
    return out


KINDS.update({"chips": chips, "leads": leads, "flow": flow})
