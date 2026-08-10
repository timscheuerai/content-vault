#!/usr/bin/env python3
"""CI for video.

Video CI is not software CI: the artifact is huge and partly subjective. But the INPUTS are
tiny text (EDLs, motion plans, word fixes) and the PIPELINE is code. So:

    version the DECISIONS, not the pixels.

A clip is fully reproducible from (raw hash + EDL + plan + script version). This runner
stamps all of that into a manifest, runs the gate, and compares the numbers against a
committed GOLDEN baseline. That is what makes it CI rather than a script: it fails when a
change to the pipeline silently degrades output that still "looks fine".

    python ci.py                  # build (if stale) + gate + brand lint + manifest
    python ci.py --check          # also fail on any REGRESSION vs edit/ci_golden.json
    python ci.py --bless          # accept the current numbers as the new golden

What the golden protects against, concretely: refactoring polish.py and losing the 30ms
fades; bumping a filter and dropping SSIM from 0.998 to 0.977; a caption change that only
breaks 3-frame words. All of these passed human review before.
"""
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from paths import PROJ, RAW, CLIPS, TIGHT, EDIT

S = Path(__file__).parent
GOLDEN = EDIT / "ci_golden.json"
MANIFEST = EDIT / "ci_manifest.json"

# the numbers a regression must not cross
TOL = {"ssim": -0.002, "leak_pct": +2.0, "clipped": 0}


def sha(p: Path, n=1 << 20) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(n):
            h.update(chunk)
    return h.hexdigest()[:16]


def script_version() -> str:
    """One hash over every script — the pipeline's version. If this changes and the numbers
    change, you know exactly why."""
    h = hashlib.sha256()
    for f in sorted(S.glob("*.py")):
        if f.name in ("ci.py",):
            continue
        h.update(f.read_bytes())
    return h.hexdigest()[:16]


def run(script, *args):
    r = subprocess.run([sys.executable, str(S / script), *args],
                       capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def parse_qa(out):
    """Pull the numbers out of the gate so they can be compared, not just eyeballed."""
    import re
    d = {}
    m = re.search(r"SSIM vs source ([\d.]+)", out)
    if m:
        d["ssim"] = float(m.group(1))
    m = re.search(r"dead-air (\d+)% of runtime", out)
    if m:
        d["leak_pct"] = float(m.group(1))
    m = re.search(r"(\d+) clipped", out)
    if m:
        d["clipped"] = int(m.group(1))
    m = re.search(r"peak ([-+\d.]+) dBFS", out)
    if m:
        d["peak_db"] = float(m.group(1))
    d["gate"] = "PASS" if "QA GATE: PASS" in out else "FAIL"
    return d


def main():
    check = "--check" in sys.argv
    bless = "--bless" in sys.argv
    names = [a for a in sys.argv[1:] if not a.startswith("--")] or \
            [p.stem for p in sorted(TIGHT.glob("*.json"))]

    print(f"pipeline version: {script_version()}")
    print(f"project: {PROJ.name}\n")

    man = {
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pipeline_version": script_version(),
        "clips": {},
    }
    failed = []

    rc, out = run("brand_lint.py")
    print(out.strip().splitlines()[-1])
    man["brand"] = "conformant" if rc == 0 else "VIOLATION"
    if rc != 0:
        failed.append("brand")

    for n in names:
        clip = CLIPS / f"{n}_final.mp4"
        print(f"\n--- {n}")
        if not clip.exists():
            print("  building…")
            rc, out = run("build.py", n, "--polish")
            if rc != 0:
                print(out[-600:])
                failed.append(f"{n}: build")
                continue

        rc, out = run("qa.py", n)
        res = parse_qa(out)
        for line in out.splitlines():
            if "[FAIL]" in line:
                print(" " + line.strip())
        print(f"  gate={res['gate']}  ssim={res.get('ssim')}  "
              f"leak={res.get('leak_pct')}%  peak={res.get('peak_db')}dB")
        if rc != 0:
            failed.append(f"{n}: gate")

        man["clips"][n] = {
            **res,
            "source_sha": sha(next(RAW.glob(f"{n}.*"))),
            "edl_sha": sha(TIGHT / f"{n}.json"),
            "output_sha": sha(clip) if clip.exists() else None,
        }

    MANIFEST.write_text(json.dumps(man, indent=2))
    print(f"\nmanifest -> {MANIFEST.relative_to(PROJ)}")

    if bless:
        GOLDEN.write_text(json.dumps(man, indent=2))
        print(f"golden  -> {GOLDEN.relative_to(PROJ)}  (blessed)")
        return 0

    if check:
        if not GOLDEN.exists():
            print("\nno golden baseline — run: python ci.py --bless")
            return 1
        g = json.loads(GOLDEN.read_text())
        print("\n--- regression check vs golden "
              f"(pipeline {g['pipeline_version']} -> {man['pipeline_version']})")
        regressed = 0
        for n, cur in man["clips"].items():
            old = g["clips"].get(n)
            if not old:
                print(f"  new clip: {n}")
                continue
            for k, tol in TOL.items():
                if k not in cur or k not in old:
                    continue
                delta = cur[k] - old[k]
                bad = delta < tol if tol < 0 else delta > tol
                if bad:
                    print(f"  REGRESSION {n}: {k} {old[k]} -> {cur[k]} ({delta:+.4g})")
                    regressed += 1
        print("  no regressions" if not regressed else f"  {regressed} REGRESSION(S)")
        if regressed:
            failed.append("regression")

    print("\n" + "=" * 60)
    print("CI: PASS" if not failed else f"CI: FAIL — {', '.join(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
