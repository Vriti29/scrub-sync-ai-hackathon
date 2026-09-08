from __future__ import annotations

import asyncio
import json
import statistics
import time
from pathlib import Path

import pytest

from backend.fencer import EpochManager, StaleEpochException
from backend.tools.ehr_service import (
    fetch_arterial_blood_gas,
    fetch_electrolyte_panel,
)


@pytest.mark.asyncio
async def test_exact_mid_tool_interruption_ten_trials() -> None:
    """
    Real elapsed measurements of coroutine cancellation, not acoustic cutoff.

    Every trial starts a 2.5-second EHR request, waits 500 ms, then advances
    from epoch 1 to epoch 2. No provider credentials are needed.
    """
    records = []

    for trial in range(1, 11):
        manager = EpochManager()
        assert manager.advance_epoch() == 1
        audio_queue: asyncio.Queue[dict] = asyncio.Queue()

        async def query_and_commit() -> None:
            result = await manager.run_fenced_task(
                1, fetch_electrolyte_panel("DEMO-001", 2.5)
            )
            manager.commit(1, lambda: audio_queue.put_nowait(result))

        task = asyncio.create_task(query_and_commit())
        await asyncio.sleep(0.5)

        started = time.perf_counter_ns()
        assert manager.advance_epoch() == 2
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=0.15)
        cancellation_ms = (time.perf_counter_ns() - started) / 1e6

        assert cancellation_ms < 150
        assert task.cancelled()
        assert audio_queue.empty()

        stale_rejected = False
        try:
            manager.commit(1, lambda: audio_queue.put_nowait({"stale": True}))
        except StaleEpochException:
            stale_rejected = True
        assert stale_rejected
        assert audio_queue.empty()

        records.append(
            {
                "trial": trial,
                "tool_delay_ms": 2500,
                "interrupt_after_ms": 500,
                "cancellation_ms": cancellation_ms,
                "stale_commit_rejected": stale_rejected,
                "stale_audio_queue_items": audio_queue.qsize(),
                "rime_ttfa_ms": None,
                "vad_acoustic_latency_ms": None,
                "acoustic_cutoff_ms": None,
            }
        )

    artifact = {
        "measurement_boundary": "Python task cancellation and fenced queue commit",
        "clock": "time.perf_counter_ns",
        "trial_count": len(records),
        "cancellation_p50_ms": statistics.median(
            record["cancellation_ms"] for record in records
        ),
        "cancellation_max_ms": max(record["cancellation_ms"] for record in records),
        "trials": records,
    }
    directory = Path("artifacts")
    directory.mkdir(exist_ok=True)
    (directory / "interruption-benchmark.json").write_text(
        json.dumps(artifact, indent=2), encoding="utf-8"
    )


@pytest.mark.asyncio
async def test_cancellation_resistant_tool_cannot_commit() -> None:
    manager = EpochManager(initial_epoch=1)
    started = asyncio.Event()
    cancellation_seen = asyncio.Event()
    audio_queue: asyncio.Queue[dict] = asyncio.Queue()

    async def cancellation_resistant_database() -> dict:
        started.set()
        try:
            await asyncio.sleep(2.5)
        except asyncio.CancelledError:
            cancellation_seen.set()
            # Reproduce an external operation that resolves after cancellation.
            await asyncio.sleep(0.02)
        return {"potassium": 3.1, "origin": "late database result"}

    async def run() -> None:
        result = await manager.run_fenced_task(
            1, cancellation_resistant_database()
        )
        manager.commit(1, lambda: audio_queue.put_nowait(result))

    task = asyncio.create_task(run())
    await started.wait()
    manager.advance_epoch()

    with pytest.raises(StaleEpochException):
        await asyncio.wait_for(task, timeout=1)

    assert cancellation_seen.is_set()
    assert manager.stale_rejections >= 1
    assert audio_queue.empty()


@pytest.mark.asyncio
async def test_new_epoch_abg_survives_old_epoch_cancellation() -> None:
    manager = EpochManager(initial_epoch=1)
    old = asyncio.create_task(
        manager.run_fenced_task(
            1, fetch_electrolyte_panel("DEMO-001", 2.5)
        )
    )
    await asyncio.sleep(0.01)
    manager.advance_epoch()
    result = await manager.run_fenced_task(
        2, fetch_arterial_blood_gas("DEMO-001", 0.01)
    )
    with pytest.raises(asyncio.CancelledError):
        await old
    assert result["panel"] == "abg"
    assert result["ph"]["value"] == 7.26
    assert result["pco2"]["value"] == 48


@pytest.mark.asyncio
async def test_already_stale_coroutine_is_closed() -> None:
    manager = EpochManager(initial_epoch=2)
    with pytest.raises(StaleEpochException):
        await manager.run_fenced_task(
            1, fetch_electrolyte_panel("DEMO-001", 0)
        )


@pytest.mark.asyncio
async def test_thread_originated_advance_cancels_owned_loop_task() -> None:
    manager = EpochManager(initial_epoch=1)
    task = asyncio.create_task(
        manager.run_fenced_task(
            1, fetch_electrolyte_panel("DEMO-001", 2.5)
        )
    )
    await asyncio.sleep(0.01)
    epoch = await asyncio.to_thread(manager.advance_epoch)
    assert epoch == 2
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, 0.15)


@pytest.mark.asyncio
async def test_stale_result_cannot_cross_commit_race() -> None:
    manager = EpochManager(initial_epoch=1)
    result = await manager.run_fenced_task(
        1, fetch_electrolyte_panel("DEMO-001", 0)
    )
    manager.advance_epoch()
    committed: list[dict] = []
    with pytest.raises(StaleEpochException):
        manager.commit(1, lambda: committed.append(result))
    assert committed == []


@pytest.mark.asyncio
async def test_only_synthetic_patient_is_available() -> None:
    with pytest.raises(ValueError):
        await fetch_electrolyte_panel("REAL-PATIENT", 0)