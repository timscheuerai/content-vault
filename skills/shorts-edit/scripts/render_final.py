#!/usr/bin/env python3
"""Single-pass render: cut + captions + audio, ONE video encode, straight from the raw.

VIDEO — one encode, or you lose the image
-----------------------------------------
OBS screen captures are often already heavily compressed (~246 kbps in the reference
session). A second generation visibly softens them. Measured SSIM vs the source frames:

    1 encode  (CRF 18)                        0.9962
    2 encodes (re-encode to burn captions)    0.9767   <- what "the quality dropped" was
    1 encode  (CRF 12, everything one graph)  0.9983

So trim -> concat -> overlay -> encode all happen in a single filtergraph. Never
re-encode a finished clip just to add something to it.

AUDIO — two traps, both silent
------------------------------
These recordings sit near -43 LUFS and need ~+26 dB. That fact causes both traps.

TRAP A: `loudnorm` with linear=true promises a constant gain and SILENTLY BREAKS THAT
PROMISE whenever the required gain would push the true peak past the ceiling — which +26
dB does. It falls back to dynamic mode: per-frame gain riding, i.e. pumping and breathing.
This, not the denoiser, was the main cause of "the audio sounds artificial".
Fix: never use loudnorm for gain. Measure the true peak, apply ONE constant `volume=XdB`
that lands it at TARGET_TP. Verified pure: correlation 0.999975 with the source waveform.

TRAP B: blind denoising sounds fake. `afftdn` with `tn=1` GUESSES the noise spectrum
moment to moment; guessing wrong is exactly what makes musical burbling. Instead LEARN the
noise from real silence in the take itself (`asendcmd ... sn start/stop`) and remove that.
Measured (on silence it did not learn from): highpass 11.2 dB, RNNoise 17.6 dB,
learned print nr=12 **23.0 dB** — all at -0.1 dB speech level.

ORDERING IS LOAD-BEARING:
  * The denoiser must run BEFORE the trims. Its sample window points at silence in the
    ORIGINAL take, and the edit throws that silence away. Applied after the cut, the
    asendcmd never fires and afftdn quietly reverts to blind mode — the artificial sound.
  * Gain must precede ANY denoiser. RNNoise is trained on speech at normal levels; fed
    -68 dBFS audio it sees silence and does literally nothing.
"""
import json
import re
import subprocess
from pathlib import Path

from paths import RAW, CLIPS, TIGHT, FPS, OUT_W, OUT_H, S

CRF = "6"            # not 12. Measured vs source: CRF12=0.9983 SSIM, CRF6=0.9993,
                     # lossless=1.0. CRF6 is essentially transparent and gives the
                     # platform's own re-encoder a cleaner input to work from.
PRESET = "slow"
FADE = 0.03          # 30ms at every segment edge — prevents an audible pop at each cut
TARGET_TP = -1.5     # constant gain lands the true peak here; no limiter ever engages

MODELS = Path.home() / "Developer/video-use/models"   # optional, for the rnn* modes

AUDIO_MODES = {
    "none": "volume={g}dB",                            # original tone, gain only
    "hp":   "highpass=f=60:poles=2,volume={g}dB",      # + infrasonic rumble removed
    "rnn":  "highpass=f=60:poles=2,volume={g}dB,arnndn=m=" + str(MODELS / "sh.rnnn"),
    # print<N> modes are built per-clip by noise_print() — they need the silence window
}
# Chosen by ear on headphones, 2026-07-11: NO denoiser.
#
# Every spectral denoiser (afftdn, RNNoise) reconstructs the signal rather than merely
# attenuating it, and on headphones that reconstruction is audible as an unnatural tone —
# even a learned noise print at nr=12, even blended 50/50. Tim listened to all of them and
# picked the honest one. The background sits ~9 dB below where it started (the 12Hz rumble
# is gone) and the voice is a mathematically pure scaled copy of the original.
#
# If a future take is noisier and needs it, print12@50 was the best-sounding compromise.
DEFAULT_AUDIO = "hp"


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-2000:])
        raise SystemExit("ffmpeg failed")
    return r


def src_for(name: str) -> Path:
    return next(RAW.glob(f"{name}.*"))


def find_silence(src: Path, min_len=0.8):
    """Longest silent stretch in the RAW take — the noise print is learned from here."""
    err = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(src),
         "-af", f"silencedetect=noise=-55dB:d={min_len}", "-f", "null", "-"],
        capture_output=True, text=True).stderr
    ss = [float(m) for m in re.findall(r"silence_start: ([\d.]+)", err)]
    ee = [float(m) for m in re.findall(r"silence_end: ([\d.]+)", err)]
    best, blen = None, 0.0
    for i, s in enumerate(ss):
        if i >= len(ee):
            break
        a, b = s + 0.15, ee[i] - 0.15       # trim edges: don't catch a word tail or breath
        if b - a > blen:
            best, blen = (a, b), b - a
    return best


