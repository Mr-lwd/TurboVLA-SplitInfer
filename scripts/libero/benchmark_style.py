"""Shared typography and colors for the published benchmark figures."""

INK = "#243746"
MUTED = "#617381"
GRID = "#E6ECEF"
MODE_COLORS = {
    "orin": "#637C97",
    "thor": "#247F78",
    "sync": "#BB8A4F",
    "replace": "#557CAF",
    "blend": "#9175A0",
}


def mode_color(run, record):
    key = run["hardware"]["device_name"] if record["mode"] == "local" else record["mode"]
    return MODE_COLORS.get(key, MODE_COLORS["orin"])


def mode_label(record):
    return {"Orin local": "Orin 本机", "Thor local": "Thor 本机",
            "Async / replace": "Async"}.get(record["label"], record["label"])


def chart_style():
    from matplotlib import font_manager

    names = ("Noto Sans CJK SC", "Noto Sans CJK JP", "Microsoft YaHei", "SimHei", "PingFang SC")
    fonts = [font for font in font_manager.fontManager.ttflist if font.name in names]
    if not fonts:
        raise RuntimeError("Chinese charts require a CJK font; on Ubuntu install fonts-noto-cjk")
    font = min(fonts, key=lambda item: names.index(item.name))
    return {"font.family": font.name, "font.size": 14, "text.color": INK,
            "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": INK,
            "svg.fonttype": "path", "svg.hashsalt": "turbovla-benchmark",
            "axes.unicode_minus": False, "figure.facecolor": "white", "axes.facecolor": "white"}


def save_chart(fig, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    svg = path.with_suffix(".svg")
    fig.savefig(svg, metadata={"Date": None})
    # Matplotlib emits trailing spaces in SVG path data; normalize for clean diffs.
    svg.write_text("\n".join(line.rstrip() for line in svg.read_text().splitlines()) + "\n")
    fig.savefig(path.with_suffix(".png"), dpi=180)
