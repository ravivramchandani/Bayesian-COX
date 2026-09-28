"""Write deterministic figures, tables and exact source lineage.

Table and figure outputs use :func:`_write_table` (CSV and LaTeX)
and :func:`_save_figure` (PDF and PNG). Both register each file with the
:class:`OutputRegistry`, recording its SHA-256 and the verified source files
and fields it was derived from. At the end of a render
:meth:`OutputRegistry.write_lineage` writes ``lineage.json``, so every output
can be traced back to hashed frozen evidence and to the exact renderer code.

Outputs are made reproducible by fixed PDF dates and metadata, a fixed
matplotlib style, Unix line endings and fixed float formatting in LaTeX
tables. Text files are written atomically through a temporary file."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import matplotlib

# Select the non-interactive backend before pyplot is imported.
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

from .constants import FIXED_PDF_DATE, PROJECT_ROOT
from .verification import FrozenRun, _source, canonical_json_hash, sha256_file


class OutputRegistry:
    """Write-only registry that records exact sources for every output file.

    The renderer source is hashed when the registry is created and again
    when lineage is written; a difference means the code changed during the
    render, and the lineage is refused.

    Attributes:
        output_dir: Directory that receives every output.
        run: The verified source run.
        outputs: One record per registered file.
        renderer_input_hashes: SHA-256 of the entry script and of every
            module in ``src/rendering``, taken at creation.
    """

    def __init__(self, output_dir: Path, run: FrozenRun) -> None:
        """Start an empty registry and hash the renderer source.

        Args:
            output_dir: Directory that receives every output.
            run: The verified source run.
        """
        self.output_dir = output_dir
        self.run = run
        self.outputs: list[dict[str, Any]] = []
        self.renderer_input_hashes = self._renderer_hashes()

    @staticmethod
    def _renderer_hashes() -> dict[str, str]:
        """Hash ``scripts/render_confirmatory.py`` and every ``src/rendering/*.py`` file."""
        paths = [PROJECT_ROOT / "scripts/render_confirmatory.py"]
        paths.extend(sorted((PROJECT_ROOT / "src/rendering").glob("*.py")))
        return {str(path.relative_to(PROJECT_ROOT)): sha256_file(path) for path in paths}

    def add(
        self,
        path: Path,
        *,
        kind: str,
        sources: Iterable[dict[str, Any]],
        note: str,
    ) -> None:
        """Record one written file with its hash, kind, sources and note.

        Args:
            path: The written file, inside ``output_dir``.
            kind: Output type, for example ``table_csv`` or ``figure_pdf``.
            sources: Lineage records of the verified inputs it came from.
            note: Short statement of what the output shows and its limits.

        Raises:
            RuntimeError: If the same path is registered twice.
        """
        relative = str(path.relative_to(self.output_dir))
        if any(row["path"] == relative for row in self.outputs):
            raise RuntimeError(f"duplicate rendered output registration: {relative}")
        self.outputs.append(
            {
                "path": relative,
                "sha256": sha256_file(path),
                "kind": kind,
                "sources": list(sources),
                "note": note,
            }
        )

    def write_lineage(
        self,
        *,
        optional_sources: list[dict[str, Any]],
        renderer_path: Path,
    ) -> Path:
        """Write ``lineage.json`` for everything registered so far.

        The file records the source run's identity and content hashes, the
        renderer script and module hashes, the optional explainability and
        robustness sources, and every output sorted by path. It is sealed
        with ``lineage_content_sha256``, the canonical hash of the rest of
        the mapping. ``lineage.json`` does not list itself.

        Args:
            optional_sources: Lineage records of the verified supplements.
            renderer_path: Entry script whose file hash is recorded.

        Returns:
            Path of ``lineage.json``.

        Raises:
            RuntimeError: If the renderer source changed since the registry
                was created.
        """
        if self._renderer_hashes() != self.renderer_input_hashes:
            raise RuntimeError(
                "renderer source changed during rendering; use a new output directory"
            )
        lineage = {
            "schema_version": "1.0.0",
            "evidence_status": self.run.evidence_status,
            "source_run": {
                "directory_name": self.run.run_dir.name,
                "analysis_mode": self.run.mode,
                "manifest_content_sha256": self.run.manifest["manifest_content_sha256"],
                "completion_content_sha256": self.run.completion["completion_content_sha256"],
            },
            "renderer": {
                "path": "scripts/render_confirmatory.py",
                "sha256": sha256_file(renderer_path),
                "module_sha256": {
                    name: digest
                    for name, digest in self.renderer_input_hashes.items()
                    if name.startswith("src/rendering/")
                },
                "policy": "pure frozen-artifact renderer; no model reconstruction or fitting",
            },
            "optional_source_artifacts": optional_sources,
            "outputs": sorted(self.outputs, key=lambda row: row["path"]),
        }
        lineage["lineage_content_sha256"] = canonical_json_hash(lineage)
        path = self.output_dir / "lineage.json"
        _atomic_text(
            path,
            json.dumps(lineage, indent=2, sort_keys=True, allow_nan=False) + "\n",
        )
        return path


def _atomic_text(path: Path, text: str) -> None:
    """Write UTF-8 text through a temporary file before replacing the destination.

    Creates the parent directory when needed.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def _configure_style() -> None:
    """Apply the shared matplotlib font, size, resolution and grid settings."""
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.labelsize": 9,
            "legend.fontsize": 7,
            "figure.dpi": 120,
            "savefig.dpi": 240,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.alpha": 0.18,
        }
    )


def _save_figure(
    figure: plt.Figure,
    base_path: Path,
    registry: OutputRegistry,
    *,
    title: str,
    sources: Iterable[dict[str, Any]],
    note: str,
) -> list[Path]:
    """Save a figure as PDF and PNG with fixed metadata, register both and close it.

    Args:
        figure: The completed figure.
        base_path: Output path without suffix.
        registry: Output registry.
        title: Title stored in the file metadata.
        sources: Lineage records of the inputs.
        note: Description stored in the metadata and in the lineage.

    Returns:
        The PDF and PNG paths.
    """
    source_list = list(sources)
    written: list[Path] = []
    figure.tight_layout()
    for suffix in (".pdf", ".png"):
        path = base_path.with_suffix(suffix)
        path.parent.mkdir(parents=True, exist_ok=True)
        # PDF and PNG writers accept different metadata keys; the PDF dates
        # are fixed because matplotlib would otherwise stamp the current time.
        if suffix == ".pdf":
            metadata = {
                "Title": title,
                "Author": "Ravi Thesis Project",
                "Subject": note,
                "Keywords": "frozen artifact; reproducible rendering",
                "Creator": "scripts/render_confirmatory.py",
                "Producer": "Matplotlib",
                "CreationDate": FIXED_PDF_DATE,
                "ModDate": FIXED_PDF_DATE,
            }
        else:
            metadata = {
                "Title": title,
                "Author": "Ravi Thesis Project",
                "Description": note,
                "Software": "scripts/render_confirmatory.py",
            }
        figure.savefig(path, bbox_inches="tight", metadata=metadata)
        registry.add(path, kind=f"figure_{suffix[1:]}", sources=source_list, note=note)
        written.append(path)
    plt.close(figure)
    return written


def _write_table(
    frame: pd.DataFrame,
    base_path: Path,
    registry: OutputRegistry,
    *,
    sources: Iterable[dict[str, Any]],
    note: str,
) -> list[Path]:
    """Write a table as CSV and LaTeX and register both.

    The LaTeX version escapes special characters, shows missing values as
    ``--`` and prints floats with four decimals; the CSV keeps full precision.

    Args:
        frame: The table.
        base_path: Output path without suffix.
        registry: Output registry.
        sources: Lineage records of the inputs.
        note: Description recorded in the lineage.

    Returns:
        The CSV and LaTeX paths.
    """
    source_list = list(sources)
    base_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path = base_path.with_suffix(".csv")
    tex_path = base_path.with_suffix(".tex")
    _atomic_text(csv_path, frame.to_csv(index=False, lineterminator="\n"))
    latex = frame.to_latex(
        index=False,
        escape=True,
        na_rep="--",
        float_format=lambda value: f"{value:.4f}",
    )
    _atomic_text(tex_path, latex)
    registry.add(csv_path, kind="table_csv", sources=source_list, note=note)
    registry.add(tex_path, kind="table_latex", sources=source_list, note=note)
    return [csv_path, tex_path]


def _cell_sources(
    run: FrozenRun,
    selected: Iterable[tuple[str, dict[str, Any]]],
    result_keys: Iterable[str],
) -> list[dict[str, Any]]:
    """Return one lineage record per selected cell, citing the same result keys.

    Args:
        run: The verified run.
        selected: ``(relative path, cell)`` pairs from ``run.cells``.
        result_keys: Cell fields the output was derived from.
    """
    keys = list(result_keys)
    return [_source(run, relative, keys) for relative, _ in selected]
