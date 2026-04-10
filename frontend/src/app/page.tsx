'use client';
import { useState, useEffect, useCallback } from 'react';
import { Bell } from 'lucide-react';
import { useWebSocket } from '@/hooks/useWebSocket';
import { api } from '@/utils/api';
import Header from '@/components/Header';
import PortfolioCard from '@/components/PortfolioCard';
import BotControls from '@/components/BotControls';
import SignalCard from '@/components/SignalCard';
import OpenTrades from '@/components/OpenTrades';
import BTSTPanel from '@/components/BTSTPanel';
import EquityCurve from '@/components/EquityCurve';
import TradeHistory from '@/components/TradeHistory';
import IndicatorsPanel from '@/components/IndicatorsPanel';
import MarketChart from '@/components/MarketChart';
import MarketStatusPanel from '@/components/MarketStatusPanel';
import StrategyAnalytics from '@/components/StrategyAnalytics';
import StatsBar from '@/components/StatsBar';
import NotificationsPanel from '@/components/NotificationsPanel';

type Tab = 'overview' | 'trades' | 'chart' | 'signals' | 'analytics';

export default function Dashboard() {
  const [botStatus, setBotStatus]         = useState<any>({
    is_running: false, mode: 'paper', symbol: 'NIFTY',
    capital: 100000, daily_pnl: 0, total_pnl: 0, open_trades: 0, btst_trades: 0,
    pnl_pct: 0, daily_trades: 0, max_daily_trades: 5, max_drawdown: 0,
    win_streak: 0, loss_streak: 0, consecutive_losses: 0,
    filters: {}, min_score: 5, risk_pct: 1.5, btst_enabled: false,
    cooldown_active: false, trading_halted_today: false, remaining_daily_risk: 3000,
  });
  const [price, setPrice]                 = useState<any>(null);
  const [signal, setSignal]               = useState<any>(null);
  const [openTrades, setOpenTrades]       = useState<any[]>([]);
  const [btst, setBtst]                   = useState<any[]>([]);
  const [equityCurve, setEquityCurve]     = useState<any[]>([]);
  const [stats, setStats]                 = useState<any>(null);
  const [indicators, setIndicators]       = useState<any>(null);
  const [alerts, setAlerts]               = useState<{ msg: string; type: string }[]>([]);
  const [activeTab, setActiveTab]         = useState<Tab>('overview');
  const [loading, setLoading]             = useState(true);
  const [showNotifs, setShowNotifs]       = useState(false);
  const [unreadCount, setUnreadCount]     = useState(0);

  const pushAlert = (msg: string, type = 'warn') => {
    setAlerts(a => [{ msg, type }, ...a].slice(0, 4));
    setTimeout(() => setAlerts(a => a.slice(0, -1)), 9000);
  };

  const { connected } = useWebSocket({
    bot_status:       (d) => setBotStatus((p: any) => ({ ...p, ...d })),
    portfolio_update: (d) => setBotStatus((p: any) => ({ ...p, ...d })),
    signal:           (d) => setSignal(d),
    trade_entered:    () => { fetchOpenTrades(); fetchStats(); },
    trade_closed:     (d) => {
      fetchOpenTrades(); fetchStats(); fetchEquity();
      pushAlert(`Trade closed | P&L ₹${d.pnl > 0 ? '+' : ''}${d.pnl?.toFixed(0)}`, d.pnl > 0 ? 'success' : 'warn');
    },
    partial_booked:   (d) => pushAlert(`📦 Partial ₹+${d.partial_pnl?.toFixed(0)} | SL→BE`, 'info'),
    btst_entered:     () => { fetchBTST(); pushAlert('🌙 BTST trade entered', 'info'); },
    btst_closed:      (d) => { fetchBTST(); fetchStats(); pushAlert(`🌅 BTST closed ₹${d.pnl > 0 ? '+' : ''}${d.pnl?.toFixed(0)}`, d.pnl > 0 ? 'success' : 'warn'); },
    emergency_stop:   (d) => { pushAlert('🚨 ' + d.message, 'error'); fetchOpenTrades(); fetchBTST(); },
    cooldown:         (d) => pushAlert(`⏸ Cooldown ${d.remaining_minutes}m`, 'warn'),
    daily_reset:      ()  => { fetchStats(); pushAlert('📅 New day — stats reset', 'info'); },
    alert:            (d) => { pushAlert(d.message, d.type?.toLowerCase() || 'warn'); setUnreadCount(c => c + 1); },
    config_updated:   ()  => fetchBotStatus(),
    pong:             () => {},
  });

  const fetchBotStatus  = async () => { try { setBotStatus(await api.getBotStatus()); } catch {} };
  const fetchOpenTrades = async () => { try { setOpenTrades(await api.getOpenTrades()); } catch {} };
  const fetchBTST       = async () => { try { setBtst(await api.getBTSTOpen()); } catch {} };
  const fetchStats      = async () => { try { setStats(await api.getStats()); } catch {} };
  const fetchEquity     = async () => { try { setEquityCurve(await api.getEquityCurve()); } catch {} };
  const fetchIndicators = async () => {
    try { setIndicators(await api.getIndicators(botStatus.symbol || 'NIFTY')); } catch {}
  };

  const fetchAll = useCallback(async () => {
    try {
      const [s, p, ot, btstt, eq, st, notifs] = await Promise.allSettled([
        api.getBotStatus(), api.getPrice('NIFTY'), api.getOpenTrades(),
        api.getBTSTOpen(), api.getEquityCurve(), api.getStats(),
        api.getNotifications(5, true),
      ]);
      if (s.status === 'fulfilled')      setBotStatus(s.value);
      if (p.status === 'fulfilled')      setPrice(p.value);
      if (ot.status === 'fulfilled')     setOpenTrades(ot.value);
      if (btstt.status === 'fulfilled')  setBtst(btstt.value);
      if (eq.status === 'fulfilled')     setEquityCurve(eq.value);
      if (st.status === 'fulfilled')     setStats(st.value);
      if (notifs.status === 'fulfilled') setUnreadCount((notifs.value as any[]).length);
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  useEffect(() => {
    const iv = setInterval(async () => {
      try { setPrice(await api.getPrice(botStatus.symbol || 'NIFTY')); } catch {}
    }, 60000);
    return () => clearInterval(iv);
  }, [botStatus.symbol]);

  const handleStart = async (sym: string, cap: number, m: string) => {
    await api.startBot(sym, cap, m); await fetchAll();
  };
  const handleStop = async () => { await api.stopBot(); await fetchAll(); };
  const handleEmergencyStop = async () => {
    if (!confirm('🚨 Close ALL intraday + BTST positions immediately?')) return;
    await api.emergencyStop(); await fetchAll();
    pushAlert('🚨 Emergency stop executed', 'error');
  };

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center bg-brand-bg">
      <div className="text-center">
        <div className="w-10 h-10 border-2 border-brand-accent border-t-transparent rounded-full animate-spin mx-auto mb-3" />
        <p className="text-brand-muted font-mono text-sm">Initializing v3...</p>
      </div>
    </div>
  );

  const TABS: { id: Tab; label: string }[] = [
    { id: 'overview',   label: 'Overview' },
    { id: 'trades',     label: 'Trades' },
    { id: 'chart',      label: 'Chart' },
    { id: 'signals',    label: 'Signals' },
    { id: 'analytics',  label: 'Analytics' },
  ];

  const alertColors: Record<string, string> = {
    error:   'bg-brand-red/10 border-brand-red/30 text-brand-red',
    success: 'bg-brand-green/10 border-brand-green/30 text-brand-green',
    info:    'bg-brand-accent/10 border-brand-accent/30 text-brand-accent',
    warn:    'bg-brand-yellow/10 border-brand-yellow/30 text-brand-yellow',
  };

  return (
    <div className="min-h-screen bg-brand-bg text-brand-text">
      <Header
        connected={connected} price={price}
        botRunning={botStatus.is_running}
        unreadCount={unreadCount}
        onBellClick={() => { setShowNotifs(true); setUnreadCount(0); }}
      />

      {alerts.length > 0 && (
        <div className="px-3 pt-2 space-y-1">
          {alerts.map((a, i) => (
            <div key={i} className={`text-xs px-3 py-2 rounded-lg font-mono border animate-slide-up ${alertColors[a.type] || alertColors.warn}`}>
              {a.msg}
            </div>
          ))}
        </div>
      )}

      <StatsBar stats={stats} />

      <div className="sticky top-0 z-20 bg-brand-bg/95 backdrop-blur border-b border-brand-border">
        <div className="flex overflow-x-auto">
          {TABS.map(t => (
            <button key={t.id} onClick={() => setActiveTab(t.id)}
              className={`flex-1 py-3 text-sm font-semibold transition-all whitespace-nowrap px-2 ${
                activeTab === t.id
                  ? 'text-brand-accent border-b-2 border-brand-accent bg-brand-accent/5'
                  : 'text-brand-muted hover:text-brand-text'
              }`}>{t.label}
            </button>
          ))}
        </div>
      </div>

      <main className="px-3 py-4 max-w-2xl mx-auto space-y-4 pb-8">

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
            <EquityCurve data={equityCurve} />
            {btst.length > 0 && <BTSTPanel btst={btst} />}
            {openTrades.length > 0 && <OpenTrades trades={openTrades} currentPrice={price?.price} />}
          </div>
        )}

        {activeTab === 'trades' && (
          <div className="space-y-4 animate-slide-up">
            {btst.length > 0 && <BTSTPanel btst={btst} />}
            <OpenTrades trades={openTrades} currentPrice={price?.price} />
            <TradeHistory />
          </div>
        )}

        {activeTab === 'chart' && (
          <div className="space-y-4 animate-slide-up">
            <MarketChart symbol={botStatus.symbol || 'NIFTY'} />
            <MarketStatusPanel symbol={botStatus.symbol || 'NIFTY'} indicators={indicators} />
            <IndicatorsPanel
              indicators={indicators}
              onRefresh={fetchIndicators}
              symbol={botStatus.symbol || 'NIFTY'}
            />
          </div>
        )}

        {activeTab === 'signals' && (
          <div className="space-y-4 animate-slide-up">
            <MarketStatusPanel symbol={botStatus.symbol || 'NIFTY'} indicators={indicators} />
            <SignalCard
              signal={signal}
              symbol={botStatus.symbol || 'NIFTY'}
              onRefresh={async () => setSignal(await api.getSignal(botStatus.symbol || 'NIFTY'))}
            />
          </div>
        )}

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
