"""Non-overlapping breakdown of measured mean remote response latency."""

import math

from scripts.libero.benchmark_style import INK, MUTED, GRID, chart_style, mode_color, mode_label, save_chart


STAGES = (
    ("Orin preprocessing", "#557CAF"),
    ("Encoding", "#AEC3DB"),
    ("Thor decode/queue", "#8DB9AC"),
    ("Thor inference", "#247F78"),
    ("HTTP/transport", "#C59D69"),
    ("Other overhead", "#BFC7CF"),
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


def plot_stage_timings(rows, path, caption=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    from matplotlib.ticker import MaxNLocator

    if not any(record["metrics"].get("remote_stage_timings") for _, record in rows):
        return False
    data = [latency_breakdown(record) for _, record in rows]
    with plt.rc_context(chart_style()):
        count = len(rows)
        fig = plt.figure(figsize=(13, max(7, 3.6 + count * .72)))
        fig.text(.055, .93, "Inference response · Latency breakdown", fontsize=25, weight="bold")
        fig.text(.055, .865, "Complete local calls and remote stage breakdowns. Units: ms / action chunk", fontsize=14, color=MUTED)
        if caption:
            fig.text(.055, .81, caption, fontsize=14, color=MUTED)
        ax = fig.add_axes([.17, .27, .57, .47])
        maximum = max((record['metrics']['filtered_calls']['mean_ms'] or 0 for _, record in rows), default=1) or 1
        for index, ((run, record), item) in enumerate(zip(rows, data)):
            total = record['metrics']['filtered_calls']['mean_ms']
            if record['mode'] == 'local' and total is not None:
                ax.barh(index, total, height=.48, color=mode_color(run, record), zorder=3)
            elif item is None:
                ax.text(0, index, "Stage data not recorded", va="center", color=MUTED, fontsize=13)
            else:
                left = 0.
                for stage_index, (value, (_, color)) in enumerate(zip(item['values'], STAGES)):
                    ax.barh(index, value, left=left, height=.48, color=color, linewidth=0, zorder=3)
                    if value / maximum >= .12:
                        ax.text(left + value / 2, index, f"{value:.1f}", ha="center", va="center",
                                fontsize=14, weight="bold", color="white" if stage_index in (0, 3) else INK)
                    left += value
        ax.set(xlim=(0, maximum * 1.06), ylim=(count - .45, -.55),
               yticks=range(count), yticklabels=[mode_label(record) for _, record in rows])
        ax.tick_params(axis='y', length=0, pad=12, labelsize=15)
        ax.tick_params(axis='x', length=0, pad=10, labelsize=12)
        ax.xaxis.set_major_locator(MaxNLocator(4))
        ax.set_axisbelow(True)
        ax.grid(axis='x', color=GRID, linewidth=.8)
        ax.spines[:].set_visible(False)
        for xpos, label in ((1.14, "Mean"), (1.36, "p95")):
            ax.text(xpos, 1.1, label, transform=ax.transAxes, ha="center", fontsize=14, color=MUTED)
        for index, (_, record) in enumerate(rows):
            for xpos, key in ((1.14, 'mean_ms'), (1.36, 'p95_ms')):
                value = record['metrics']['filtered_calls'][key]
                ax.text(xpos, index, "—" if value is None else f"{value:.2f}",
                        transform=ax.get_yaxis_transform(), ha="center", va="center",
                        fontsize=16, weight="bold", color=INK)
        fig.legend(handles=[Patch(facecolor=color, label=label) for label, color in STAGES],
                   loc='lower center', bbox_to_anchor=(.5, .045), ncol=3, frameon=False,
                   fontsize=14, handlelength=1.1, handleheight=1.1, columnspacing=2.8, labelspacing=1.1)
        save_chart(fig, path)
        plt.close(fig)
    return True
