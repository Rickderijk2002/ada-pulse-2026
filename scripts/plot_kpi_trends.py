from __future__ import annotations

import argparse
import logging
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = BASE_DIR / "data" / "kpi" / "gold_kpi_snapshots_local.csv"
DEFAULT_OUTPUT_DIR = BASE_DIR / "data" / "kpi" / "plots"


def plot_domain_panel(
    df: pd.DataFrame,
    domain: str,
    out_path: Path,
) -> None:
    subset = df[df["domain"] == domain].copy()
    if subset.empty:
        logger.warning("No rows for domain %s", domain)
        return

    subset = subset.sort_values("period_end")
    metrics = sorted(subset["metric_name"].unique())
    n = len(metrics)
    cols = min(2, max(1, n))
    rows = (n + cols - 1) // cols
    fig, axes = plt.subplots(
        rows,
        cols,
        figsize=(5.5 * cols, 3.2 * rows),
        squeeze=False,
        sharex=False,
    )
    for ax, metric in zip(axes.flat, metrics):
        mdf = subset[subset["metric_name"] == metric]
        y = pd.to_numeric(mdf["metric_value"], errors="coerce")
        ax.plot(mdf["period_end"], y, marker=".", markersize=3, linewidth=1)
        ax.set_title(metric, fontsize=10)
        ax.set_xlabel("period_end")
        ax.grid(True, alpha=0.3)
        ax.tick_params(axis="x", rotation=25)

    for ax in axes.flat[len(metrics) :]:
        ax.axis("off")

    fig.suptitle(domain, fontsize=12)
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=140, bbox_inches="tight")
    plt.close(fig)
    logger.info("Wrote %s", out_path)


def main() -> None:
    # Set variables directly rather than using argparse.
    input_path = DEFAULT_INPUT
    output_dir = DEFAULT_OUTPUT_DIR

    df = pd.read_csv(input_path, parse_dates=["period_start", "period_end"])
    if df.empty:
        logger.error("Empty input: %s", input_path)
        return

    for domain in sorted(df["domain"].dropna().unique()):
        safe_name = domain.replace("/", "_")
        plot_domain_panel(
            df,
            domain,
            output_dir / f"trends_{safe_name}.png",
        )


if __name__ == "__main__":
    main()