def noise_print(src: Path, gain: float, nr=12, wet=1.0, hp=True) -> str:
    """afftdn with a profile learned from this take's own silence.

    `wet` blends the denoised signal back with the dry one. Spectral subtraction ALWAYS
    leaves some texture — it is reconstructing, not just attenuating — and on headphones
    that texture is audible even at nr=12. Blending is the honest lever: at wet=0.7 you
    keep ~70% of the noise reduction and only 70% of the artifact, and critically the
    dry signal (which is the real voice, untouched) dominates the character of the tone.
    """
    win = find_silence(src)
    if not win:
        raise SystemExit(f"no silence long enough to learn a noise print in {src.name}")
    a, b = win
    pre = "highpass=f=60:poles=2," if hp else ""
    den = (f"asendcmd={a:.2f} afftdn sn start,asendcmd={b:.2f} afftdn sn stop,"
           f"afftdn=nr={nr}:nf=-40")
    if wet >= 0.999:
        return f"{pre}volume={gain:.2f}dB,{den}"
    return (f"{pre}volume={gain:.2f}dB,asplit[dry][w];"
            f"[w]{den}[wet];"
            f"[dry]volume={1 - wet:.2f}[d2];[wet]volume={wet:.2f}[w2];"
            f"[d2][w2]amix=inputs=2:normalize=0")


def segment_graph(ranges, pre_audio=None, zooms=None):
    """trim/concat both streams; 30ms fades per segment.

    `pre_audio` is applied to the FULL audio BEFORE the trims — load-bearing for the
    noise print (see module docstring).
    `zooms` is one scale factor per segment; the punch-in happens inside the same encode.
    """
    n = len(ranges)
    parts = []
    if pre_audio:
        taps = "".join(f"[ap{i}]" for i in range(n))   # a named link is consumed once
        parts.append(f"[0:a]{pre_audio},asplit={n}{taps}")
        src = lambda i: f"[ap{i}]"
    else:
        src = lambda i: "[0:a]"

    for i, r in enumerate(ranges):
        s, e = float(r["start"]), float(r["end"])
        d = e - s
        vf = f"[0:v]trim=start={s:.3f}:end={e:.3f},setpts=PTS-STARTPTS"
        z = ""
        if zooms:
            from polish import zoom_filter
            z = zoom_filter(zooms[i], round(d * FPS),    # drift completes across the segment
                            w=OUT_W, h=OUT_H)
        # Master at OUT (1080x1920): the source's ONE upscale happens here, inside the
        # single encode — zoomed segments upscale inside zoom_filter's own graph, wide
        # segments here. The overlay PNGs are rasterized at OUT, so type stays native-
        # resolution sharp instead of being upscaled with the video.
        vf += ("," + z) if z else f",scale={OUT_W}:{OUT_H}:flags=lanczos"
        # concat demands identical size AND sample-aspect-ratio across inputs. scale
        # rewrites SAR, so a zoomed segment stops matching an un-zoomed one and concat
        # refuses to configure. Pin it on every segment.
        vf += ",setsar=1"
        parts.append(f"{vf}[v{i}]")

        # Fades ONLY at real cut edges. A chunk boundary (a mid-beat framing change) is not
        # a cut — the audio runs straight through it. Fading there would dip the voice
        # mid-sentence, which is audible and reads as a glitch.
        fin = r.get("fade_in", True)
        fout = r.get("fade_out", True)
        af = [f"{src(i)}atrim=start={s:.3f}:end={e:.3f},asetpts=PTS-STARTPTS"]
        if fin:
            af.append(f"afade=t=in:st=0:d={FADE}")
        if fout:
            af.append(f"afade=t=out:st={max(0.0, d - FADE):.3f}:d={FADE}")
        parts.append(",".join(af) + f"[a{i}]")

    # concat wants inputs INTERLEAVED per segment: v0,a0,v1,a1,... Passing all the video
    # pads then all the audio pads is identical when n==1, so a single-segment test clip
    # will happily hide the bug.
    pads = "".join(f"[v{i}][a{i}]" for i in range(n))
    parts.append(f"{pads}concat=n={n}:v=1:a=1[vc][ac]")
    return parts


