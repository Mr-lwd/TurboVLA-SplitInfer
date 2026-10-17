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
    return {"Orin local": "Orin local", "Thor local": "Thor local",
            "Async / replace": "Async"}.get(record["label"], record["label"])


def chart_style():
    return {"font.family": "DejaVu Sans", "font.size": 14, "text.color": INK,
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
