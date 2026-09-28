#!/usr/bin/env python3
"""Package verified programme evidence into private, deterministic release assets.

Requires the final release_ready seal written after visual QA. This command never
publishes assets and never changes the original confirmatory Release or run.

This is the last step after ``complete_results_programme.py`` and the visual
quality assurance (QA) review. This script does not create the seal
(``programme_release_ready.json``); it must already exist. The seal names the
committed code revision, the hash of every code file, the verified programme
report, the passed visual QA record, and the root directory and file hashes of
the seven programme artefacts: the original 450-cell run, the full
reproduction, the robustness run, the explanation result, the rendered
confirmatory package, the sampler-sensitivity run and the rendered post-hoc
package.

Before writing anything, the script checks every sealed file and artefact
inventory, checks the sealed code against the committed Git tree and the
working tree, and cross-checks the artefacts against their scientific
evidence: 450 identical refits, 825 robustness cells, the verified
explanation, the 75-cell sensitivity and both rendered bundles.

Writes, into a new ``--output-dir``: five deterministic archives
(``programme-committed-code.tar.gz``, ``programme-reproduction.tar.gz``,
``programme-robustness.tar.gz``, ``programme-confirmatory-reports.tar.gz`` and
``programme-posthoc-sensitivity.tar.gz``), copies of the seal, the verified
report and the visual QA record, ``programme_release_manifest.json`` and
``SHA256SUMS``. The original 450-cell run is referenced by its inventory, not
repackaged. An existing output directory is verified against the same seal and
left unchanged. Verify or restore the assets with
``restore_programme_release.py``.

Example:
    python scripts/package_programme_release.py \
        --seal <closeout>/programme_release_ready.json \
        --output-dir <new release directory>
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
# The seven artefacts a release seal must name, and how the four evidence
# archives group them; the committed-code archive is built separately.
ARTIFACT_KEYS = {
    "original450", "reproduction", "robustness", "explanation",
    "rendered_confirmatory", "sampler_run", "rendered_posthoc",
}
ARCHIVE_GROUPS = {
    "programme-reproduction.tar.gz": ("reproduction",),
    "programme-robustness.tar.gz": ("robustness",),
    "programme-confirmatory-reports.tar.gz": ("explanation", "rendered_confirmatory"),
    "programme-posthoc-sensitivity.tar.gz": ("sampler_run", "rendered_posthoc"),
}
HASH_PATTERN = re.compile(r"[0-9a-f]{64}\Z")


def sha256_file(path: Path) -> str:
    """Hash a file without loading a large result archive into memory.

    Args:
        path: File whose bytes are hashed.

    Returns:
        The 64-character hexadecimal digest of the file bytes.
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    """Hash the canonical JSON representation used by stored evidence.

    Args:
        value: JSON-compatible content excluding any claimed hash field.

    Returns:
        The hexadecimal SHA-256 of the canonical UTF-8 JSON bytes.
    """
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False,
    ).encode()).hexdigest()


def load_mapping(path: Path) -> dict[str, Any]:
    """Read a JSON object, rejecting missing files and non-object values.

    Args:
        path: JSON file required to contain an object.

    Returns:
        The parsed JSON object.
    """
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def verify_content_hash(record: dict[str, Any], field: str) -> None:
    """Verify a record's self-contained canonical content hash.

    Args:
        record: Stored object including its claimed content hash.
        field: Hash field excluded when recomputing the digest.
    """
    content = dict(record)
    claimed = content.pop(field, None)
    if claimed != canonical_hash(content):
        raise ValueError(f"invalid {field}")


def safe_relative(name: str) -> str:
    """Accept a canonical, portable relative file path with no traversal.

    Rejected are empty names, backslashes, colons, control characters,
    absolute paths, ``.`` or ``..`` components, and empty or redundant
    separators.

    Args:
        name: Archive or inventory member name in POSIX form.

    Returns:
        ``name`` unchanged.

    Raises:
        ValueError: If ``name`` is not such a path.
    """
    if (not isinstance(name, str) or not name or "\\" in name or ":" in name
            or any(ord(character) < 32 or ord(character) == 127 for character in name)):
        raise ValueError(f"unsafe relative path: {name!r}")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in {".", ".."} for part in name.split("/")):
        raise ValueError(f"unsafe relative path: {name!r}")
    if path.as_posix() != name or "" in name.split("/"):
        raise ValueError(f"noncanonical relative path: {name!r}")
    return name