def measure_tp(name, ranges, prefilter) -> float:
    """True peak of the CUT audio, with the pre-gain filters applied. Audio-only graph:
    the full graph's video output would sit unconnected."""
    parts, al = [], []
    for i, r in enumerate(ranges):
        s, e = float(r["start"]), float(r["end"])
        d = e - s
        parts.append(
            f"[0:a]atrim=start={s:.3f}:end={e:.3f},asetpts=PTS-STARTPTS,"
            f"afade=t=in:st=0:d={FADE},afade=t=out:st={max(0.0, d - FADE):.3f}:d={FADE}[a{i}]")
        al.append(f"[a{i}]")
    parts.append(f"{''.join(al)}concat=n={len(ranges)}:v=0:a=1[ac]")
    chain = f"{prefilter}," if prefilter else ""
    parts.append(f"[ac]{chain}loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json[m]")
    err = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(src_for(name)),
         "-filter_complex", ";".join(parts), "-map", "[m]", "-f", "null", "-"],
        capture_output=True, text=True).stderr
    i, j = err.rfind("{"), err.rfind("}")
    if i < 0:
        print(err[-1200:])
        raise SystemExit("loudness measurement failed")
    return float(json.loads(err[i:j + 1])["input_tp"])


def render(name, audio_mode=DEFAULT_AUDIO, frames=None, suffix="_final",
           zooms=None, sfx_wav=None, chunks=None, progress=False) -> Path:
    ranges = json.loads((TIGHT / f"{name}.json").read_text())["ranges"]
    src = src_for(name)
    # chunks are the ranges re-cut for pattern interrupts; the audio timeline is identical
    render_ranges = chunks or ranges

    prefilter = "" if audio_mode == "none" else "highpass=f=60:poles=2"
    tp = measure_tp(name, render_ranges, prefilter)
    gain = TARGET_TP - tp

    if audio_mode.startswith("print"):
        # print<NR>[@<wet%>]   e.g. print12, print12@70
        spec = audio_mode[len("print"):]
        nr_s, _, wet_s = spec.partition("@")
        nr = int(nr_s or 12)
        wet = (float(wet_s) / 100.0) if wet_s else 1.0
        chain = noise_print(src, gain, nr=nr, wet=wet)
    else:
        chain = AUDIO_MODES[audio_mode].format(g=f"{gain:.2f}")

    zoom_list = [c["zoom"] for c in chunks] if chunks else zooms
    parts = segment_graph(render_ranges, pre_audio=chain, zooms=zoom_list)

    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src)]
    total = sum(float(r["end"]) - float(r["start"]) for r in ranges)
    # A thin progress bar. Cheap, and it tells the viewer "you're nearly there" — which is
    # what lifts completion rate. drawbox, so it costs no per-frame PNGs.
    bar = (f",drawbox=x=0:y=0:w='iw*t/{total:.3f}':h={3 * S}:color=0x10b981@0.85:t=fill"
           if progress else "")
    if frames:
        cmd += ["-framerate", str(FPS), "-i", str(frames / "f_%06d.png")]
        parts.append(f"[vc][1:v]overlay=0:0:format=auto{bar},format=yuv420p[vout]")
    else:
        parts.append(f"[vc]format=yuv420p{bar}[vout]")

    if sfx_wav:
        # normalize=0 so the voice keeps its own level — amix would otherwise halve it.
        #
        # aformat on BOTH inputs is load-bearing. amix negotiates a common channel layout,
        # and a MONO sfx bed makes it pick mono — which silently downmixes the stereo voice
        # and pushed the peak from -1.6 dB to +0.8 dB (clipping). Pin stereo on both sides
        # and the voice passes through untouched.
        cmd += ["-i", str(sfx_wav)]
        idx = 2 if frames else 1
        fmt = "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo"
        parts.append(f"[ac]aresample=48000,{fmt}[voice]")
        parts.append(f"[{idx}:a]{fmt}[sfx]")
        parts.append("[voice][sfx]amix=inputs=2:normalize=0:duration=first[aout]")
    else:
        parts.append("[ac]aresample=48000[aout]")

    CLIPS.mkdir(parents=True, exist_ok=True)
    out = CLIPS / f"{name}{suffix}.mp4"
    run(cmd + [
        "-filter_complex", ";".join(parts),
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", PRESET, "-crf", CRF,
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-colorspace", "bt709", "-color_primaries", "bt709",
        "-color_trc", "bt709", "-color_range", "tv",
        "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
        "-movflags", "+faststart", str(out),
    ])
    print(f"    audio: {audio_mode} | TP {tp:.1f} dB -> gain {gain:+.1f} dB "
          f"-> peak {TARGET_TP} dB, no limiting")
    return out
