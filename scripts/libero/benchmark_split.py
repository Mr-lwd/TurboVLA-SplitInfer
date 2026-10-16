"""Run device-labelled split inference benchmarks using the common report format."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.libero.benchmark_local import main


if __name__ == "__main__":
    main(split=True)