def validate_inventory(value: Any) -> dict[str, str]:
    """Require a nonempty mapping of safe relative files to SHA256 hashes.

    Args:
        value: Nonempty mapping from relative file paths to hexadecimal SHA-256 digests.

    Returns:
        A copy of the mapping sorted by file name.
    """
    if not isinstance(value, dict) or not value:
        raise ValueError("file inventory must be a nonempty mapping")
    for name, digest in value.items():
        safe_relative(name)
        if not isinstance(digest, str) or not HASH_PATTERN.fullmatch(digest):
            raise ValueError(f"invalid SHA256 for {name}")
    return dict(sorted(value.items()))


def directory_inventory(root: Path) -> dict[str, str]:
    """Hash every regular file, rejecting symlinks and special files.

    Args:
        root: Real directory whose complete file tree is inventoried.

    Returns:
        Relative POSIX path of each file below ``root`` mapped to its SHA-256.
    """
    if root.is_symlink() or not root.is_dir():
        raise ValueError(f"artifact root must be a real directory: {root}")
    inventory = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or (not path.is_dir() and not path.is_file()):
            raise ValueError(f"artifact contains a link or special file: {path}")
        if path.is_file():
            relative = safe_relative(path.relative_to(root).as_posix())
            inventory[relative] = sha256_file(path)
    return inventory


def verify_inventory(root: Path, inventory: dict[str, str]) -> None:
    """Require the exact declared set of files and bytes under an artifact root.

    Args:
        root: Artefact directory to check.
        inventory: Expected nonempty relative-path and file-digest mapping.
    """
    expected = validate_inventory(inventory)
    if directory_inventory(root) != expected:
        raise ValueError(f"artifact inventory changed or is incomplete: {root}")


def _descriptor_file(descriptor: Any) -> tuple[Path, dict[str, Any]]:
    """Check a sealed ``{"path", "sha256"}`` descriptor and load the JSON file it names.

    Only the file's bytes are checked against the recorded hash; its content
    is not otherwise validated here.
    """
    if not isinstance(descriptor, dict):
        raise ValueError("missing sealed file descriptor")
    path = Path(descriptor["path"])
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise ValueError(f"sealed file must be an absolute regular file: {path}")
    if sha256_file(path) != descriptor.get("sha256"):
        raise ValueError(f"sealed file changed: {path}")
    return path, load_mapping(path)


def read_release_seal(seal_path: Path) -> tuple[dict[str, Any], dict[str, Path]]:
    """Require final visual QA and verify all sealed files and artifact inventories.

    Args:
        seal_path: Final programme release-ready JSON record.

    Returns:
        The seal and the resolved root directory of each of the seven
        artefacts.

    Raises:
        ValueError: If the seal is not ``release_ready``, visual QA has not
            passed, a sealed file or inventory differs, an artefact is missing
            or has a relative root, or the code revision is not a full commit
            hash.
    """
    seal = load_mapping(seal_path)
    if seal.get("status") != "release_ready":
        raise ValueError("packaging requires the final release_ready seal after visual QA")
    _descriptor_file(seal.get("verified_report"))
    qa = seal.get("visual_qa", {})
    if qa.get("status") != "passed":
        raise ValueError("final visual QA must have passed")
    _, qa_record = _descriptor_file(qa)
    if qa_record.get("status") != "passed":
        raise ValueError("visual QA record does not report passed")
    if not isinstance(seal.get("artifacts"), dict) or set(seal["artifacts"]) != ARTIFACT_KEYS:
        raise ValueError("seal must enumerate all seven programme artifacts")
    roots = {}
    for name, descriptor in seal["artifacts"].items():
        root = Path(descriptor["root"])
        if not root.is_absolute():
            raise ValueError(f"artifact root must be absolute: {name}")
        verify_inventory(root, descriptor["files"])
        roots[name] = root.resolve()
    validate_inventory(seal.get("code_files"))
    if not re.fullmatch(r"[0-9a-f]{40}", str(seal.get("code_commit", ""))):
        raise ValueError("seal must pin the full committed code revision")
    return seal, roots


