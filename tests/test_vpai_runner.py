"""Spec §20 Phase 2 'retry and caching behaviour'. Never invokes the real
vpai binary — subprocess.run is monkeypatched so these tests run offline
and never spend real credits."""

from __future__ import annotations

import subprocess
from typing import Any

import pytest

from lead_radar.providers.vpai_runner import (
    CachingVpaiRunner,
    SubprocessVpaiRunner,
    VpaiCommandError,
)


class _FakeCompletedProcess:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_successful_call_parses_json_stdout(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(argv: list[str], **kwargs: Any) -> _FakeCompletedProcess:
        assert argv[:2] == ["vpai", "fetch-entities"]
        return _FakeCompletedProcess(0, stdout='{"row_count": 1}')

    monkeypatch.setattr(subprocess, "run", fake_run)
    runner = SubprocessVpaiRunner()
    result = runner.run("fetch-entities", args={"entity_type": "businesses"})
    assert result == {"row_count": 1}


def test_nonzero_exit_raises_immediately_without_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def fake_run(argv: list[str], **kwargs: Any) -> _FakeCompletedProcess:
        calls.append(argv)
        return _FakeCompletedProcess(1, stderr="bad args")

    monkeypatch.setattr(subprocess, "run", fake_run)
    runner = SubprocessVpaiRunner(max_retries=3)
    with pytest.raises(VpaiCommandError, match="bad args"):
        runner.run("fetch-entities")
    # A non-zero exit means the process ran and vpai reported an outcome —
    # possibly already billed — so it must NOT be retried.
    assert len(calls) == 1


def test_non_json_stdout_raises_immediately_without_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def fake_run(argv: list[str], **kwargs: Any) -> _FakeCompletedProcess:
        calls.append(argv)
        return _FakeCompletedProcess(0, stdout="not json")

    monkeypatch.setattr(subprocess, "run", fake_run)
    runner = SubprocessVpaiRunner(max_retries=3)
    with pytest.raises(VpaiCommandError, match="non-JSON"):
        runner.run("fetch-entities")
    assert len(calls) == 1


def test_process_launch_failure_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = {"count": 0}

    def fake_run(argv: list[str], **kwargs: Any) -> _FakeCompletedProcess:
        attempts["count"] += 1
        if attempts["count"] < 2:
            raise subprocess.TimeoutExpired(cmd=argv, timeout=1)
        return _FakeCompletedProcess(0, stdout="{}")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    runner = SubprocessVpaiRunner(max_retries=2, retry_backoff_seconds=0.01)
    result = runner.run("fetch-entities")
    assert result == {}
    assert attempts["count"] == 2


def test_process_launch_failure_gives_up_after_max_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(argv: list[str], **kwargs: Any) -> _FakeCompletedProcess:
        raise FileNotFoundError("vpai binary not found")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    runner = SubprocessVpaiRunner(max_retries=2, retry_backoff_seconds=0.01)
    with pytest.raises(VpaiCommandError, match="failed to run"):
        runner.run("fetch-entities")


class _RecordingRunner:
    def __init__(self, response: dict[str, Any]) -> None:
        self._response = response
        self.call_count = 0

    def run(self, command: str, **kwargs: Any) -> dict[str, Any]:
        self.call_count += 1
        return self._response


def test_caching_runner_returns_cached_response_for_identical_call() -> None:
    inner = _RecordingRunner({"row_count": 5})
    cached = CachingVpaiRunner(inner)

    first = cached.run("fetch-entities", args={"entity_type": "businesses"}, number_of_results=5)
    second = cached.run("fetch-entities", args={"entity_type": "businesses"}, number_of_results=5)

    assert first == second == {"row_count": 5}
    assert inner.call_count == 1
    assert cached.cache_hits == 1
    assert cached.cache_misses == 1


def test_caching_runner_treats_different_args_as_different_calls() -> None:
    inner = _RecordingRunner({"row_count": 5})
    cached = CachingVpaiRunner(inner)

    cached.run("fetch-entities", args={"entity_type": "businesses"})
    cached.run("fetch-entities", args={"entity_type": "prospects"})

    assert inner.call_count == 2
    assert cached.cache_misses == 2
    assert cached.cache_hits == 0
