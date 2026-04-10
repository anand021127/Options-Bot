'use client';
import { useEffect, useState } from 'react';
import { Globe, Calendar, AlertTriangle, TrendingUp, Activity } from 'lucide-react';
import { api } from '@/utils/api';

const REGIME_CFG: Record<string, { color: string; bg: string; icon: string }> = {
  TRENDING:   { color: 'text-brand-green',  bg: 'bg-brand-green/10 border-brand-green/25',  icon: '📈' },
  SIDEWAYS:   { color: 'text-brand-yellow', bg: 'bg-brand-yellow/10 border-brand-yellow/25', icon: '↔️' },
  VOLATILE:   { color: 'text-brand-red',    bg: 'bg-brand-red/10 border-brand-red/25',       icon: '⚡' },
  WEAK_TREND: { color: 'text-brand-muted',  bg: 'bg-brand-surface border-brand-border',      icon: '〰️' },
  UNKNOWN:    { color: 'text-brand-muted',  bg: 'bg-brand-surface border-brand-border',      icon: '❓' },
};

const IV_CFG: Record<string, { color: string; label: string }> = {
  LOW_IV:     { color: 'text-brand-green',  label: 'Low — Buy options' },
  NORMAL_IV:  { color: 'text-brand-text',   label: 'Normal' },
  HIGH_IV:    { color: 'text-brand-yellow', label: 'High — Caution' },
  EXTREME_IV: { color: 'text-brand-red',    label: 'Extreme — Avoid' },
};

