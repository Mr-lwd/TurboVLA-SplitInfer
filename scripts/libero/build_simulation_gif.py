"""Build a shared-clock 2x2 replay from recorded LIBERO videos and timing logs."""

import argparse
import json
import math
import subprocess
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
REMOTE = "orin_to_thor_async_libero_spatial_20261016T224546_700348+0800"
LOCAL = "orin_libero_spatial_bf16_20261017T180050_872432+0800"
FPS = 20
WIDTH, HEIGHT = 1060, 756
PANEL_WIDTH, PANEL_HEIGHT = 512, 326
COLORS = {
    "准备": ("#eef2f6", "#455569"),
    "执行": ("#e8f5ed", "#246345"),
    "等待推理": ("#fff1d8", "#875400"),
    "执行 + 后台推理": ("#e4f0ff", "#205c9c"),
    "保持 / 缓冲为空": ("#fff1d8", "#875400"),
    "任务成功": ("#e8f5ed", "#246345"),
    "任务结束": ("#eef2f6", "#455569"),
}


def phase(episode, elapsed, local=False):
    if elapsed >= episode["rollout_wall_time_s"]:
        return "任务成功" if episode["success"] else "任务结束"
    calls = episode["inference_timings"]
    steps = episode["step_timings"]
    if elapsed < min(calls[0]["start_s"], steps[0]["action_start_s"]):
        return "准备"
    waits = calls if local else episode["blocking_waits"]
    if any(w["start_s"] <= elapsed < w["end_s"] for w in waits):
        return "等待推理"
    if any(s["hold"] and s["action_start_s"] <= elapsed < s["action_end_s"] for s in steps):
        return "保持 / 缓冲为空"
    if not local and any(c["start_s"] <= elapsed < c["end_s"] for c in calls):
        return "执行 + 后台推理"
    return "执行"


def sources(task_id):
    local_dir = ROOT / "outputs/evaluation/local" / LOCAL
    report = json.loads((local_dir / f"{LOCAL}.json").read_text(encoding="utf-8"))
    task = next(t for t in report["tasks"] if t["task_id"] == task_id)
    episode = next(e for e in task["episode_results"] if e["episode"] == 0)
    result = [{
        "label": "Local Orin · 本机推理", "local": True, "episode": episode,
        "report": local_dir / f"{LOCAL}.json",
        "video": local_dir / f"orin_videos/turbovla_libero/libero_spatial/task{task_id:02d}_ep000_success_realtime.mp4",
    }]
    remote_dir = ROOT / "outputs/evaluation/async" / REMOTE
    for mode, label in [("sync", "Sync · 同步"), ("replace", "Async · 异步替换"), ("blend", "Blend · 异步融合")]:
        report_path = remote_dir / f"{REMOTE}_{mode}.json"
        data = json.loads(report_path.read_text(encoding="utf-8"))
        episode = next(e for e in data["episodes"] if e["task_id"] == task_id and e["episode"] == 0)
        assert episode["instruction"] == task["task_description"], "Task mismatch"
        result.append({"label": label, "local": False, "episode": episode, "report": report_path,
                       "video": remote_dir / mode / f"videos/task{task_id:02d}_ep000_success_realtime.mp4"})
    for source in result:
        assert source["episode"]["success"], source["label"]
        reader = imageio_ffmpeg.read_frames(str(source["video"]), pix_fmt="rgb24")
        meta = next(reader)
        assert meta["size"] == (512, 256) and meta["fps"] == FPS, meta
        source["frames"] = [Image.frombytes("RGB", meta["size"], frame) for frame in reader]
        assert len(source["frames"]) >= math.ceil(source["episode"]["rollout_wall_time_s"] * FPS)
    return result


