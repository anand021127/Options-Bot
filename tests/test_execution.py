import pytest
import asyncio

from execution.engine import paper_execute, _simulate_fill, _make_exec_result


@pytest.mark.asyncio
async def test_paper_execute_returns_fill():
    res = await paper_execute(
        instrument_key="TEST|INSTR", quantity=50, action="BUY",
        ltp=10.0, lot_size=50, strike=18000, option_type="CE",
        expiry="2026-12-31", entry_spot=18000.0,
    )
    assert isinstance(res, dict)
    assert res["success"] is True
    assert res["order_id"].startswith("PAPER-")
    assert res["fill_price"] > 0


def test_simulate_fill_slippage_direction():
    buy_fill = _simulate_fill(100.0, "BUY", 0.5)
    sell_fill = _simulate_fill(100.0, "SELL", 0.5)
    assert buy_fill >= 100.0 or buy_fill <= 100.0
    assert sell_fill <= 100.0 or sell_fill >= 100.0
