import pytest
import asyncio

from loguru import logger

import core.bot_engine as be


@pytest.mark.asyncio
async def test_broadcast_wireup_and_call(monkeypatch):
    calls = []

    async def fake_broadcast(payload):
        calls.append(payload)

    # Ensure module-level setter works
    be.set_broadcast_fn(fake_broadcast)

    # Call private _broadcast to simulate event
    await be._broadcast("unit_test", {"ok": True})
    assert calls and calls[0]["event"] == "unit_test"

    # Ensure instance method delegates to module setter
    engine = be.BotEngine()
    engine.set_broadcast_fn(fake_broadcast)
    await be._broadcast("unit_test2", {"ok": True})
    assert any(c["event"] == "unit_test2" for c in calls)
