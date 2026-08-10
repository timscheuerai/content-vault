#!/usr/bin/env python3
"""transcripts/*.json -> words/<name>.md : every word with its start, plus [GAP] markers.

The packed/phrase view breaks only on silences >= 0.5s, which HIDES retakes: the speaker
restarts a sentence after a 0.3s breath and it reads as one phrase. The editor needs word
boundaries to cut those, so this exposes every word and every gap >= 0.25s.

Only word START times appear here. Word END times from ASR are not trustworthy (see
reference/PROCESS.md §2) and must never be used to reason about silence.
"""
import json

from paths import TRANSCRIPTS, WORDS


def main():
    WORDS.mkdir(parents=True, exist_ok=True)
    for tp in sorted(TRANSCRIPTS.glob("*.json")):
        d = json.loads(tp.read_text())
        words = [w for w in d.get("words", []) if w.get("type") == "word"]
        lines = [f"# {tp.stem}  ({d.get('audio_duration_secs', 0):.1f}s, {len(words)} words)", ""]
        buf, prev_end = [], None

        def flush():
            if buf:
                lines.append("  " + " ".join(buf))
                buf.clear()

        for w in words:
            s, e, t = w["start"], w["end"], w["text"].strip()
            if prev_end is not None and s - prev_end >= 0.25:
                flush()
                lines.append(f"[GAP {s - prev_end:.2f}s]  (silence {prev_end:.2f} -> {s:.2f})")
            buf.append(f"{t}<{s:.2f}>")
            prev_end = e
        flush()
        (WORDS / f"{tp.stem}.md").write_text("\n".join(lines) + "\n")
        print(f"  + {tp.stem}: {len(words)} words")
    print(f"\nwrote -> {WORDS}")


if __name__ == "__main__":
    main()
