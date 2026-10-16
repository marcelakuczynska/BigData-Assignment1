import csv
from pathlib import Path
import matplotlib.pyplot as plt


def make_plots(summary_csv, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)
    with open(summary_csv, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    for column, ylabel, name, title in [
        ("median_time_ms", "Median multiplication time (ms)", "time_comparison.png",
         "Triple-loop matrix multiplication: measured execution time"),
        ("peak_process_rss_mib", "Sampled maximum process RSS (MiB)", "memory_comparison.png",
         "Observed process memory (includes runtime and I/O)"),
    ]:
        fig, ax = plt.subplots(figsize=(9, 5))
        for language in ["Python", "Java", "C"]:
            entries = sorted((row for row in rows if row["language"] == language),
                             key=lambda r: int(r["n"]))
            if entries:
                ax.plot([int(r["n"]) for r in entries],
                        [float(r[column]) for r in entries], marker="o", label=language)
        ax.set_title(title)
        ax.set_xlabel("Matrix dimension n (n × n)")
        ax.set_ylabel(ylabel)
        if column == "median_time_ms":
            ax.set_yscale("log")
        ax.legend()
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.savefig(output_dir / name, dpi=160)
        plt.close(fig)


if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    make_plots(here / "results" / "summary.csv", here / "figures")
