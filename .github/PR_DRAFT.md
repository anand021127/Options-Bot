# Draft PR: Harden Upstox intraday bot — production readiness

Summary
-------
This PR hardens the intraday trading bot for reliable local and CI usage:

- Persist Upstox auth token and refresh flows.
- Replace deprecated Upstox websocket streaming with robust REST polling.
- Remove all developer/mock fallbacks from production code paths.
- Add safe paper execution that uses real LTP from market data.
- Fix broadcast wiring in `BotEngine` and wire WebSocket manager at startup.
- Add replay harness for local end-to-end testing without a live token.
- Add unit + e2e tests (e2e skips when no `UPSTOX_TOKEN` present).
- Add CI job gating for optional E2E runs behind `UPSTOX_TOKEN` secret.
- Startup warnings for any `DEV_*/MOCK_/TEST_` env vars.

Files of interest
-----------------
- `backend/data/upstox_market.py` — REST polling, removed mocks.
- `backend/core/bot_engine.py` — broadcast wiring fix.
- `backend/execution/engine.py` — safer paper execution.
- `tools/replay_harness.py` — local-only replay harness.
- `tools/replay_harness_README.md` — usage guide.
- `tests/` — new unit and e2e tests.
- `.github/workflows/ci.yml` — CI additions for optional E2E runs.

Testing
-------
Local:

1. Start backend:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --app-dir backend
```

2. Run unit tests:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

3. For end-to-end local testing without a token:

```powershell
python tools/replay_harness.py --symbol NIFTY --ohlcv sample.csv --rate 1
# then exercise the app endpoints / UI to observe signals and simulated fills
```

CI:

- Lint and unit tests run on every push.
- Optional E2E workflow job runs only when repository secret `UPSTOX_TOKEN` is set.

Review checklist
----------------
- [ ] Confirm removal of any remaining mock/data fallbacks.
- [ ] Verify no production code writes synthetic data to DB.
- [ ] Spot-check performance and polling intervals for REST usage.
- [ ] Run CI with `UPSTOX_TOKEN` (if available) to validate E2E acceptance.

Notes for maintainers
--------------------
- The replay harness is for developer testing only and intentionally writes
  to internal module caches — it should not be used in production.
- If you'd like, I can open the PR on your behalf (requires repo push/PR
  permissions). Otherwise, push your branch and paste the PR body into GitHub.
