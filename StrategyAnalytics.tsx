const BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

async function req(path: string, options?: RequestInit) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) throw new Error(`API ${path} → ${res.status}`);
  return res.json();
}

export const api = {
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

  getPrice:        (symbol: string) => req(`/api/market/price/${symbol}`),
  getOptions:      (symbol: string) => req(`/api/market/options/${symbol}`),
  getIndicators:   (symbol: string, period = '5d', interval = '5m') =>
    req(`/api/market/indicators/${symbol}?period=${period}&interval=${interval}`),
  getCandles:      (symbol: string, period = '5d', interval = '5m') =>
    req(`/api/market/candles/${symbol}?period=${period}&interval=${interval}`),
  getMarketStatus: (symbol = 'NIFTY') => req(`/api/market/status?symbol=${symbol}`),

  getOpenTrades:    () => req('/api/trades/open'),
  getTradeHistory:  (limit = 30) => req(`/api/trades/history?limit=${limit}`),
  getStats:         () => req('/api/trades/stats'),
  getEquityCurve:   () => req('/api/trades/equity-curve'),
  getExecutionAudit:(tradeId?: number) =>
    req(`/api/trades/execution-audit${tradeId ? `?trade_id=${tradeId}` : ''}`),

  getBTSTOpen:    () => req('/api/btst/open'),
  getBTSTHistory: (limit = 20) => req(`/api/btst/history?limit=${limit}`),
  getBTSTSignal:  (symbol: string) => req(`/api/btst/signal/${symbol}`),

  getMarketIntel:         () => req('/api/intelligence/market'),
  getStrategyPerformance: () => req('/api/intelligence/strategy-performance'),
  addBlockedDate:         (date: string, reason: string) =>
    req('/api/intelligence/blocked-date', { method: 'POST', body: JSON.stringify({ date, reason }) }),
  removeBlockedDate:      (date: string) =>
    req(`/api/intelligence/blocked-date/${date}`, { method: 'DELETE' }),

  getSignal:  (symbol: string) => req(`/api/signal/${symbol}`),
  getConfig:  () => req('/api/config'),
  updateConfig:(data: object) => req('/api/config', { method: 'PUT', body: JSON.stringify(data) }),

  getNotifications:      (limit = 20, unreadOnly = false) =>
    req(`/api/notifications?limit=${limit}&unread_only=${unreadOnly}`),
  markNotificationsRead: () => req('/api/notifications/read', { method: 'POST' }),
  health:                () => req('/health'),
};
