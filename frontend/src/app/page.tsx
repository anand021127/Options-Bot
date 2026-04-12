'use client';
import { useState, useEffect, useCallback } from 'react';
import { Moon, Activity } from 'lucide-react';
import { useWebSocket } from '@/hooks/useWebSocket';
import { api } from '@/utils/api';

// ── Components ──────────────────────────────────────────────────────────────
import Header          from '@/components/Header';
import PortfolioCard   from '@/components/PortfolioCard';
import BotControls     from '@/components/BotControls';
import SignalCard       from '@/components/SignalCard';
import OpenTrades      from '@/components/OpenTrades';
import BTSTPanel       from '@/components/BTSTPanel';
import EquityCurve     from '@/components/EquityCurve';
import TradeHistory    from '@/components/TradeHistory';
import IndicatorsPanel from '@/components/IndicatorsPanel';
import MarketChart     from '@/components/MarketChart';
import MarketStatusPanel    from '@/components/MarketStatusPanel';
import StrategyAnalytics    from '@/components/StrategyAnalytics';
import StatsBar        from '@/components/StatsBar';
import NotificationsPanel   from '@/components/NotificationsPanel';
import TradeTracker    from '@/components/TradeTracker';
import OptionsChain    from '@/components/OptionsChain';

// ── Tab definition ───────────────────────────────────────────────────────────
type Tab = 'overview' | 'live' | 'options' | 'chart' | 'signals' | 'btst' | 'analytics';

const TABS: { id: Tab; label: string; icon?: string }[] = [
  { id: 'overview',   label: 'Home' },
  { id: 'live',       label: 'Trades' },
  { id: 'options',    label: 'Chain' },
  { id: 'chart',      label: 'Chart' },
  { id: 'signals',    label: 'Signals' },
  { id: 'btst',       label: '🌙 BTST' },
  { id: 'analytics',  label: 'Stats' },
];

// ── Alert colors ─────────────────────────────────────────────────────────────
const ALERT_COLORS: Record<string, string> = {
  error:   'bg-brand-red/10 border-brand-red/30 text-brand-red',
  success: 'bg-brand-green/10 border-brand-green/30 text-brand-green',
  info:    'bg-brand-accent/10 border-brand-accent/30 text-brand-accent',
  warn:    'bg-brand-yellow/10 border-brand-yellow/30 text-brand-yellow',
};

