"""Faithful, shareable action overlays for recorded policy rollouts.

Usage: python -m astra_manipulation.media RUN --output DIRECTORY --title TITLE
"""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import textwrap

import imageio.v2 as imageio
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps


def read_json(path):
    return json.loads(Path(path).read_text())


def load_calls(run):
    calls = []
    for folder in sorted(Path(run).glob("call_*")):
        if not (folder / "response.json").exists():
            continue
        response = read_json(folder / "response.json")
        calls.append({"name": folder.name, "step": int(read_json(folder / "input.json")["observation"]["step_index"]),
                      **response})
    return calls


def executed_call(calls, step):
    """Frame zero is reset; an action at input k first appears in frame k+1."""
    for call in reversed(calls):
        decision = call["decision"]
        if call["step"] < step:
            if not decision["done"] and step <= call["step"] + decision["repeat"]:
                return call
            return None
    return None


def outcome(result):
    if result.get("error") or result.get("status") == "error":
        return "ERROR / incomplete trial", "#f8a55b"
    if result.get("success_any_step"):
        suffix = "criterion met at final frame" if result.get("success_final_step") else "criterion not met at final frame"
        return f"SUCCESS observed ({suffix})", "#69e0ab"
    if result.get("status") == "budget_exhausted":
        return "BUDGET EXHAUSTED / no success observed", "#f8cf6b"
    return "NO SUCCESS observed / " + str(result.get("status", "unknown")), "#ff9199"


def font(size, mono=False):
    name = "DejaVuSansMono.ttf" if mono else "DejaVuSans.ttf"
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/" + name, size)
    except OSError:
        return ImageFont.load_default(size=size)


def panel(config, spec, result, call, title, duration, source_duration):
    canvas = Image.new("RGB", (1920, 1536), "#101825")
    draw = ImageDraw.Draw(canvas)
    title_font = font(40)
    if title_font.getlength(title) > 1260:
        title_font = font(max(18, int(40 * 1260 / title_font.getlength(title))))
    draw.text((36, 18), title, font=title_font, fill="#f1f6ff")
    for i, line in enumerate(textwrap.wrap(config.get("instruction", ""), 108)[:2]):
        draw.text((36, 66 + 36 * i), line, font=font(30), fill="#bcd0ea")
    label, color = outcome(result)
    draw.text((36, 928), "Episode result: " + label, font=font(30), fill=color)
    speed = source_duration / duration
    draw.text((36, 973), f"Simulation playback {speed:.3f}x | {source_duration:.2f}s simulated / {duration:.2f}s video"
              " | request waits omitted", font=font(26), fill="#bcd0ea")
    if call:
        decision, metadata = call["decision"], call.get("metadata", {})
        latency = metadata.get("latency_seconds")
        latency_text = f"{latency:.2f}s" if isinstance(latency, (int, float)) else "unreported"
        draw.text((36, 1015), f"{call['name']} | request latency {latency_text} | repeat={decision['repeat']}"
                  f" | done={str(decision['done']).lower()}", font=font(30), fill="#69d6ee")
        draw.text((36, 1062), "Executed action (Astra JSON; named coordinates, normalized controls)",
                  font=font(28), fill="#f1f6ff")
        names = spec.get("names", [])
        action = decision["action"]
        rows = max(1, (len(action) + 2) // 3)
        for index, value in enumerate(action):
            column, row = divmod(index, rows)
            name = names[index] if index < len(names) else f"action[{index}]"
            # repr preserves the exact recorded number; no rounding or invented intent.
            line = f"{index:02d} {name}: {value!r}"
            size = min(28, max(14, int(570 / max(len(line), 1) / .61)))
            draw.text((36 + column * 630, 1110 + row * 35), line, font=font(size, True), fill="#e3ecfb")
    else:
        draw.text((36, 1015), "Initial observation / no executed action", font=font(34), fill="#69d6ee")
    draw.text((36, 1500), "Camera observations + robot proprioception | requested model: " +
              str(config.get("requested_model", "unreported")), font=font(25), fill="#8faac8")
    return canvas


def make_gif(movie, target, duration, max_bytes=8_000_000):
    """Palette quantization, bounded size, and a full-episode timeline compressed to <=20s."""
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    with tempfile.TemporaryDirectory(prefix="astra-palette-") as temp:
        palette = str(Path(temp) / "palette.png")
        for width, fps, colors in [(640, 6, 128), (640, 5, 96), (560, 4, 64), (480, 3, 48), (400, 2, 32)]:
            filters = f"setpts={min(1., 20 / duration):.9f}*PTS,fps={fps},scale={width}:-1:flags=lanczos"
            subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(movie), "-vf",
                            filters + f",palettegen=max_colors={colors}:stats_mode=diff", "-frames:v", "1", palette], check=True)
            subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(movie), "-i", palette,
                            "-lavfi", f"[0:v]{filters}[v];[v][1:v]paletteuse=dither=bayer:bayer_scale=4",
                            "-loop", "0", str(target)], check=True)
            if target.stat().st_size <= max_bytes:
                return {"width": width, "fps": fps, "colors": colors, "bytes": target.stat().st_size,
                        "timeline_seconds": min(duration, 20)}
    raise RuntimeError(f"GIF exceeds {max_bytes} bytes after compression: {target}")


def export_media(run, output, title=None):
    run, output = Path(run), Path(output)
    config, spec, result = (read_json(run / name) for name in ("config.json", "action_spec.json", "result.json"))
    calls = load_calls(run)
    count = int(result["control_steps"]) + 1
    dt = float(spec["control_dt"])
    duration = min(45., max(20., count * dt))
    output.mkdir(parents=True, exist_ok=True)
    movie = output / "annotated.mp4"
    reader = imageio.get_reader(str(run / "rollout.mp4"))
    writer = None
    frames = 0
    previous_key, background = object(), None
    try:
        writer = imageio.get_writer(str(movie), fps=count / duration, codec="libx264", quality=8,
                                   macro_block_size=16, ffmpeg_log_level="error",
                                   output_params=["-movflags", "+faststart", "-pix_fmt", "yuv420p"])
        for step, pixels in enumerate(reader):
            call = executed_call(calls, step)
            key = call["name"] if call else None
            if key != previous_key:
                background = panel(config, spec, result, call, title or run.name, duration, (count - 1) * dt)
                previous_key = key
            frame = background.copy()
            scene = ImageOps.contain(Image.fromarray(pixels), (1920, 768), Image.Resampling.LANCZOS)
            frame.paste(scene, ((1920 - scene.width) // 2, 145 + (768 - scene.height) // 2))
            draw = ImageDraw.Draw(frame)
            time_label = f"Step {step:04d} | simulation {step * dt:.2f}s"
            draw.text((1340, 23), time_label, font=font(27), fill="#ffffff")
            writer.append_data(np.asarray(frame))
            frames += 1
    finally:
        reader.close()
        if writer is not None:
            writer.close()
    if frames != count:
        raise ValueError(f"Video has {frames} frames; expected reset + {count - 1} control steps")
    gif_info = make_gif(movie, output / "preview.gif", duration)
    manifest = {"source_run": str(run), "title": title or run.name, "frames": frames,
                "simulation_seconds": (count - 1) * dt, "video_seconds": duration,
                "fps": count / duration, "resolution": [1920, 1536], "camera_panel_height": 768,
                "request_waits_in_video": False,
                "action_alignment": "frame 0 reset; input step k action starts frame k+1",
                "gif": gif_info, "result": result}
    (output / "media.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--title")
    args = parser.parse_args()
    print(json.dumps(export_media(args.run, args.output, args.title), indent=2))


if __name__ == "__main__":
    main()
