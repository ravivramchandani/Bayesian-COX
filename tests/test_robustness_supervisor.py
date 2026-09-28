"""The finish supervisor must distinguish this run's workers from unrelated jobs.

Covers ``active_workers`` in ``scripts/wait_for_robustness.py``, which scans the
process table so that the final unsharded ``--resume`` of a sharded robustness
run (ADR-031) starts only after that checkout's own shard workers have exited.
The process table is faked; no process is started.
"""

from pathlib import Path
from types import SimpleNamespace

from scripts.wait_for_robustness import active_workers


def test_worker_detection_is_specific_to_checkout_and_worker_script(monkeypatch) -> None:
    """Only shard workers whose argument is exactly this checkout path count as active (ADR-031)."""
    # Fake ``ps -axo pid=,args=`` output. 101 is the target worker; 102 is a
    # worker for another checkout; 103 runs a different script on the same
    # checkout; 104 has a quoted path that merely starts with "/runs/frozen",
    # so a substring match would wrongly count it for that checkout.
    table = (
        "101 /env/python /runs/harness/shard_worker.py /runs/frozen /runs/claims 0\n"
        "102 /env/python /runs/harness/shard_worker.py /runs/other /runs/claims 1\n"
        "103 /env/python /runs/harness/check.py /runs/frozen\n"
        "104 /env/python /runs/harness/shard_worker.py '/runs/frozen space' /runs/claims 2\n"
    )
    monkeypatch.setattr(
        "scripts.wait_for_robustness.subprocess.run", lambda *_, **__: SimpleNamespace(stdout=table)
    )
    assert active_workers(Path("/runs/frozen")) == [101]
    assert active_workers(Path("/runs/frozen space")) == [104]