def committed_code(project_root: Path, seal: dict[str, Any]) -> dict[str, bytes]:
    """Read the immutable Git tree and verify sealed actual-code hashes against it.

    Every sealed code file must match both the blob at the sealed commit and
    the file in the working tree.

    Args:
        project_root: Repository containing the named commit and actual sealed code files.
        seal: Release-ready record naming the commit and sealed code-file digests.

    Returns:
        Every file of the commit's tree, by path, as bytes.

    Raises:
        ValueError: If the tree contains a link or submodule, or a sealed file
            differs from the commit or the working tree.
    """
    commit = seal["code_commit"]
    listing = subprocess.run(
        ["git", "ls-tree", "-rz", "--full-tree", commit], cwd=project_root,
        check=True, stdout=subprocess.PIPE,
    ).stdout
    files = {}
    for entry in listing.split(b"\0"):
        if not entry:
            continue
        metadata, encoded_name = entry.split(b"\t", 1)
        mode, kind, object_id = metadata.decode().split()
        name = safe_relative(encoded_name.decode())
        if kind != "blob" or mode not in {"100644", "100755"}:
            raise ValueError(f"committed code contains a link or submodule: {name}")
        files[name] = subprocess.run(
            ["git", "cat-file", "blob", object_id], cwd=project_root,
            check=True, stdout=subprocess.PIPE,
        ).stdout
    for name, digest in validate_inventory(seal["code_files"]).items():
        if name not in files or hashlib.sha256(files[name]).hexdigest() != digest:
            raise ValueError(f"sealed code differs from the committed snapshot: {name}")
        if sha256_file(project_root / name) != digest:
            raise ValueError(f"actual programme code changed: {name}")
    return files


def _find_record(root: Path, inventory: dict[str, str], field: str, value: str) -> Path:
    """Return the only JSON file in ``inventory`` whose ``field`` equals ``value``."""
    candidates = []
    for relative in inventory:
        if relative.endswith(".json"):
            path = root / relative
            if load_mapping(path).get(field) == value:
                candidates.append(path)
    if len(candidates) != 1:
        raise ValueError(f"expected exactly one {field}={value} record under {root}")
    return candidates[0]


def _verify_reproduction(seal: dict[str, Any], roots: dict[str, Path], source: Any) -> None:
    """Require a complete, identical 450-cell reproduction run with the sealed code.

    The report, its checkpoint and every saved refit are checked; each refit
    is compared with its original cell again through
    ``reproduce_confirmatory_cells.check_saved_refit``.

    Raises:
        ValueError: If the report, checkpoint, code hashes or any saved refit
            do not match.
    """
    descriptor = seal["artifacts"]["reproduction"]
    root = roots["reproduction"]
    report_path = _find_record(
        root, descriptor["files"], "analysis", "confirmatory_refit_reproduction",
    )
    report = load_mapping(report_path)
    verify_content_hash(report, "report_content_sha256")
    if (report.get("selection") != "all" or report.get("cells_checked") != 450
            or report.get("cells_identical") != 450
            or report.get("evidence_status") != "verification_only"):
        raise ValueError("release requires an exact completed 450-cell reproduction")
    expected = {}
    for _, cell in source.cells:
        key = (cell["dataset"], cell["model_key"], int(cell["repeat"]), int(cell["fold"]))
        expected[":".join(map(str, key))] = key
    rows = report.get("cells", [])
    if (len(rows) != 450 or {row["cell"] for row in rows} != set(expected)
            or any(row.get("identical") is not True or row.get("n_differences") != 0
                   for row in rows)):
        raise ValueError("reproduction report does not cover the full frozen cell grid")
    checkpoint = report["provenance"]
    if (checkpoint.get("source_manifest_sha256") != sha256_file(source.run_dir / "manifest.json")
            or checkpoint.get("source_completion_sha256") != sha256_file(source.run_dir / "completion.json")
            or checkpoint.get("source_file_sha256") != source.source_hashes
            or {tuple(key) for key in checkpoint.get("planned_keys", [])} != set(expected.values())):
        raise ValueError("reproduction source lineage or planned grid changed")
    for relative, digest in checkpoint["actual_code_sha256"].items():
        if seal["code_files"].get(relative) != digest:
            raise ValueError(f"release code differs from reproduction code: {relative}")
    checkpoints = [root / name for name in descriptor["files"]
                   if PurePosixPath(name).name == "reproduction_checkpoint.json"]
    if len(checkpoints) != 1 or load_mapping(checkpoints[0]) != checkpoint:
        raise ValueError("reproduction checkpoint is missing or differs from its report")
    spec = importlib.util.spec_from_file_location(
        "programme_reproduction_verifier", PROJECT_ROOT / "scripts/reproduce_confirmatory_cells.py",
    )
    assert spec is not None and spec.loader is not None
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    for key in expected.values():
        dataset, model, repeat, fold = key
        suffix = f"{dataset}/repeat_{repeat:02d}_fold_{fold:02d}/{model}.json"
        candidates = [root / name for name in descriptor["files"]
                      if name == suffix or name.endswith("/" + suffix)]
        if len(candidates) != 1:
            raise ValueError(f"missing or duplicate reproduction cell: {suffix}")
        result = verifier.check_saved_refit(source.run_dir, candidates[0], key)
        if not result["identical"]:
            raise ValueError(f"saved reproduction differs from original evidence: {suffix}")