// ── BTST Tab component ────────────────────────────────────────────────────────
function BTSTTab({
  botStatus, btstTrades, onToggle, onConfigChange,
}: {
  botStatus: any; btstTrades: any[]; onToggle: () => void; onConfigChange: () => void;
}) {
  const [history,  setHistory]  = useState<any[]>([]);
  const [signal,   setSignal]   = useState<any>(null);
  const [loading,  setLoading]  = useState(false);
  const btstEnabled = botStatus?.btst_enabled;

  useEffect(() => {
    api.getBTSTHistory(10).then(setHistory).catch(() => {});
  }, []);

  const previewSignal = async () => {
    setLoading(true);
    try { setSignal(await api.getBTSTSignal(botStatus?.symbol || 'NIFTY')); }
    catch (e: any) { setSignal({ error: e.message }); }
    setLoading(false);
  };

  return (
    <div className="space-y-4 animate-slide-up">
      {/* BTST Master Toggle Card */}
      <div className="bg-brand-card card-glow rounded-2xl p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Moon size={16} className="text-brand-yellow" />
            <div>
              <p className="font-display font-bold text-sm">BTST Module</p>
              <p className="text-brand-muted text-xs font-mono">Buy Today Sell Tomorrow</p>
            </div>
          </div>
          {/* Large visible toggle */}
          <button
            onClick={onToggle}
            className={`relative w-16 h-8 rounded-full transition-all duration-300 focus:outline-none border-2 ${
              botStatus?.btst_enabled
                ? 'bg-brand-yellow border-brand-yellow'
                : 'bg-brand-border border-brand-border'
            }`}
            aria-label="Toggle BTST"
          >
            <div className={`absolute top-0.5 w-6 h-6 rounded-full bg-white shadow-md transition-all duration-300 ${
              botStatus?.btst_enabled ? 'right-0.5' : 'left-0.5'
            }`} />
          </button>
        </div>

        <div className={`text-xs font-mono px-3 py-1.5 rounded-lg inline-block ${
          btstEnabled
            ? 'bg-brand-yellow/15 text-brand-yellow border border-brand-yellow/30'
            : 'bg-brand-border/30 text-brand-muted border border-brand-border'
        }`}>
          {btstEnabled ? '✅ BTST ON — monitoring 14:45–15:10 IST' : '⭕ BTST OFF — tap toggle to enable'}
        </div>

        {/* Rules card */}
        <div className="mt-3 grid grid-cols-2 gap-2 text-xs font-mono text-brand-muted">
          <div className="bg-brand-surface rounded-xl p-2.5 space-y-1">
            <p className="text-brand-text font-semibold text-xs">Entry (14:45–15:10)</p>
            <p>• ADX ≥ 25 (strong trend)</p>
            <p>• Confirmed 15min breakout</p>
            <p>• Volume above average</p>
            <p>• RSI 25–72 range</p>
            <p>• IVR &lt; 60</p>
            <p>• Skips expiry days</p>
            <p>• Max 1 trade/day</p>
          </div>
          <div className="bg-brand-surface rounded-xl p-2.5 space-y-1">
            <p className="text-brand-text font-semibold text-xs">Exit (next morning)</p>
            <p>• 09:20 IST primary exit</p>
            <p>• +40% gap profit → early</p>
            <p>• SL hit → early exit</p>
            <p className="mt-2 text-brand-text font-semibold">Risk</p>
            <p>• 1% of capital max</p>
            <p>• lot_size from Upstox API</p>
            <p>• expiry from Upstox API</p>
          </div>
        </div>
      </div>

      {/* Active BTST positions */}
      {btstTrades.length > 0 && <BTSTPanel btst={btstTrades} />}

      {btstTrades.length === 0 && btstEnabled && (
        <div className="bg-brand-card card-glow rounded-2xl p-4 text-center">
          <Moon size={24} className="text-brand-yellow mx-auto mb-2 opacity-50" />
          <p className="text-brand-muted text-xs font-mono">
            No active BTST positions.{' '}
            {new Date().getHours() >= 14 && new Date().getHours() < 15
              ? 'Scanning for entry signal 14:45–15:10...'
              : 'Entry window: 14:45–15:10 IST today.'}
          </p>
        </div>
      )}

      {/* Signal preview */}
      <div className="bg-brand-card card-glow rounded-2xl p-4 space-y-3">
        <div className="flex items-center justify-between">
          <p className="font-display font-bold text-sm">BTST Signal Preview</p>
          <button onClick={previewSignal} disabled={loading}
            className="text-xs font-mono text-brand-accent hover:underline disabled:opacity-50">
            {loading ? 'Checking...' : 'Check Now'}
          </button>
        </div>
        {signal && (
          <div className={`rounded-xl p-3 border text-xs font-mono ${
            signal.error ? 'bg-brand-red/10 border-brand-red/30 text-brand-red' :
            signal.signal_type?.includes('BTST') && !signal.blocked_by
              ? 'bg-brand-green/10 border-brand-green/30'
              : 'bg-brand-surface border-brand-border'
          }`}>
            {signal.error ? (
              <p className="text-brand-red">Error: {signal.error}</p>
            ) : (
              <>
                <p className="font-bold text-brand-text mb-1">{signal.signal_type}</p>
                {signal.blocked_by && (
                  <p className="text-brand-yellow">Blocked: {signal.blocked_by}</p>
                )}
                {signal.option && (
                  <div className="mt-2 grid grid-cols-2 gap-1 text-brand-muted">
                    <span>Strike: <span className="text-brand-text">₹{signal.option.strike}</span></span>
                    <span>Type: <span className="text-brand-text">{signal.option.option_type}</span></span>
                    <span>LTP: <span className="text-brand-text">₹{signal.option.ltp}</span></span>
                    <span>Lot: <span className="text-brand-text">{signal.option.lot_size} (API)</span></span>
                    <span>Expiry: <span className="text-brand-text">{signal.option.expiry}</span></span>
                    <span>Score: <span className="text-brand-text">{signal.score}</span></span>
                  </div>
                )}
                {signal.reasons?.length > 0 && (
                  <div className="mt-2 space-y-0.5 text-brand-muted">
                    {signal.reasons.slice(0, 4).map((r: string, i: number) => (
                      <p key={i}>{r}</p>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        )}
        {!signal && (
          <p className="text-brand-muted text-xs font-mono">
            Tap "Check Now" to preview what the BTST scanner sees right now.
          </p>
        )}
      </div>

      {/* BTST history */}
      {history.length > 0 && (
        <div className="bg-brand-card card-glow rounded-2xl p-4 space-y-3">
          <p className="font-display font-bold text-sm">Recent BTST Trades</p>
          <div className="space-y-2">
            {history.slice(0, 5).map((t: any) => {
              const isPos = t.pnl >= 0;
              return (
                <div key={t.id} className="bg-brand-surface rounded-xl p-3 border border-brand-border">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className={`text-xs font-mono font-bold px-2 py-0.5 rounded ${
                        t.option_type === 'CE'
                          ? 'bg-brand-green/15 text-brand-green'
                          : 'bg-brand-red/15 text-brand-red'
                      }`}>{t.option_type}</span>
                      <span className="font-mono text-sm font-bold">₹{t.strike}</span>
                    </div>
                    <div className="text-right">
                      <p className={`font-mono font-bold text-sm ${isPos ? 'text-brand-green' : 'text-brand-red'}`}>
                        {isPos ? '+' : ''}₹{t.pnl?.toFixed(0) ?? '--'}
                      </p>
                      <p className="text-brand-muted text-xs font-mono">{t.exit_reason || t.status}</p>
                    </div>
                  </div>
                  <div className="mt-1 flex justify-between text-xs font-mono text-brand-muted">
                    <span>Entry ₹{t.entry_price} → Exit ₹{t.exit_price || '--'}</span>
                    <span>{t.expiry}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main Dashboard ────────────────────────────────────────────────────────────
export default function Dashboard() {
  // Bot state
  const [botStatus, setBotStatus] = useState<any>({
    is_running: false, mode: 'paper', symbol: 'NIFTY',
    capital: 100000, daily_pnl: 0, total_pnl: 0,
    open_trades: 0, btst_trades: 0, pnl_pct: 0,
    daily_trades: 0, max_daily_trades: 5, max_drawdown: 0,
    win_streak: 0, loss_streak: 0, consecutive_losses: 0,
    filters: {}, min_score: 5, risk_pct: 1.5,
    btst_enabled: false, cooldown_active: false,
    trading_halted_today: false, remaining_daily_risk: 3000,
  });

  // Market data
  const [price,       setPrice]       = useState<any>(null);
  const [signal,      setSignal]      = useState<any>(null);
  const [indicators,  setIndicators]  = useState<any>(null);
  const [wsConnected, setWsConnected] = useState(false);

  // Trade data
  const [openTrades,  setOpenTrades]  = useState<any[]>([]);
  const [btst,        setBtst]        = useState<any[]>([]);
  const [equityCurve, setEquityCurve] = useState<any[]>([]);
  const [stats,       setStats]       = useState<any>(null);

  // Live premium ticks from premium_tick WS event
  const [premiumTicks, setPremiumTicks] = useState<any[]>([]);
  const [liveSpot,     setLiveSpot]     = useState<number>(0);

  // UI
  const [alerts,      setAlerts]      = useState<{ msg: string; type: string }[]>([]);
  const [activeTab,   setActiveTab]   = useState<Tab>('overview');
  const [loading,     setLoading]     = useState(true);
  const [showNotifs,  setShowNotifs]  = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);

  const pushAlert = (msg: string, type = 'warn') => {
    setAlerts(a => [{ msg, type }, ...a].slice(0, 4));
    setTimeout(() => setAlerts(a => a.slice(0, -1)), 9000);
  };

  // ── WebSocket handlers ──────────────────────────────────────────────────────
  const { connected } = useWebSocket({
    bot_status:       (d) => setBotStatus((p: any) => ({ ...p, ...d })),
    portfolio_update: (d) => setBotStatus((p: any) => ({ ...p, ...d })),
    signal:           (d) => setSignal(d),

    // Real-time option premiums from Upstox — powers TradeTracker
    premium_tick: (d) => {
      setPremiumTicks(d.ticks || []);
      if (d.spot) setLiveSpot(d.spot);
    },

    trade_entered: (d) => {
      fetchOpenTrades(); fetchStats();
      pushAlert(
        `📈 Trade opened | ${d.option_type} ₹${d.strike} | Premium ₹${d.entry_option_price || d.fill_price}`,
        'success'
      );
    },
    trade_closed: (d) => {
      fetchOpenTrades(); fetchStats(); fetchEquity();
      setPremiumTicks(prev => prev.filter(t => t.id !== d.id));
      pushAlert(
        `Trade closed | P&L ₹${d.pnl > 0 ? '+' : ''}${d.pnl?.toFixed(0)}`,
        d.pnl > 0 ? 'success' : 'warn'
      );
    },
    partial_booked: (d) => pushAlert(`📦 Partial +₹${d.partial_pnl?.toFixed(0)} | SL→BE`, 'info'),

    btst_entered: () => { fetchBTST(); pushAlert('🌙 BTST trade entered', 'info'); },
    btst_closed:  (d) => {
      fetchBTST(); fetchStats();
      pushAlert(`🌅 BTST closed ₹${d.pnl > 0 ? '+' : ''}${d.pnl?.toFixed(0)}`, d.pnl > 0 ? 'success' : 'warn');
    },

    emergency_stop: (d) => {
      pushAlert('🚨 ' + d.message, 'error');
      fetchOpenTrades(); fetchBTST();
      setPremiumTicks([]);
    },
    cooldown:       (d) => pushAlert(`⏸ Cooldown ${d.remaining_minutes}m`, 'warn'),
    daily_reset:    ()  => { fetchStats(); pushAlert('📅 New day — reset', 'info'); },
    alert:          (d) => { pushAlert(d.message, d.type?.toLowerCase() || 'warn'); setUnreadCount(c => c + 1); },
    config_updated: ()  => fetchBotStatus(),
    pong:           () => {},
  });

  // ── Fetchers ────────────────────────────────────────────────────────────────
  const fetchBotStatus  = async () => { try { setBotStatus(await api.getBotStatus()); } catch {} };
  const fetchOpenTrades = async () => { try { setOpenTrades(await api.getOpenTrades()); } catch {} };
  const fetchBTST       = async () => { try { setBtst(await api.getBTSTOpen()); } catch {} };
  const fetchStats      = async () => { try { setStats(await api.getStats()); } catch {} };
  const fetchEquity     = async () => { try { setEquityCurve(await api.getEquityCurve()); } catch {} };
  const fetchIndicators = async () => {
    try { setIndicators(await api.getIndicators(botStatus.symbol || 'NIFTY')); } catch {}
  };

  const checkWsStatus = useCallback(async () => {
    try { const d = await api.getWsStatus(); setWsConnected(d.connected || false); } catch {}
  }, []);

  const fetchAll = useCallback(async () => {
    try {
      const [s, p, ot, bt, eq, st, notifs] = await Promise.allSettled([
        api.getBotStatus(), api.getPrice('NIFTY'), api.getOpenTrades(),
        api.getBTSTOpen(), api.getEquityCurve(), api.getStats(),
        api.getNotifications(5, true),
      ]);
      if (s.status === 'fulfilled')     setBotStatus(s.value);
      if (p.status === 'fulfilled')     { setPrice(p.value); setLiveSpot(p.value?.price || 0); }
      if (ot.status === 'fulfilled')    setOpenTrades(ot.value);
      if (bt.status === 'fulfilled')    setBtst(bt.value);
      if (eq.status === 'fulfilled')    setEquityCurve(eq.value);
      if (st.status === 'fulfilled')    setStats(st.value);
      if (notifs.status === 'fulfilled') setUnreadCount((notifs.value as any[]).length);
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);
  useEffect(() => {
    checkWsStatus();
    const iv = setInterval(checkWsStatus, 30000);
    return () => clearInterval(iv);
  }, [checkWsStatus]);
  useEffect(() => {
    const iv = setInterval(async () => {
      try {
        const p = await api.getPrice(botStatus.symbol || 'NIFTY');
        setPrice(p);
        if (p?.price) setLiveSpot(p.price);
      } catch {}
    }, 60000);
    return () => clearInterval(iv);
  }, [botStatus.symbol]);

  // ── Bot actions ─────────────────────────────────────────────────────────────
  const handleStart = async (sym: string, cap: number, m: string) => {
    await api.startBot(sym, cap, m);
    await fetchAll();
  };
  const handleStop          = async () => { await api.stopBot();       await fetchAll(); };
  const handleEmergencyStop = async () => {
    if (!confirm('🚨 Close ALL positions immediately? This cannot be undone.')) return;
    await api.emergencyStop();
    await fetchAll();
    pushAlert('🚨 Emergency stop executed — all positions closed', 'error');
  };

  // BTST toggle — accessible from both BotControls and BTST tab
  const handleBTSTToggle = async () => {
    const newVal = !botStatus.btst_enabled;
    await api.updateBotConfig({ btst_enabled: newVal });
    fetchBotStatus();
    pushAlert(`🌙 BTST ${newVal ? 'enabled' : 'disabled'}`, 'info');
  };

  const symbol       = botStatus.symbol || 'NIFTY';
  const hasLiveTrades = premiumTicks.length > 0;

  // ── Loading ─────────────────────────────────────────────────────────────────
  if (loading) return (
    <div className="min-h-screen flex items-center justify-center bg-brand-bg">
      <div className="text-center">
        <div className="w-10 h-10 border-2 border-brand-accent border-t-transparent rounded-full animate-spin mx-auto mb-3" />
        <p className="text-brand-muted font-mono text-sm">Connecting to Upstox...</p>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-brand-bg text-brand-text">
      <Header
        connected={connected}
        price={price}
        botRunning={botStatus.is_running}
        unreadCount={unreadCount}
        wsDataConnected={wsConnected}
        onBellClick={() => { setShowNotifs(true); setUnreadCount(0); }}
      />

      {/* Alert toasts */}
      {alerts.length > 0 && (
        <div className="px-3 pt-2 space-y-1">
          {alerts.map((a, i) => (
            <div key={i} className={`text-xs px-3 py-2 rounded-lg font-mono border animate-slide-up ${ALERT_COLORS[a.type] || ALERT_COLORS.warn}`}>
              {a.msg}
            </div>
          ))}
        </div>
      )}

      <StatsBar stats={stats} />

      {/* ── Tab bar ── */}
      <div className="sticky top-0 z-20 bg-brand-bg/95 backdrop-blur border-b border-brand-border">
        <div className="flex overflow-x-auto scrollbar-none">
          {TABS.map(t => (
            <button key={t.id} onClick={() => setActiveTab(t.id)}
              className={`flex-1 py-2.5 text-xs font-semibold transition-all whitespace-nowrap px-1.5 min-w-0 ${
                activeTab === t.id
                  ? 'text-brand-accent border-b-2 border-brand-accent bg-brand-accent/5'
                  : 'text-brand-muted hover:text-brand-text'
              }`}>
              {t.label}
              {/* Dot indicators */}
              {t.id === 'live' && hasLiveTrades && (
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-brand-green ml-1 animate-pulse align-middle" />
              )}
              {t.id === 'btst' && btst.length > 0 && (
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-brand-yellow ml-1 align-middle" />
              )}
            </button>
          ))}
        </div>
      </div>

      {/* ── Tab content ── */}
      <main className="px-3 py-4 max-w-2xl mx-auto space-y-4 pb-10">

        {/* ── OVERVIEW ──────────────────────────────────────────────────── */}
        {activeTab === 'overview' && (
          <div className="space-y-4 animate-slide-up">
            <PortfolioCard botStatus={botStatus} />
            <BotControls
              botStatus={botStatus}
              onStart={handleStart}
              onStop={handleStop}
              onEmergencyStop={handleEmergencyStop}
              onConfigChange={fetchBotStatus}
            />
            {hasLiveTrades && (
              <TradeTracker ticks={premiumTicks} currentSpot={liveSpot} />
            )}
            <EquityCurve data={equityCurve} />
            {btst.length > 0 && <BTSTPanel btst={btst} />}
          </div>
        )}

        {/* ── LIVE TRADES ───────────────────────────────────────────────── */}
        {activeTab === 'live' && (
          <div className="space-y-4 animate-slide-up">
            <TradeTracker ticks={premiumTicks} currentSpot={liveSpot} />
            {btst.length > 0 && <BTSTPanel btst={btst} />}
            <OpenTrades trades={openTrades} currentPrice={price?.price} />
          </div>
        )}

        {/* ── OPTIONS CHAIN ─────────────────────────────────────────────── */}
        {activeTab === 'options' && (
          <div className="space-y-4 animate-slide-up">
            {/* Upstox data note */}
            <div className="bg-brand-surface rounded-xl px-3 py-2 flex items-center gap-2 border border-brand-border">
              <Activity size={12} className="text-brand-accent flex-shrink-0" />
              <p className="text-brand-muted text-xs font-mono">
                Live chain from Upstox API · Expiries &amp; lot sizes from instruments API · Auto-refresh 15s
              </p>
            </div>
            <OptionsChain symbol={symbol} spot={liveSpot || price?.price} />
          </div>
        )}

        {/* ── CHART ─────────────────────────────────────────────────────── */}
        {activeTab === 'chart' && (
          <div className="space-y-4 animate-slide-up">
            <MarketChart symbol={symbol} />
            <MarketStatusPanel symbol={symbol} indicators={indicators} />
            <IndicatorsPanel
              indicators={indicators}
              onRefresh={fetchIndicators}
              symbol={symbol}
            />
          </div>
        )}

        {/* ── SIGNALS ───────────────────────────────────────────────────── */}
        {activeTab === 'signals' && (
          <div className="space-y-4 animate-slide-up">
            <MarketStatusPanel symbol={symbol} indicators={indicators} />
            <SignalCard
              signal={signal}
              symbol={symbol}
              onRefresh={async () => {
                try { setSignal(await api.getSignal(symbol)); } catch {}
              }}
            />
          </div>
        )}

        {/* ── BTST ──────────────────────────────────────────────────────── */}
        {activeTab === 'btst' && (
          <BTSTTab
            botStatus={botStatus}
            btstTrades={btst}
            onToggle={handleBTSTToggle}
            onConfigChange={fetchBotStatus}
          />
        )}

        {/* ── ANALYTICS ─────────────────────────────────────────────────── */}
        {activeTab === 'analytics' && (
          <div className="space-y-4 animate-slide-up">
            <StrategyAnalytics />
            <EquityCurve data={equityCurve} />
            <TradeHistory />
          </div>
        )}

      </main>

      {showNotifs && <NotificationsPanel onClose={() => setShowNotifs(false)} />}
    </div>
  );
}
