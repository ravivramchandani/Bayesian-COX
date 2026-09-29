"""Continue only audited pre-fit stages from explicit immutable bindings."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

THREADS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS")


def require(condition: bool, message: str) -> None:
    """Refuse unsafe orchestration without changing a scientific outcome."""
    if not condition:
        raise ValueError(message)


def sha(path: Path) -> str:
    """Hash one ordinary explicitly located file."""
    require(path.is_absolute() and ".." not in path.parts
            and not any(item.is_symlink() for item in (path, *path.parents))
            and path.is_file(), f"unsafe or missing file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read(path: Path, expected: str | None = None) -> dict[str, Any]:
    """Read finite canonical receipts while checking actual bytes."""
    before = sha(path)
    require(expected is None or before == expected, "receipt byte binding differs")
    value = json.loads(path.read_text(), parse_constant=lambda item: (_ for _ in ()).throw(ValueError(item)))
    require(isinstance(value, dict), "receipt must be a mapping")
    body = {key: item for key, item in value.items() if key != "content_sha256"}
    digest = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    require(value["content_sha256"] == digest and sha(path) == before, "receipt content binding differs")
    return value


def publish(path: Path, body: dict[str, Any]) -> None:
    """Publish a new fsynced receipt exclusively; never replace an attempt."""
    require("content_sha256" not in body and not path.exists(), "receipt already exists")
    prefix = ".continuation-" + path.name + "-"
    require(not list(path.parent.glob(prefix + "*")), "prior attributable publication residue requires review")
    body = {**body, "content_sha256": hashlib.sha256(json.dumps(body, sort_keys=True,
        separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()}
    payload = (json.dumps(body, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()
    descriptor, name = tempfile.mkstemp(prefix=prefix, dir=path.parent)
    temporary = Path(name)

    def sync_parent() -> None:
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)

    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
        sync_parent()
        temporary.unlink()
        sync_parent()
        require(not list(path.parent.glob(prefix + "*")), "attributable publication residue remains")
    except BaseException:
        # Keep attributable closed bytes for review if publication/cleanup fails.
        sync_parent()
        raise


def complete_preflight(path: Path) -> dict[str, Any]:
    """Require full outcome accounting, allowing explicitly terminal failures."""
    value = read(path)
    require(value["status"] == "all_scheduled_contexts_accounted"
            and value["scheduled_contexts"] == value["accounted_contexts"] == 1650
            and len(value["outcomes"]) == 1650
            and len({row["context_id"] for row in value["outcomes"]}) == 1650,
            "complete1650 preflight required")
    return value


def verify_code(request: dict[str, Any]) -> None:
    """Check clean detached implementation and every supplied source pin."""
    code = Path(request["paths"]["code"])
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=code, text=True).strip()
    status = subprocess.check_output(["git", "status", "--porcelain"], cwd=code, text=True)
    require(commit == request["code_commit"] and not status, "continuation code checkout changed")
    for name, digest in request["code_sha256"].items():
        require(not Path(name).is_absolute() and ".." not in Path(name).parts
                and sha(code / name) == digest, "continuation source bytes changed")
    require(sha(Path(__file__).absolute()) == request["continuation_source_sha256"], "continuation source changed")


def preflight_running(request: dict[str, Any]) -> bool:
    """Reject a reused PID rather than wait for an unrelated process."""
    try:
        os.kill(request["preflight_pid"], 0)
    except ProcessLookupError:
        return False
    result = subprocess.run(["ps", "-p", str(request["preflight_pid"]), "-o", "command="],
                            capture_output=True, check=False)
    require(result.returncode == 0 and hashlib.sha256(result.stdout).hexdigest()
            == request["preflight_process_command_sha256"], "original preflight PID identity changed")
    return True


def safe_destination(request: dict[str, Any]) -> Path:
    """Refuse output overlaps before creating logs or a launch receipt."""
    paths = {name: Path(value) for name, value in request["paths"].items()}
    output = paths["continuation"]
    require(output.is_absolute() and ".." not in output.parts
            and not any(path.is_symlink() for path in (output, *output.parents)), "unsafe continuation output")
    require(all(path.is_absolute() and ".." not in path.parts
                and (name == "python" or not any(node.is_symlink() for node in (path, *path.parents)))
                and not output.is_relative_to(path) and not path.is_relative_to(output)
                for name, path in paths.items() if name != "continuation"),
            "continuation output overlaps input or another stage")
    if "python" in paths:
        target = paths["python"].resolve(strict=True)
        require(target.is_file() and target.samefile(Path(sys.executable))
                and not any(node.is_symlink() for node in (target, *target.parents)),
                "only an alias of the actual locked interpreter is permitted")
    require(not output.exists() and output.parent.is_dir(), "new existing-parent continuation output required")
    return output


def execute(label: str, command: list[str], output: Path, env: dict[str, str]) -> None:
    """Retain raw logs and actual process result before any next stage."""
    started, clock = datetime.now(UTC).isoformat(), time.monotonic()
    print(json.dumps({"stage": label, "status": "starting", "started_at_utc": started}), flush=True)
    with (output / f"{label}.stdout.log").open("xb") as stdout, (output / f"{label}.stderr.log").open("xb") as stderr:
        result = subprocess.run(command, env=env, stdout=stdout, stderr=stderr, check=False)
        for stream in (stdout, stderr):
            stream.flush()
            os.fsync(stream.fileno())
    publish(output / f"{label}.invocation.json", {"argv": command, "started_at_utc": started,
        "finished_at_utc": datetime.now(UTC).isoformat(), "wall_seconds": time.monotonic() - clock,
        "exit_code": result.returncode, "numeric_threads": {name: env[name] for name in THREADS},
        "stdout_sha256": sha(output / f"{label}.stdout.log"), "stderr_sha256": sha(output / f"{label}.stderr.log")})
    require(result.returncode == 0, f"{label} failed; retain and review this attempt")


def run(request: dict[str, Any], output: Path) -> None:
    """Wait, then run first-draw/input witnesses and changed-input arithmetic."""
    paths = {key: Path(value) for key, value in request["paths"].items()}
    require(paths["python"].samefile(Path(sys.executable)), "actual continuation interpreter differs")
    require(all(os.environ.get(name) == "1" for name in THREADS), "numeric-one environment required")
    verify_code(request)
    preflight = paths["preflight"]
    read(paths["preflight_launch"], request["preflight_launch_sha256"])
    while True:
        complete = preflight / "completion.json"
        if not preflight_running(request):
            require(complete.exists() and not any((preflight / name).exists()
                    for name in ("controller.claim.json", "launcher.claim.json")),
                    "preflight exited without complete unclaimed evidence; review its retained diagnostics")
            break
        print(json.dumps({"stage": "wait_preflight", "checked_at_utc": datetime.now(UTC).isoformat(),
                          "expected_pid": request["preflight_pid"]}), flush=True)
        time.sleep(30)
    completion = complete_preflight(complete)
    manifest = read(preflight / "manifest.json", request["preflight_manifest_sha256"])
    require(manifest["content_sha256"] == completion["run_binding_sha256"], "preflight run binding differs")
    verify_code(request)
    publish(output / "preflight_ready.json", {"checked_at_utc": datetime.now(UTC).isoformat(),
        "completion_sha256": sha(complete), "manifest_sha256": sha(preflight / "manifest.json"),
        "outcome_counts": completion["outcome_counts"], "corrected_fitting_approved": False})
    folder = paths["code"] / "scripts/catalytic_correction"
    pins = request["code_sha256"]
    command = [str(paths["python"]), "-B", str(folder / "run_reuse.py")]
    values = {"source": paths["source"], "run": paths["original_run"], "matched": paths["matched"],
        "inventory": paths["recipes"], "candidate-module": paths["code"] / "src/pipelines/extensions/correction_generator.py",
        "correction-config": paths["code"] / "config/catalytic_correction.yaml",
        "correction-addendum": paths["code"] / "docs/protocol_addendum_catalytic_correction.md",
        "preflight-output": preflight, "preflight-core": folder / "preflight_core.py",
        "preflight-runner": folder / "run_preflight.py", "contracts-module": folder / "correction_fit_contracts.py",
        "output": paths["witness"], "python": paths["python"],
        "preflight-manifest-sha256": sha(preflight / "manifest.json"), "preflight-completion-sha256": sha(complete)}
    pin_roles = {"candidate": "src/pipelines/extensions/correction_generator.py",
        "preflight-core": "scripts/catalytic_correction/preflight_core.py",
        "preflight-runner": "scripts/catalytic_correction/run_preflight.py",
        "contracts": "scripts/catalytic_correction/correction_fit_contracts.py",
        "reuse-core": "scripts/catalytic_correction/reuse_core.py",
        "reuse-runner": "scripts/catalytic_correction/run_reuse.py",
        "first-draw-child": "scripts/catalytic_correction/normal_first_draw_child.py",
        "correction-config": "config/catalytic_correction.yaml",
        "correction-addendum": "docs/protocol_addendum_catalytic_correction.md"}
    values.update({name + "-sha256": pins[relative] for name, relative in pin_roles.items()})
    for name, value in values.items():
        command.extend(["--" + name, str(value)])
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    execute("reuse", command, output, environment)
    verify_code(request)
    final = json.loads((output / "reuse.stdout.log").read_text().splitlines()[-1])
    require(final["status"] == "complete_witness_inventory_sealed" and final["fit_dispatched"] is False,
            "whole actual input witness inventory required")
    inventory_path = Path(final["inventory"])
    require(inventory_path.is_relative_to(paths["witness"]), "unexpected inventory root")
    inventory = read(inventory_path, final["inventory_sha256"])
    require(inventory["scheduled_cells"] == len(inventory["entries"]) == 1625, "whole1625 inventory required")
    command = [str(paths["python"]), "-B", str(folder / "run_arithmetic.py")]
    values = {"source-checkout": paths["source"], "preflight-root": preflight,
        "witness-root": paths["witness"], "inventory": inventory_path,
        "python": paths["python"], "output": paths["arithmetic"],
        "completion-sha256": sha(complete), "replay-sha256": sha(paths["witness"] / "replay/completion.json"),
        "selector-sha256": sha(paths["witness"] / "arithmetic_selector.json"),
        "definition-sha256": sha(paths["witness"] / "definition.json"), "inventory-sha256": sha(inventory_path)}
    for name, value in values.items():
        command.extend(["--" + name, str(value)])
    execute("arithmetic", command, output, environment)
    verify_code(request)
    account = read(paths["arithmetic"] / "accounting.json")
    require(account["status"] == "all_scheduled_arithmetic_outcomes_accounted"
            and len(account["context_outcomes"]) == 1650, "whole1650 arithmetic accounting required")
    publish(output / "pre_fit_evidence_prepared.json", {"status": "pre_fit_evidence_prepared",
        "finished_at_utc": datetime.now(UTC).isoformat(), "inventory": str(inventory_path),
        "inventory_sha256": sha(inventory_path), "arithmetic": str(paths["arithmetic"] / "accounting.json"),
        "arithmetic_sha256": sha(paths["arithmetic"] / "accounting.json"),
        "actual_corrected_fits": 0, "scientific_method_approved": False,
        "pending": ["actual_root_execution_reviews", "corrected_freeze", "full_budget_pilot", "pilot_review"]})


def main() -> int:
    """Run one newly owned orchestration attempt without automatic recovery."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--request-sha256", required=True)
    args = parser.parse_args()
    request = read(args.request, args.request_sha256)
    require(request["schema_version"] == 1 and request["status"] == "authorised_pre_fit_continuation"
            and request["host"] == socket.gethostname() and request["corrected_fitting_approved"] is False,
            "explicit same-host pre-fit-only request required")
    output = safe_destination(request)
    output.mkdir()
    publish(output / "launch.json", {"request_sha256": args.request_sha256, "pid": os.getpid(),
        "host": socket.gethostname(), "started_at_utc": datetime.now(UTC).isoformat()})
    try:
        run(request, output)
    except BaseException as error:
        publish(output / "failure.json", {"exception_type": type(error).__name__, "message": str(error),
            "failed_at_utc": datetime.now(UTC).isoformat(), "corrected_fitting_approved": False})
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
