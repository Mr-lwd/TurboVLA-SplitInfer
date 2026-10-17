"""Non-overlapping breakdown of measured mean remote response latency."""

import math


STAGES = (
    ("Orin 图像与状态预处理", "#557da8"),
    ("请求编码与压缩", "#9bbbd8"),
    ("Thor 解码与排队", "#9ec9bc"),
    ("Thor 推理与动作转换", "#277b70"),
    ("HTTP / 传输等开销", "#dca76b"),
    ("其他调用开销", "#bbc3cc"),
)


def latency_breakdown(record):
    """Only stack complete, aligned sample means; never stack percentiles."""
    metrics = record["metrics"]
    stages = metrics.get("remote_stage_timings")
    if not stages:
        return None
    calls = metrics["filtered_calls"]
    count, total = calls["count"], calls["mean_ms"]
    if not count or total is None:
        return None
    means = {}
    for key in ("client_preprocess_s", "client_encode_s", "server_decode_s", "server_queue_s",
                "server_inference_s", "server_total_s", "round_trip_s", "transport_overhead_s"):
        stage = stages.get(key, {}).get("filtered_calls", {})
        value = stage.get("mean_ms")
        if stage.get("count") != count or stage.get("missing_count", 0) or value is None:
            return None
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"Invalid stage mean: {key}")
        means[key] = value
    decode = means["server_decode_s"] + means["server_queue_s"]
    inference = means["server_inference_s"]
    transport = means["transport_overhead_s"]
    if not math.isclose(decode + inference, means["server_total_s"], abs_tol=1e-5):
        raise ValueError("Server stages do not reconcile")
    if not math.isclose(means["server_total_s"] + transport, means["round_trip_s"], abs_tol=1e-5):
        raise ValueError("Round trip and transport residual do not reconcile")
    values = [means["client_preprocess_s"], means["client_encode_s"], decode, inference, transport]
    other = total - sum(values)
    if not math.isfinite(total) or other < -1e-5:
        raise ValueError("Stage means exceed complete response time")
    return {"label": record["label"], "count": count, "total": total,
            "p95": calls["p95_ms"], "values": [*values, max(0., other)]}


def plot_stage_timings(rows, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager

    remote = [(run, record) for run, record in rows if record["metrics"].get("remote_stage_timings")]
    if not remote:
        return False
    data = [latency_breakdown(record) for _, record in remote]
    fonts = [f for f in font_manager.fontManager.ttflist
             if f.name in ("Noto Sans CJK SC", "Noto Sans CJK JP", "Microsoft YaHei", "SimHei", "PingFang SC")]
    if not fonts:
        raise RuntimeError("Chinese charts require a CJK font; on Ubuntu install fonts-noto-cjk")
    font = font_manager.FontProperties(fname=fonts[0].fname)
    # Paths embed the glyphs, so GitHub and browsers need no installed CJK font.
    with plt.rc_context({"font.family": font.get_name(), "svg.fonttype": "path",
                         "svg.hashsalt": "turbovla-stage-timings", "axes.unicode_minus": False}):
        count = len(remote)
        fig = plt.figure(figsize=(13, max(7.5, 5.8 + count * .57)), facecolor="white")
        ink, muted = "#20364b", "#667a8c"
        fig.text(.055, .94, "协同推理 · 时间花在哪里", fontsize=22, weight="bold", color=ink)
        filters = sorted({run["exclude_first_calls"] for run, _ in remote})
        filter_label = str(filters[0]) if len(filters) == 1 else "/".join(map(str, filters))
        fig.text(.055, .895, f"每次动作块的响应时间  /  毫秒  ·  每回合排除前 {filter_label} 次调用；样本数 n 见模式标签",
                 fontsize=11, color=muted)
        ax = fig.add_axes([.18, .51, .59, .29])
        maximum = max((item["total"] for item in data if item), default=1) or 1
        for index, item in enumerate(data):
            if item is None:
                ax.text(0, index, "阶段记录不完整，未绘制分解", va="center", color=muted, fontsize=11)
                continue
            left = 0.
            for stage_index, (value, (_, color)) in enumerate(zip(item["values"], STAGES)):
                ax.barh(index, value, left=left, height=.48, color=color, linewidth=0)
                if value / maximum >= .075:
                    ax.text(left + value / 2, index, f"{value:.1f}", ha="center", va="center",
                            fontsize=11, weight="bold", color="white" if stage_index in (0, 3) else ink)
                left += value
        ax.set(xlim=(0, maximum * 1.03), ylim=(count - .45, -.55),
               yticks=range(count), yticklabels=[f"{r['label']}\nn = {r['metrics']['filtered_calls']['count']}" for _, r in remote])
        ax.tick_params(axis="y", length=0, pad=12, labelsize=11, colors=ink)
        ax.tick_params(axis="x", length=0, pad=8, labelsize=10, colors=muted)
        ax.set_axisbelow(True)
        ax.grid(axis="x", color="#e8edf2", linewidth=.8)
        ax.spines[["top", "right", "left", "bottom"]].set_visible(False)
        ax.set_xlabel("平均响应时间（ms）", fontsize=10, color=muted, labelpad=10)
        for xpos, label in ((1.12, "平均响应"), (1.32, "响应 p95")):
            ax.text(xpos, 1.11, label, transform=ax.transAxes, ha="center", fontsize=10, color=muted)
        for index, (_, record) in enumerate(remote):
            for xpos, key in ((1.12, "mean_ms"), (1.32, "p95_ms")):
                value = record["metrics"]["filtered_calls"][key]
                ax.text(xpos, index, "—" if value is None else f"{value:.2f}", transform=ax.get_yaxis_transform(),
                        ha="center", va="center", fontsize=13, weight="bold", color=ink)
        # Exact values remain legible for narrow segments that cannot hold labels.
        table_ax = fig.add_axes([.055, .14, .89, .26])
        table_ax.axis("off")
        table_ax.text(0, 1.06, "阶段明细 / ms", fontsize=11, weight="bold", color=ink)
        positions = [.44 + i * .52 / max(1, count - 1) for i in range(count)]
        for xpos, (_, record) in zip(positions, remote):
            table_ax.text(xpos, 1.06, record["label"], ha="right", fontsize=11, weight="bold", color=ink)
        for index, (label, color) in enumerate(STAGES):
            y = .88 - index * .17
            table_ax.axhline(y - .085, color="#e8edf2", linewidth=.7)
            table_ax.scatter(.008, y, s=75, marker="s", color=color)
            table_ax.text(.03, y, label, va="center", fontsize=11, color=ink)
            for xpos, item in zip(positions, data):
                table_ax.text(xpos, y, "—" if item is None else f"{item['values'][index]:.2f}",
                              ha="right", va="center", fontsize=11, color=ink)
        table_ax.set(xlim=(-.005, 1.01), ylim=(-.08, 1.2))
        fig.text(.055, .068, "分段之和 = 平均响应时间；颜色表示耗时构成，不代表执行先后。响应 p95 独立统计，不做阶段相加。",
                 fontsize=10, color=muted)
        fig.text(.055, .035, "HTTP / 传输等开销包含接收等待与系统开销，并非纯网络延迟；灰色为调用总时间减已分解阶段的余量。",
                 fontsize=10, color=muted)
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path.with_suffix(".svg"), metadata={"Date": None})
        fig.savefig(path.with_suffix(".png"), dpi=160)
        plt.close(fig)
    return True
