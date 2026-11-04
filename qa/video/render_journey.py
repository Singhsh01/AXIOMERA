"""Renders the demo journey from journey_capture.py output: one encoded file per frame (slow push-in,
crossfade from the previous frame inside the file), joined with the concat demuxer.

    python qa/video/render_journey.py FRAMES_DIR OUT.mp4
"""
import json, os, subprocess, sys
from pathlib import Path

src, out = Path(sys.argv[1]), Path(sys.argv[2])
tl = json.loads((src / "timeline.json").read_text())
work = src / "render"; work.mkdir(exist_ok=True)
FPS, X, Z = 30, 0.45, 0.03
ENC = ["-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-r", str(FPS)]

def zp(n):
    return f"zoompan=z='1+{Z}*on/({n}-1)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={n}:s=1280x800:fps={FPS},setsar=1"

parts = []
for i, (f, secs) in enumerate(tl):
    n = round(secs * FPS)
    tmp, final = work / f"tmp_{i:02d}.mp4", work / f"s_{i:02d}.mp4"
    if i == 0:
        vf = f"{zp(n)},fade=t=in:st=0:d=0.5:color=black,format=yuv420p"
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(src / f), "-vf", vf, *ENC, str(tmp)]
    else:
        prev = tl[i - 1][0]; xn = round(X * FPS)
        tail = f",fade=t=out:st={secs - 0.6:.2f}:d=0.6:color=black" if i == len(tl) - 1 else ""
        fc = (f"[0]zoompan=z='1+{Z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={xn}:s=1280x800:fps={FPS},setsar=1,format=yuv420p[a];"
              f"[1]{zp(n)},format=yuv420p[b];[a][b]xfade=transition=fade:duration={X}:offset=0,trim=duration={secs}{tail}")
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(src / prev), "-framerate", str(FPS), "-i", str(src / f),
               "-filter_complex", fc, *ENC, str(tmp)]
    subprocess.run(cmd, check=True)
    os.replace(tmp, final); parts.append(final)
(work / "list.txt").write_text("".join(f"file '{p.name}'\n" for p in parts))
tmp = out.with_suffix(".tmp.mp4")
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(work / "list.txt"), "-c", "copy", "-movflags", "+faststart", str(tmp)], check=True)
os.replace(tmp, out)
print(out, subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)], capture_output=True, text=True).stdout.strip(), "s")
