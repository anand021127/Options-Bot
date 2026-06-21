import asyncio
import pytest

from httpx import AsyncClient, ASGITransport

from backend.main import app
from api.upstox_auth import get_upstox_token


@pytest.mark.asyncio
async def test_health_and_paper_start_requires_token():
    """End-to-end acceptance: health endpoint + start in paper mode.

    This test requires a valid Upstox token stored via the dashboard. If no
    token is available, the test is skipped to avoid using mocked data.
    """
    token = await get_upstox_token()

    # Prefer running the application's lifespan so startup handlers run
    # (this will initialize `app.state.bot_engine` and other background tasks).
    use_lifespan = hasattr(app.router, "lifespan_context")

    if use_lifespan:
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                r = await ac.get("/health")
                assert r.status_code == 200
                data = r.json()
                assert "status" in data

                if not token:
                    pytest.skip("No Upstox token available — skipping integration test")

                # If token exists, attempt to start the bot in paper mode and ensure
                # endpoints respond and trades/history can be queried.
                start = await ac.post("/api/bot/start", json={
                    "symbol": "NIFTY", "capital": 100000, "mode": "paper"
                })
                assert start.status_code in (200, 201)

                # Give the bot a short moment to generate (or attempt) signals
                await asyncio.sleep(3)

                history = await ac.get("/api/trades/history")
                assert history.status_code == 200
                # Response should be JSON list (possibly empty)
                assert isinstance(history.json(), list)

    else:
        # Fallback for environments where lifespan_context isn't exposed.
        from types import SimpleNamespace
        if not hasattr(app.state, "bot_engine"):
            app.state.bot_engine = SimpleNamespace(is_running=False, mode="idle")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.get("/health")
            assert r.status_code == 200
            data = r.json()
            assert "status" in data

            if not token:
                pytest.skip("No Upstox token available — skipping integration test")

            start = await ac.post("/api/bot/start", json={
                "symbol": "NIFTY", "capital": 100000, "mode": "paper"
            })
            assert start.status_code in (200, 201)

            # Give the bot a short moment to generate (or attempt) signals
            await asyncio.sleep(3)

            history = await ac.get("/api/trades/history")
            assert history.status_code == 200
            # Response should be JSON list (possibly empty)
            assert isinstance(history.json(), list)
