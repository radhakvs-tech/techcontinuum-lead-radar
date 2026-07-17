"""Thin subprocess wrapper around the real `vpai` CLI, plus retry and
caching behaviour. Spec §6, §20 (Phase 2: "Inspect and implement the
available Vibe interface... Retry and caching behaviour").

`VibeProvider` depends on the `VpaiRunner` protocol, never on
`SubprocessVpaiRunner` directly — tests construct `VibeProvider` with a fake
runner that returns canned JSON and never shells out to the real CLI, so no
test in this repository spends real Vibe Prospecting credits or requires
`vpai` to be installed. `SubprocessVpaiRunner` is the only piece of this
codebase that actually invokes the binary.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from typing import Any, Protocol


class VpaiCommandError(Exception):
    """Raised when a vpai invocation fails or returns unparseable output."""


class VpaiRunner(Protocol):
    def run(
        self,
        command: str,
        *,
        args: dict[str, Any] | None = None,
        tool_reasoning: str | None = None,
        number_of_results: int | None = None,
        session_id: str | None = None,
        csv_path: str | None = None,
    ) -> dict[str, Any]: ...


class SubprocessVpaiRunner:
    """Real implementation. Never constructed in tests.

    Retry policy is deliberately conservative given vpai calls spend real
    credits: we only retry failures that could not possibly have reached
    Explorium's API — the binary missing (`FileNotFoundError`) or the
    process hanging past `timeout_seconds` before any response
    (`subprocess.TimeoutExpired`). A non-zero exit *with* stderr output, or
    unparseable stdout, means the process ran and vpai itself reported an
    outcome — that could mean the request was already billed, so those are
    surfaced immediately as `VpaiCommandError` rather than retried.
    """

    def __init__(
        self,
        binary: str = "vpai",
        max_retries: int = 2,
        retry_backoff_seconds: float = 1.0,
        timeout_seconds: float = 120.0,
    ) -> None:
        self._binary = binary
        self._max_retries = max_retries
        self._retry_backoff_seconds = retry_backoff_seconds
        self._timeout_seconds = timeout_seconds

    def _argv(
        self,
        command: str,
        args: dict[str, Any] | None,
        tool_reasoning: str | None,
        number_of_results: int | None,
        session_id: str | None,
        csv_path: str | None,
    ) -> list[str]:
        argv = [self._binary, command]
        if args is not None:
            argv += ["--args", json.dumps(args)]
        if tool_reasoning is not None:
            argv += ["--tool-reasoning", tool_reasoning]
        if number_of_results is not None:
            argv += ["--number-of-results", str(number_of_results)]
        if session_id is not None:
            argv += ["--session-id", session_id]
        if csv_path is not None:
            argv += ["--csv-path", csv_path]
        return argv

    def run(
        self,
        command: str,
        *,
        args: dict[str, Any] | None = None,
        tool_reasoning: str | None = None,
        number_of_results: int | None = None,
        session_id: str | None = None,
        csv_path: str | None = None,
    ) -> dict[str, Any]:
        argv = self._argv(command, args, tool_reasoning, number_of_results, session_id, csv_path)

        attempt = 0
        while True:
            try:
                result = subprocess.run(
                    argv, capture_output=True, text=True, timeout=self._timeout_seconds
                )
            except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
                if attempt >= self._max_retries:
                    raise VpaiCommandError(
                        f"vpai {command} failed to run after {attempt + 1} attempt(s): {exc}"
                    ) from exc
                time.sleep(self._retry_backoff_seconds * (2**attempt))
                attempt += 1
                continue

            if result.returncode != 0:
                raise VpaiCommandError(
                    f"vpai {command} failed (exit {result.returncode}): {result.stderr.strip()}"
                )
            try:
                parsed: dict[str, Any] = json.loads(result.stdout)
            except json.JSONDecodeError as exc:
                raise VpaiCommandError(
                    f"vpai {command} returned non-JSON output: {result.stdout[:500]!r}"
                ) from exc
            return parsed


def _cache_key(
    command: str,
    args: dict[str, Any] | None,
    number_of_results: int | None,
    session_id: str | None,
    csv_path: str | None,
) -> str:
    payload = json.dumps(
        {
            "command": command,
            "args": args,
            "number_of_results": number_of_results,
            "session_id": session_id,
            "csv_path": csv_path,
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class CachingVpaiRunner:
    """Wraps any `VpaiRunner` and memoizes identical calls for the lifetime
    of this instance (spec §20 Phase 2 "caching behaviour"). An identical
    (command, args, number_of_results, session_id, csv_path) tuple within a
    run is answered from cache instead of spending credits again — the
    pipeline running twice over the same account within one process must
    not double-charge.

    Deliberately in-memory and per-instance, not persisted across runs:
    caching stale account data across separate pipeline runs would be
    wrong (the whole point of re-running is to catch new signals), so this
    only protects against redundant calls *within* a single run.
    """

    def __init__(self, wrapped: VpaiRunner) -> None:
        self._wrapped = wrapped
        self._cache: dict[str, dict[str, Any]] = {}
        self.cache_hits = 0
        self.cache_misses = 0

    def run(
        self,
        command: str,
        *,
        args: dict[str, Any] | None = None,
        tool_reasoning: str | None = None,
        number_of_results: int | None = None,
        session_id: str | None = None,
        csv_path: str | None = None,
    ) -> dict[str, Any]:
        key = _cache_key(command, args, number_of_results, session_id, csv_path)
        if key in self._cache:
            self.cache_hits += 1
            return self._cache[key]

        self.cache_misses += 1
        response = self._wrapped.run(
            command,
            args=args,
            tool_reasoning=tool_reasoning,
            number_of_results=number_of_results,
            session_id=session_id,
            csv_path=csv_path,
        )
        self._cache[key] = response
        return response