def verify_programme(seal: dict[str, Any], roots: dict[str, Path], project_root: Path) -> None:
    """Cross-check sealed artifacts against their stored scientific evidence.

    Every code hash recorded by the sampler run, the reproduction and the two
    renderers must equal the sealed code hash.

    Args:
        seal: Release-ready record containing all evidence descriptors.
        roots: Resolved directories for the seven sealed programme artefacts.
        project_root: Repository containing the sealed actual code and study inputs.

    Raises:
        ValueError: If an artefact fails its evidence check or used code that
            differs from the seal.
    """
    from src.pipelines.robustness.provenance import verify_completed_robustness_run
    from src.rendering.verification import (
        verify_explainability_artifact,
        verify_frozen_run,
        verify_robustness_run,
    )
    from src.utils.frozen_evidence import verify_frozen_evidence
    from src.utils.posthoc_evidence import verify_posthoc_run

    source = verify_frozen_run(roots["original450"])
    if source.mode != "confirmatory" or len(source.cells) != 450:
        raise ValueError("original source must be the completed 450-cell confirmatory run")
    verify_frozen_evidence(project_root, source.manifest["input_sha256"])
    verify_completed_robustness_run(
        roots["robustness"], project_root, confirmatory_run_dir=roots["original450"],
    )
    robustness, robustness_ref = verify_robustness_run(roots["robustness"], source)
    if len(robustness["cells"]) != 825:
        raise ValueError("release requires all 825 planned robustness cells")
    explanation = _find_record(
        roots["explanation"], seal["artifacts"]["explanation"]["files"],
        "analysis", "confirmatory_explainability_from_frozen_cells",
    )
    _, explanation_ref = verify_explainability_artifact(explanation, source)
    posthoc = verify_posthoc_run(roots["sampler_run"], roots["original450"])
    for relative, digest in posthoc["manifest"]["input_sha256"].items():
        if relative.startswith(("src/", "scripts/")) and seal["code_files"].get(relative) != digest:
            raise ValueError(f"release code differs from sampler sensitivity code: {relative}")
    _verify_reproduction(seal, roots, source)
    spec = importlib.util.spec_from_file_location(
        "programme_bundle_verifier", project_root / "scripts/complete_results_programme.py",
    )
    assert spec is not None and spec.loader is not None
    coordinator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(coordinator)
    source_hashes = {"source_run/" + name: digest for name, digest in source.source_hashes.items()}
    source_hashes[explanation_ref["artifact"]] = explanation_ref["sha256"]
    source_hashes.update({
        ref["artifact"]: ref["sha256"] for ref in robustness["source_refs"].values()
    })
    confirmatory_lineage = coordinator.verify_rendered_bundle(
        roots["rendered_confirmatory"], source_dir=roots["original450"],
        expected_optional_sources=[explanation_ref, robustness_ref],
        expected_source_hashes=source_hashes,
    )
    lineage = coordinator.verify_rendered_bundle(
        roots["rendered_posthoc"], source_dir=roots["sampler_run"], posthoc=True,
    )
    renderer_code = {
        confirmatory_lineage["renderer"]["path"]: confirmatory_lineage["renderer"]["sha256"],
        **confirmatory_lineage["renderer"]["module_sha256"],
        **lineage["renderer_input_sha256"],
    }
    for relative, digest in renderer_code.items():
        if seal["code_files"].get(relative) != digest:
            raise ValueError(f"release code differs from renderer code: {relative}")
    if lineage.get("source_cell_sha256") != posthoc["completion"]["cell_sha256"]:
        raise ValueError("posthoc rendering cell inventory differs from its verified source")


def write_archive(path: Path, files: dict[str, Path | bytes]) -> dict[str, str]:
    """Write a reproducible gzip/tar archive of regular files without source metadata.

    Members are written in name order with zero timestamps and owner
    identifiers and fixed permissions, so identical inputs give identical
    archive bytes.

    Args:
        path: New archive path; an existing file is never overwritten.
        files: Member name mapped to a source file or to the member's bytes.

    Returns:
        Member name mapped to the SHA-256 of the bytes written.
    """
    inventory = {}
    with path.open("xb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w|", format=tarfile.PAX_FORMAT) as archive:
                for name, source in sorted(files.items()):
                    safe_relative(name)
                    content = source if isinstance(source, bytes) else source.read_bytes()
                    info = tarfile.TarInfo(name)
                    info.size = len(content)
                    info.mode = 0o644
                    info.mtime = info.uid = info.gid = 0
                    info.uname = info.gname = ""
                    archive.addfile(info, io.BytesIO(content))
                    inventory[name] = hashlib.sha256(content).hexdigest()
    return inventory


