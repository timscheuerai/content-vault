# BRAND.md — motion graphics tokens

This is the default token table `brand_lint.py` checks the renderers against. **Edit it to
your brand**, or point `SHORTS_BRAND_MD` at the BRAND.md you already keep somewhere else:

```bash
export SHORTS_BRAND_MD=~/my-company/brand/BRAND.md
```

The lint parses the table below by regex and fails on any drift between it and the
constants in `scripts/motion.py` / `scripts/tierboard.py` / `scripts/caption_render.py`.
So changing a colour here is step one; the lint then tells you which constant to follow.

## Colour

| Token | Hex | Used for |
|---|---|---|
| `--surface` | `#ffffff` | card and panel backgrounds |
| `--surface-alt` | `#f5f5f7` | the recessed fill inside a panel |
| `--ink` | `#0a0a0a` | primary type. Near-black, never pure black |
| `--muted` | `#71717a` | kickers, labels, secondary type |
| `--line` | `#e4e4e7` | 1px hairlines. Panels get a line, not a shadow |
| `--accent` | `#10b981` | **the one green** |

## The one-accent rule

> `--accent` is the one green. Use sparingly.

Exactly one accent element per graphic. This is the rule the lint enforces that no type
checker can: it renders every motion primitive, finds pixels within tolerance of
`--accent`, counts connected blobs, and fails on two. A second green element is not a
bug in the code, it is a brand violation — the accent means "look here", and two of them
mean nothing.

## Type

```css
--font-sans: 'Helvetica Neue';
```

Captions render Medium, lowercase, 18 logical px, tracking −1, no stroke. Swap the face
with `SHORTS_FONT` (see `scripts/assets.py`) and update the value above so the lint
agrees.