export default function MarketStatusPanel({ symbol = 'NIFTY', indicators }: any) {
  const [marketStatus, setMarketStatus] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const refresh = async () => {
    setLoading(true);
    try {
      const data = await api.getMarketStatus(symbol);
      setMarketStatus(data);
    } catch (e) {
      console.error(e);
    } finally { setLoading(false); }
  };

  useEffect(() => { refresh(); }, [symbol]);

  const regime   = indicators?.regime || 'UNKNOWN';
  const ivData   = indicators?.iv_rank || {};
  const ivRegime = ivData.regime || 'NORMAL_IV';
  const adx      = indicators?.adx;

  const regimeCfg = REGIME_CFG[regime] || REGIME_CFG.UNKNOWN;
  const ivCfg     = IV_CFG[ivRegime] || IV_CFG.NORMAL_IV;

  const sentiment = marketStatus?.global_sentiment;
  const noTrade   = marketStatus?.no_trade_day;
  const eventDay  = marketStatus?.high_impact_event;
  const expiry    = marketStatus?.is_expiry_day;
  const dte       = marketStatus?.days_to_expiry;

  return (
    <div className="bg-brand-card card-glow rounded-2xl p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity size={14} className="text-brand-accent"/>
          <h2 className="font-display font-bold text-sm">Market Intelligence</h2>
        </div>
        <button onClick={refresh}
          className={`text-brand-muted hover:text-brand-accent text-xs font-mono transition-all ${loading ? 'animate-pulse' : ''}`}>
          {loading ? '...' : '↻ refresh'}
        </button>
      </div>

      {/* Alerts */}
      {(noTrade || eventDay || expiry) && (
        <div className="space-y-1.5">
          {noTrade && (
            <div className="flex items-center gap-2 bg-brand-yellow/10 border border-brand-yellow/30 rounded-lg px-3 py-2">
              <AlertTriangle size={12} className="text-brand-yellow flex-shrink-0"/>
              <p className="text-brand-yellow text-xs font-mono">No-trade day auto-detected</p>
            </div>
          )}
          {eventDay && (
            <div className="flex items-center gap-2 bg-brand-red/10 border border-brand-red/30 rounded-lg px-3 py-2">
              <Calendar size={12} className="text-brand-red flex-shrink-0"/>
              <p className="text-brand-red text-xs font-mono">High-impact event — trading blocked</p>
            </div>
          )}
          {expiry && (
            <div className="flex items-center gap-2 bg-brand-yellow/10 border border-brand-yellow/30 rounded-lg px-3 py-2">
              <AlertTriangle size={12} className="text-brand-yellow flex-shrink-0"/>
              <p className="text-brand-yellow text-xs font-mono">Expiry day (Thursday) — BTST disabled</p>
            </div>
          )}
        </div>
      )}

      {/* 2x2 status grid */}
      <div className="grid grid-cols-2 gap-2">
        {/* Market regime */}
        <div className={`rounded-xl p-3 border ${regimeCfg.bg}`}>
          <div className="flex items-center gap-1 mb-1">
            <span className="text-base">{regimeCfg.icon}</span>
            <span className="text-xs text-brand-muted font-mono">Regime</span>
          </div>
          <p className={`font-mono font-bold text-sm ${regimeCfg.color}`}>{regime}</p>
          {adx && <p className="text-brand-muted text-xs font-mono mt-0.5">ADX {adx.toFixed(0)}</p>}
        </div>

        {/* IV condition */}
        <div className="bg-brand-surface rounded-xl p-3 border border-brand-border">
          <div className="flex items-center gap-1 mb-1">
            <span className="text-base">💰</span>
            <span className="text-xs text-brand-muted font-mono">IV Condition</span>
          </div>
          <p className={`font-mono font-bold text-sm ${ivCfg.color}`}>
            {ivRegime.replace('_IV', '')}
          </p>
          {ivData.iv_rank != null && (
            <p className="text-brand-muted text-xs font-mono mt-0.5">IVR {ivData.iv_rank}</p>
          )}
        </div>

        {/* Global sentiment */}
        <div className="bg-brand-surface rounded-xl p-3 border border-brand-border">
          <div className="flex items-center gap-1 mb-1">
            <Globe size={11} className="text-brand-muted"/>
            <span className="text-xs text-brand-muted font-mono">S&P 500</span>
          </div>
          {sentiment ? (
            <>
              <p className={`font-mono font-bold text-sm ${
                sentiment.signal === 'RISK_ON' ? 'text-brand-green'
                : sentiment.signal === 'RISK_OFF' ? 'text-brand-red' : 'text-brand-muted'
              }`}>
                {sentiment.signal === 'RISK_ON' ? '🟢 Risk-On' : sentiment.signal === 'RISK_OFF' ? '🔴 Risk-Off' : '⚪ Neutral'}
              </p>
              <p className="text-brand-muted text-xs font-mono mt-0.5">
                {sentiment.change_pct > 0 ? '+' : ''}{sentiment.change_pct?.toFixed(1)}%
              </p>
            </>
          ) : (
            <p className="text-brand-muted text-xs font-mono">Loading...</p>
          )}
        </div>

        {/* Expiry countdown */}
        <div className="bg-brand-surface rounded-xl p-3 border border-brand-border">
          <div className="flex items-center gap-1 mb-1">
            <Calendar size={11} className="text-brand-muted"/>
            <span className="text-xs text-brand-muted font-mono">Expiry</span>
          </div>
          <p className={`font-mono font-bold text-sm ${dte <= 1 ? 'text-brand-red' : dte <= 2 ? 'text-brand-yellow' : 'text-brand-text'}`}>
            {dte != null ? `${dte}d away` : expiry ? 'Today!' : '--'}
          </p>
          <p className="text-brand-muted text-xs font-mono mt-0.5">Weekly Thu</p>
        </div>
      </div>

      {/* IV detail bar */}
      {ivData.iv_rank != null && (
        <div>
          <div className="flex justify-between text-xs font-mono mb-1">
            <span className="text-brand-muted">IV Rank (HV proxy)</span>
            <span className={ivCfg.color}>{ivData.iv_rank} — {ivCfg.label}</span>
          </div>
          <div className="h-1.5 bg-brand-border rounded-full overflow-hidden">
            <div className={`h-full rounded-full transition-all ${
              ivData.iv_rank < 30 ? 'bg-brand-green'
              : ivData.iv_rank < 60 ? 'bg-brand-yellow'
              : 'bg-brand-red'
            }`} style={{ width: `${Math.min(ivData.iv_rank, 100)}%` }}/>
          </div>
          <div className="flex justify-between text-xs text-brand-muted font-mono mt-0.5">
            <span>0 (cheapest)</span><span>100 (expensive)</span>
          </div>
        </div>
      )}
    </div>
  );
}
