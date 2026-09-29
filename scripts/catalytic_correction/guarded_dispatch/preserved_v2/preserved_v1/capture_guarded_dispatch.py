"""Own the genuine guarded child return; retain failures without retrospective proof."""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any


def bootstrap(request_path: Path, expected: str, *, own_name: str = "capture_guarded_dispatch.py") -> Any:
    """Check externally pinned request/source bytes before private runtime import."""
    if hashlib.sha256(request_path.read_bytes()).hexdigest() != expected:
        raise RuntimeError("externally supplied request hash differs")
    request = json.loads(request_path.read_text())
    code = Path(__file__).absolute().parent
    if code != Path(request["guard_code"]):
        raise RuntimeError("actual source directory differs")
    for name in (own_name, "guard_fit_dispatch.py"):
        path = code / name
        if any(node.is_symlink() for node in (path, *path.parents)) or hashlib.sha256(path.read_bytes()).hexdigest() != request["guard_source_sha256"][name]:
            raise RuntimeError("executing source pin differs")
    alias = "_guard_dispatch_runtime"
    if alias in sys.modules:
        raise RuntimeError("occupied runtime alias")
    specification = importlib.util.spec_from_file_location(alias, code / "guard_fit_dispatch.py")
    if specification is None or specification.loader is None:
        raise RuntimeError("guard source unavailable")
    module = importlib.util.module_from_spec(specification)
    sys.modules[alias] = module
    try:
        specification.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(alias, None)
        raise
    return module


@contextlib.contextmanager
def owned_claim(g: Any, path: Path, request_sha: str, identity: str) -> Iterator[None]:
    """Release only this new, byte-identical own claim; never clear an old claim."""
    g.write_new(path, {"schema_version": 1, "request_sha256": request_sha, "invocation_id": identity,
                       "owner_pid": os.getpid(), "created_at_utc": g.utc_now()})
    expected = g.binding(path)
    try:
        yield
    finally:
        g.require(g.binding(path) == expected, "own claim changed; preserve it for review")
        path.unlink()


def launch(g: Any, args: Any, gates: dict[str, Any], *, invoke: Callable[..., Any] = subprocess.run,
           gates_factory: Callable[..., Any] | None = None, testing: bool = False) -> dict[str, Any]:
    """Validate authority, reserve immutable capture, and wait for the actual guard.

    Only fictional injected tests may supply alternative subprocess/gate code.
    A prior partial namespace without introduction is never adopted on resume.
    """
    g.require(testing or invoke is subprocess.run, "unapproved subprocess injection")
    g.require(testing or gates_factory is None, "unapproved gate injection")
    request = g.document(args.request, args.request_sha256)
    preparation = g.validate_request(request, testing=testing)
    g.match_arguments(args, request)
    observed = g.runtime(args.python)
    g.validate_authority(request, gates, testing=testing)
    root = g.safe(args.output)
    forbidden = [Path(request[key]) for key in ("guard_code", "fit_code", "reproduction_code")]
    forbidden.extend(Path(value) for value in gates["freeze"]["paths"].values())
    forbidden.extend((Path(request["guard_preparation"]["path"]).parent,
                      Path(gates["freeze"]["arithmetic_accounting"]["path"]).parent))
    gates["controller"].prepare_output(root, args.manifest, args.manifest_sha256, forbidden)
    namespace = root / g.NAMESPACE
    g.require(not (namespace / "guard.claim.json").exists(), "guard already owned; no stale clearing")
    if namespace.exists():
        g.require((namespace / "introduction.json").exists(), "prior partial namespace has no introduction; review it")
        previous = g.history(root, request, gates_factory=gates_factory or g.original_gates, testing=testing)
        index, predecessor = previous["invocations"] + 1, previous["last_guard_capture_sha256"]
    else:
        g.account_only(root, request, gates)
        namespace.mkdir()
        (namespace / "invocations").mkdir()
        g.copy_preparation(namespace, request, preparation)
        index, predecessor = 1, None
    identity = uuid.uuid4().hex
    directory = namespace / "invocations" / identity
    directory.mkdir()
    g.copy_authority(directory, args.request, request, args.request_sha256)
    before = g.tree(root, omit_guard=True)
    g.write_new(directory / "launcher_before.json", {"schema_version": 1, "state": before})
    prefix = [request["locked_python"], "-I", "-B", str(Path(request["guard_code"]) / "guard_fit_dispatch.py"),
              *g.guard_cli_args(args.request, args.request_sha256, request), "--invocation-id", identity]
    g.write_new(directory / "launcher_launch.json", {"schema_version": 1, "status": "guard_launch_prepared",
                "test_only_dependency_injection": testing, "request_path": str(args.request), "request_sha256": args.request_sha256,
                "invocation_id": identity, "sequence_index": index, "previous_guard_capture_sha256": predecessor,
                "guard_source_sha256": request["guard_source_sha256"], "guard_argv_prefix": prefix,
                "runtime": observed, "prepared_at_utc": g.utc_now(), "owner_pid": os.getpid()})
    launch_sha = g.binding(directory / "launcher_launch.json")["sha256"]
    argv = [*prefix, "--launch-sha256", launch_sha]
    with owned_claim(g, namespace / "guard.claim.json", args.request_sha256, identity):
        g.require(g.tree(root, omit_guard=True) == before, "root changed before guard launch")
        captured = g.capture(argv, directory, "guard", Path(request["guard_code"]), dict(os.environ), invoke=invoke, testing=testing)
        after = g.tree(root, omit_guard=True)
        g.write_new(directory / "launcher_after.json", {"schema_version": 1, "state": after})
        g.write_new(directory / "launcher_result.json", {"schema_version": 1, "status": "owned_guard_return_recorded",
                    "test_only_dependency_injection": testing, "request_sha256": args.request_sha256,
                    "guard_returncode": captured["returncode"], "guard_invocation_sha256": g.binding(directory / "guard_invocation.json")["sha256"],
                    "before_sha256": g.binding(directory / "launcher_before.json")["sha256"],
                    "after_sha256": g.binding(directory / "launcher_after.json")["sha256"],
                    "scientific_completion_certified": False, "programme_complete": False})
    return g.document(directory / "launcher_result.json")


def main() -> None:
    """Launch only exact actual reviewed request arguments with genuine raw capture."""
    import argparse

    first = argparse.ArgumentParser(add_help=False)
    first.add_argument("--request", type=Path, required=True)
    first.add_argument("--request-sha256", required=True)
    known, _ = first.parse_known_args()
    g = bootstrap(known.request, known.request_sha256)
    try:
        args = g.parser().parse_args()
        request = g.document(args.request, args.request_sha256)
        g.require(sys.flags.isolated == 1 and sys.dont_write_bytecode, "owned launcher requires -I -B")
        g.validate_request(request)
        g.match_arguments(args, request)
        with g.original_gates(request) as gates:
            result = launch(g, args, gates)
        code = result["guard_returncode"]
        if code != 0:
            raise SystemExit(code if type(code) is int and code > 0 else 1)
        print(json.dumps({"status": "owned_guard_capture_completed", "scientific_completion_certified": False}, sort_keys=True))
    finally:
        sys.modules.pop("_guard_dispatch_runtime", None)


if __name__ == "__main__":
    main()