def render(records, elapsed, font_path, task_id):
    fonts = {size: ImageFont.truetype(str(font_path), size) for size in (14, 16, 20, 22)}
    image = Image.new("RGB", (WIDTH, HEIGHT), "#f3f7fb")
    draw = ImageDraw.Draw(image)
    draw.text((16, 12), f"LIBERO Spatial · Task {task_id:02d} · 四模式实测", font=fonts[22], fill="#182433")
    draw.text((WIDTH - 16, 16), f"t = {elapsed:05.2f} s  |  1× 实时", anchor="ra", font=fonts[20], fill="#205c9c")
    for index, source in enumerate(records):
        x, y = 12 + (index % 2) * 524, 54 + (index // 2) * 340
        episode = source["episode"]
        duration = episode["rollout_wall_time_s"]
        state = phase(episode, elapsed, source["local"])
        background, foreground = COLORS[state]
        draw.rectangle((x, y, x + PANEL_WIDTH, y + PANEL_HEIGHT), fill="white")
        draw.text((x + 12, y + 6), source["label"], font=fonts[20], fill="#182433")
        draw.rounded_rectangle((x + 10, y + 34, x + 234, y + 62), radius=5, fill=background)
        draw.text((x + 18, y + 37), state, font=fonts[16], fill=foreground)
        draw.text((x + 500, y + 39), f"{min(elapsed, duration):.2f} / {duration:.2f} s", anchor="ra", font=fonts[16], fill="#455569")
        # Use the existing wall-clock resampling; retain the terminal frame once done.
        frame_index = len(source["frames"]) - 1 if elapsed >= duration else min(int(round(elapsed * FPS)), len(source["frames"]) - 1)
        frame = source["frames"][frame_index].copy()
        label = ImageDraw.Draw(frame)
        # Replace the existing 21 px English status strip, never cover additional scene pixels.
        label.rectangle((0, 0, 511, 20), fill="#edf3f9")
        label.text((8, 1), "环境视角", font=fonts[14], fill="#455569")
        label.text((264, 1), "腕部视角", font=fonts[14], fill="#455569")
        image.paste(frame, (x, y + 70))
    draw.text((16, 738), "各次独立运行按起点对齐 · 保留全部推理等待 · 完成后保持终帧", font=fonts[14], fill="#455569")
    return image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-id", type=int, choices=range(10), default=9, help="LIBERO Spatial task; default: cabinet-to-plate task 9")
    parser.add_argument("--font", type=Path, default=Path("C:/Windows/Fonts/msyh.ttc"), help="Chinese-capable TrueType/OpenType font")
    parser.add_argument("--output", type=Path, default=ROOT / "assets/simulation/libero-four-mode-realtime.gif")
    args = parser.parse_args()
    records = sources(args.task_id)
    count = math.ceil(max(s["episode"]["rollout_wall_time_s"] for s in records) * FPS)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    command = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "rawvideo",
               "-pix_fmt", "rgb24", "-s", f"{WIDTH}x{HEIGHT}", "-r", str(FPS), "-i", "pipe:0",
               "-filter_complex", "[0:v]split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle",
               "-loop", "0", str(args.output)]
    with subprocess.Popen(command, stdin=subprocess.PIPE) as process:
        for index in range(count + 1):
            process.stdin.write(render(records, index / FPS, args.font, args.task_id).tobytes())
        process.stdin.close()
        if process.wait() != 0:
            raise RuntimeError("FFmpeg GIF encoding failed")
    manifest = {"fps": FPS, "size": [WIDTH, HEIGHT], "speed": 1, "alignment": "independent rollout starts",
                "task_id": args.task_id, "episode": 0, "sources": []}
    for source in records:
        manifest["sources"].append({"mode": source["label"], "report": source["report"].relative_to(ROOT).as_posix(),
            "video": source["video"].relative_to(ROOT).as_posix(), "wall_time_s": source["episode"]["rollout_wall_time_s"],
            "states": sorted({phase(source["episode"], i / FPS, source["local"]) for i in range(count + 1)})})
    args.output.with_suffix(".json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Exported {args.output.name}: {WIDTH}x{HEIGHT}, {count + 1} frames, {(count + 1) / FPS:.2f}s")
    for source in manifest["sources"]:
        print(source["mode"], f"{source['wall_time_s']:.2f}s", ", ".join(source["states"]))


if __name__ == "__main__":
    main()
