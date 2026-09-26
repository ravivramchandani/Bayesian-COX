"""The finish supervisor must distinguish this run's workers from unrelated jobs."""

from pathlib import Path
from types import SimpleNamespace

from scripts.wait_for_robustness import active_workers


def test_worker_detection_is_specific_to_checkout_and_worker_script(monkeypatch) -> None:
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