def publish_staged_directory(stage: Path, destination: Path) -> None:
    """Claim a fresh directory and install files without replacing any existing path.

    Args:
        stage: Verified staged directory on the same filesystem as the destination.
        destination: Unused output path; its parent must already exist.
    """
    destination.mkdir(exist_ok=False)
    # Hard links install each staged file without copying or overwriting. The
    # release manifest is linked last, so a destination missing it is visibly
    # incomplete.
    files = sorted(path for path in stage.rglob("*") if path.is_file())
    files.sort(key=lambda path: path.name == "programme_release_manifest.json")
    for source in files:
        target = destination / source.relative_to(stage)
        target.parent.mkdir(parents=True, exist_ok=True)
        os.link(source, target)


def package_release(seal_path: Path, project_root: Path, destination: Path) -> Path:
    """Build write-once supplementary assets after every seal and factual gate passes.

    Args:
        seal_path: The final ``programme_release_ready.json`` seal.
        project_root: Repository whose committed and working-tree code the
            seal must match.
        destination: New release directory outside every sealed artefact.

    Returns:
        ``destination``.

    Raises:
        ValueError: If any seal, code or evidence check fails, or an input
            changes while the archives are written.
        FileExistsError: If ``destination`` holds a release for another seal.
    """
    seal, roots = read_release_seal(seal_path)
    seal_digest = sha256_file(seal_path)
    code = committed_code(project_root, seal)
    verify_programme(seal, roots, project_root)
    destination = destination.resolve()
    if any(destination == root or root in destination.parents for root in roots.values()):
        raise ValueError("release output must be outside every immutable artifact")
    if destination.exists():
        from scripts.restore_programme_release import verify_release

        manifest = verify_release(destination, roots["original450"])
        if manifest.get("seal_sha256") != sha256_file(seal_path):
            raise FileExistsError("existing release belongs to a different final seal")
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".programme-package-", dir=destination.parent))
    try:
        assets = {}
        code_name = "programme-committed-code.tar.gz"
        files = write_archive(stage / code_name, {f"code/{name}": value for name, value in code.items()})
        assets[code_name] = {"sha256": sha256_file(stage / code_name), "files": files}
        for archive_name, names in ARCHIVE_GROUPS.items():
            members = {
                f"{name}/{relative}": roots[name] / relative
                for name in names for relative in seal["artifacts"][name]["files"]
            }
            inventory = write_archive(stage / archive_name, members)
            expected = {
                f"{name}/{relative}": digest
                for name in names for relative, digest in seal["artifacts"][name]["files"].items()
            }
            if inventory != expected:
                raise ValueError("artifact changed while its release archive was being written")
            assets[archive_name] = {"sha256": sha256_file(stage / archive_name), "files": inventory}
        metadata = {}
        for name, source_path in {
            "programme_release_ready.json": seal_path,
            "programme_analysis_verified.json": Path(seal["verified_report"]["path"]),
            "programme_visual_qa.json": Path(seal["visual_qa"]["path"]),
        }.items():
            shutil.copyfile(source_path, stage / name)
            metadata[name] = sha256_file(stage / name)
        if metadata["programme_analysis_verified.json"] != seal["verified_report"]["sha256"]:
            raise ValueError("verified report changed during packaging")
        if metadata["programme_visual_qa.json"] != seal["visual_qa"]["sha256"]:
            raise ValueError("visual QA record changed during packaging")
        if read_release_seal(seal_path)[0] != seal or sha256_file(seal_path) != seal_digest:
            raise ValueError("final seal changed during packaging")
        manifest = {
            "schema_version": "1.0.0", "status": "private_supplementary_release",
            "code_commit": seal["code_commit"], "seal_sha256": metadata["programme_release_ready.json"],
            "original_confirmatory_release": seal["artifacts"]["original450"],
            "assets": assets, "metadata_sha256": metadata,
        }
        manifest["manifest_content_sha256"] = canonical_hash(manifest)
        (stage / "programme_release_manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n",
        )
        checksums = directory_inventory(stage)
        (stage / "SHA256SUMS").write_text("".join(
            f"{digest}  {name}\n" for name, digest in checksums.items()
        ))
        from scripts.restore_programme_release import verify_release

        # Verify the staged release exactly as a restorer would before it is
        # installed.
        verify_release(stage, roots["original450"])
        publish_staged_directory(stage, destination)
        return destination
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def main() -> int:
    """Parse explicit source/seal/output paths and build unpublished assets."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seal", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(package_release(args.seal.resolve(), args.project_root.resolve(), args.output_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
