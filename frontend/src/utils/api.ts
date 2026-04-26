const BASE = process.env.NEXT_PUBLIC_API_URL?.trim() || '';

async function req(path: string, options?: RequestInit) {
  const url = `${BASE}${path}`;
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) throw new Error(`API ${path} → ${res.status}`);
  return res.json();
}

export const api = {
  // ── Bot control ───────────────────────────────────────────────────────────
  startBot:       (symbol: string, capital: number, mode = 'paper') =>
    req('/api/bot/start', { method: 'POST', body: JSON.stringify({ symbol, capital, mode }) }),
  stopBot:        () => req('/api/bot/stop',           { method: 'POST' }),
  emergencyStop:  () => req('/api/bot/emergency-stop', { method: 'POST' }),
  haltTrading:    () => req('/api/bot/halt',            { method: 'POST' }),
  resumeTrading:  () => req('/api/bot/resume',          { method: 'POST' }),
  getBotStatus:   () => req('/api/bot/status'),
  updateBotConfig:(data: Record<string, any>) =>
    req('/api/bot/config', { method: 'POST', body: JSON.stringify(data) }),
  updateFilters:  (filters: Record<string, boolean>) =>
    req('/api/bot/filters', { method: 'POST', body: JSON.stringify({ filters }) }),

  // ── Upstox OAuth ──────────────────────────────────────────────────────────
  getUpstoxLoginUrl: () => req('/api/upstox/login'),
  getUpstoxStatus:   () => req('/api/upstox/status'),
  logoutUpstox:      () => req('/api/upstox/logout', { method: 'POST' }),

  // ── Market data (Upstox) ──────────────────────────────────────────────────
  getPrice:         (symbol: string) => req(`/api/market/price/${symbol}`),
  getOptions:       (symbol: string, expiry?: string) =>
    req(`/api/market/options/${symbol}${expiry ? `?expiry=${expiry}` : ''}`),
  getExpiries:      (symbol: string) => req(`/api/market/expiries/${symbol}`),
  loadInstruments:  (symbol: string) =>
    req(`/api/market/load-instruments/${symbol}`, { method: 'POST' }),
  getIndicators:    (symbol: string, period = '5d', interval = '5m') =>
    req(`/api/market/indicators/${symbol}?period=${period}&interval=${interval}`),
  getCandles:       (symbol: string, period = '5d', interval = '5m') =>
    req(`/api/market/candles/${symbol}?period=${period}&interval=${interval}`),
  getMarketStatus:  (symbol = 'NIFTY') => req(`/api/market/status?symbol=${symbol}`),
  getWsStatus:      () => req('/api/market/ws-status'),
  getLivePremiums:  () => req('/api/market/live-premiums'),

  // ── Trades ────────────────────────────────────────────────────────────────
  getOpenTrades:    () => req('/api/trades/open'),
  getTradeHistory:  (limit = 30) => req(`/api/trades/history?limit=${limit}`),
  getStats:         () => req('/api/trades/stats'),
  getEquityCurve:   () => req('/api/trades/equity-curve'),
  getExecutionAudit:(tradeId?: number) =>
    req(`/api/trades/execution-audit${tradeId ? `?trade_id=${tradeId}` : ''}`),
  getDailySummary:  () => req('/api/trades/daily-summary'),

  // ── BTST ──────────────────────────────────────────────────────────────────
  getBTSTOpen:    () => req('/api/btst/open'),
  getBTSTHistory: (limit = 20) => req(`/api/btst/history?limit=${limit}`),
  getBTSTSignal:  (symbol: string) => req(`/api/btst/signal/${symbol}`),

  // ── Intelligence ──────────────────────────────────────────────────────────
  getMarketIntel:         () => req('/api/intelligence/market'),
  getStrategyPerformance: () => req('/api/intelligence/strategy-performance'),
  addBlockedDate:         (date: string, reason: string) =>
    req('/api/intelligence/blocked-date', { method: 'POST', body: JSON.stringify({ date, reason }) }),
  removeBlockedDate:      (date: string) =>
    req(`/api/intelligence/blocked-date/${date}`, { method: 'DELETE' }),

  // ── Signal ────────────────────────────────────────────────────────────────
  getSignal: (symbol: string) => req(`/api/signal/${symbol}`),

  // ── Config ────────────────────────────────────────────────────────────────
  getConfig:    () => req('/api/config'),
  updateConfig: (data: object) =>
    req('/api/bot/config', { method: 'POST', body: JSON.stringify(data) }),

  // ── Notifications ─────────────────────────────────────────────────────────
  getNotifications:      (limit = 20, unreadOnly = false) =>
    req(`/api/notifications?limit=${limit}&unread_only=${unreadOnly}`),
  markNotificationsRead: () => req('/api/notifications/read', { method: 'POST' }),

  // ── Health ────────────────────────────────────────────────────────────────
  health: () => req('/health'),

  // ── Debug ──────────────────────────────────────────────────────────────────
  debugUpstox: (endpoint: string, symbol = 'NIFTY') =>
    req(`/api/debug/upstox/${endpoint}?symbol=${symbol}`),
  getDebugLogs: () => req('/api/debug/logs'),

  // ── AI Advisor ─────────────────────────────────────────────────────────────
  getAIStatus:   () => req('/api/ai/status'),
  getAIHistory:  (limit = 20) => req(`/api/ai/history?limit=${limit}`),
  getAIAnalysis: (symbol = 'NIFTY') => req(`/api/ai/analysis?symbol=${symbol}`),
  toggleAI:      () => req('/api/ai/toggle', { method: 'POST' }),
  updateAIConfig:(data: object) =>
    req('/api/ai/config', { method: 'POST', body: JSON.stringify(data) }),
  getTradingDay: () => req('/api/market/trading-day'),

  // ── Signal Decision Log ────────────────────────────────────────────────────
  getSignalLog:  (limit = 50) => req(`/api/signals/log?limit=${limit}`),
};
