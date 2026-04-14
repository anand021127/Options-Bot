'use client';
import { useEffect, useState } from 'react';
import {
  TrendingUp, TrendingDown, Clock, Zap,
  Activity, Target, Shield, Info,
} from 'lucide-react';

// ── Types matching backend premium_tick broadcast ─────────────────────────────
export interface TradeTick {
  id:               number;
  symbol:           string;
  option_type:      'CE' | 'PE';
  strike:           number;
  expiry:           string;           // actual expiry from Upstox API e.g. "2024-01-25"
  entry_spot:       number;           // Nifty/BankNifty spot at entry
  entry_premium:    number;           // option LTP at entry (real from Upstox)
  current_premium:  number;           // live LTP from Upstox WS/REST
  current_spot:     number;           // current Nifty/BankNifty spot
  running_pnl:      number;           // (current - entry) × qty
  pnl_pct:          number;           // % change on premium
  sl_price:         number;
  target_price:     number;
  partial_target:   number;
  entry_time:       string;
  quantity:         number;
  lots:             number;
  lot_size:         number;           // from Upstox instruments API — never assumed
  instrument_key?:  string;           // Upstox instrument key
}

interface Props {
  ticks:       TradeTick[];
  currentSpot: number;
}

// ── Helper: Format IST time ────────────────────────────────────────────────────
function fmtTime(iso: string): string {
  if (!iso) return '--';
  try {
    return new Date(iso).toLocaleTimeString('en-IN', {
      hour: '2-digit', minute: '2-digit', second: '2-digit',
      timeZone: 'Asia/Kolkata',
    });
  } catch { return '--'; }
}

// ── Helper: Format expiry date nicely ─────────────────────────────────────────
function fmtExpiry(expiry: string): string {
  if (!expiry) return '--';
  try {
    const d = new Date(expiry);
    return d.toLocaleDateString('en-IN', {
      day: '2-digit', month: 'short', year: '2-digit',
      timeZone: 'Asia/Kolkata',
    });
  } catch { return expiry; }
}

// ── Range Progress Bar ─────────────────────────────────────────────────────────
function PremiumBar({ entry, current, sl, target, partial }: {
  entry: number; current: number; sl: number; target: number; partial: number;
}) {
  const range    = target - sl;
  if (range <= 0) return null;

  const clamp    = (v: number) => Math.max(0, Math.min(100, ((v - sl) / range) * 100));
  const curPos   = clamp(current);
  const entryPos = clamp(entry);
  const partPos  = clamp(partial);
  const isProfit = current >= entry;

  return (
    <div className="mt-2.5 mb-1">
      {/* Bar */}
      <div className="relative h-2.5 bg-brand-border rounded-full overflow-visible">
        {/* Filled region */}
        <div
          className={`absolute left-0 top-0 h-full rounded-full transition-all duration-700 ${
            isProfit ? 'bg-brand-green/70' : 'bg-brand-red/70'
          }`}
          style={{ width: `${curPos}%` }}
        />

        {/* Partial target marker */}
        <div className="absolute top-[-3px] h-[18px] w-0.5 bg-brand-yellow opacity-80"
          style={{ left: `${partPos}%` }} title={`T1 ₹${partial}`} />

        {/* Entry marker */}
        <div className="absolute top-[-4px] h-[20px] w-0.5 bg-brand-accent"
          style={{ left: `${entryPos}%` }} title={`Entry ₹${entry}`} />

        {/* Live cursor */}
        <div
          className={`absolute top-[-3px] w-3 h-3 rounded-full border-2 border-brand-bg transition-all duration-700 ${
            isProfit ? 'bg-brand-green' : 'bg-brand-red'
          }`}
          style={{ left: `calc(${curPos}% - 6px)` }}
        />
      </div>

      {/* Labels */}
      <div className="flex justify-between text-xs font-mono mt-1.5 text-brand-muted">
        <span className="text-brand-red">SL ₹{sl}</span>
        <span className="text-brand-yellow">T1 ₹{partial.toFixed(0)}</span>
        <span className="text-brand-green">T2 ₹{target}</span>
      </div>
    </div>
  );
}

// ── Individual Trade Card ──────────────────────────────────────────────────────
function TradeCard({ tick }: { tick: TradeTick }) {
  const [prevPremium, setPrevPremium] = useState(tick.current_premium);
  const [flash, setFlash]             = useState<'up' | 'down' | null>(null);

  useEffect(() => {
    if (tick.current_premium !== prevPremium) {
      setFlash(tick.current_premium > prevPremium ? 'up' : 'down');
      setPrevPremium(tick.current_premium);
      const t = setTimeout(() => setFlash(null), 600);
      return () => clearTimeout(t);
    }
  }, [tick.current_premium]);

  const isCE     = tick.option_type === 'CE';
  const isProfit = tick.running_pnl >= 0;
  const pnlAbs   = Math.abs(tick.running_pnl);
  const pnlPctAbs = Math.abs(tick.pnl_pct);
  const premiumΔ = tick.current_premium - tick.entry_premium;

  return (
    <div className={`rounded-2xl p-4 border transition-all ${
      isProfit
        ? 'bg-brand-card border-brand-green/25'
        : 'bg-brand-card border-brand-red/25'
    }`}>

      {/* ── Header ───────────────────────────────────────────────────────── */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          {/* Option type badge */}
          <span className={`px-2.5 py-1 rounded-lg text-xs font-mono font-bold ${
            isCE ? 'bg-brand-green/15 text-brand-green' : 'bg-brand-red/15 text-brand-red'
          }`}>{tick.option_type}</span>

          <div>
            {/* Instrument title: SYMBOL STRIKE */}
            <p className="font-mono font-bold text-base leading-tight">
              {tick.symbol} {tick.strike.toLocaleString('en-IN')}
            </p>
            {/* Expiry from API — displayed exactly as received */}
            <p className="text-brand-muted text-xs font-mono">
              Exp: {fmtExpiry(tick.expiry)}
              <span className="ml-2 text-brand-border">|</span>
              <span className="ml-2">{tick.lots}L × {tick.lot_size} = {tick.quantity}</span>
            </p>
          </div>
        </div>

        {/* Live P&L badge */}
        <div className={`flex items-center gap-1.5 px-3 py-2 rounded-xl border ${
          isProfit
            ? 'bg-brand-green/10 border-brand-green/30'
            : 'bg-brand-red/10 border-brand-red/30'
        }`}>
          {isProfit
            ? <TrendingUp size={13} className="text-brand-green" />
            : <TrendingDown size={13} className="text-brand-red" />}
          <div className="text-right">
            <p className={`font-mono font-bold text-sm leading-tight ${
              isProfit ? 'text-brand-green' : 'text-brand-red'
            }`}>
              {isProfit ? '+' : '-'}₹{pnlAbs.toFixed(0)}
            </p>
            <p className={`text-xs font-mono leading-tight ${
              isProfit ? 'text-brand-green/70' : 'text-brand-red/70'
            }`}>
              {isProfit ? '+' : '-'}{pnlPctAbs.toFixed(1)}%
            </p>
          </div>
        </div>
      </div>

      {/* ── Price grid (2 × 2) ───────────────────────────────────────────── */}
      <div className="grid grid-cols-2 gap-2 mb-1">
        {/* Entry spot */}
        <div className="bg-brand-surface rounded-xl p-2.5">
          <p className="text-brand-muted text-xs font-mono mb-0.5">ENTRY SPOT</p>
          <p className="font-mono font-bold text-sm text-brand-text">
            ₹{tick.entry_spot ? tick.entry_spot.toLocaleString('en-IN', { maximumFractionDigits: 0 }) : '--'}
          </p>
          <p className="text-brand-muted text-xs font-mono">Nifty at entry</p>
        </div>

        {/* Entry premium */}
        <div className="bg-brand-surface rounded-xl p-2.5">
          <p className="text-brand-muted text-xs font-mono mb-0.5">ENTRY PREMIUM</p>
          <p className="font-mono font-bold text-sm text-brand-accent">
            ₹{tick.entry_premium}
          </p>
          <p className="text-brand-muted text-xs font-mono">Upstox LTP</p>
        </div>

        {/* Current spot */}
        <div className="bg-brand-surface rounded-xl p-2.5">
          <p className="text-brand-muted text-xs font-mono mb-0.5">CURRENT SPOT</p>
          <p className={`font-mono font-bold text-sm ${
            tick.current_spot >= tick.entry_spot ? 'text-brand-green' : 'text-brand-red'
          }`}>
            ₹{tick.current_spot ? tick.current_spot.toLocaleString('en-IN', { maximumFractionDigits: 0 }) : '--'}
          </p>
          <p className="text-brand-muted text-xs font-mono">
            {tick.current_spot && tick.entry_spot
              ? `${((tick.current_spot - tick.entry_spot) / tick.entry_spot * 100) >= 0 ? '+' : ''}${((tick.current_spot - tick.entry_spot) / tick.entry_spot * 100).toFixed(2)}%`
              : '--'}
          </p>
        </div>

        {/* Live premium */}
        <div className={`rounded-xl p-2.5 border transition-colors duration-300 ${
          flash === 'up'   ? 'bg-brand-green/20 border-brand-green/50' :
          flash === 'down' ? 'bg-brand-red/20 border-brand-red/50' :
          isProfit ? 'bg-brand-green/8 border-brand-green/20' : 'bg-brand-red/8 border-brand-red/20'
        }`}>
          <div className="flex items-center gap-1 mb-0.5">
            <div className="w-1.5 h-1.5 rounded-full bg-brand-green animate-pulse flex-shrink-0" />
            <p className="text-brand-muted text-xs font-mono">LIVE PREMIUM</p>
          </div>
          <p className={`font-mono font-bold text-sm ${
            isProfit ? 'text-brand-green' : 'text-brand-red'
          }`}>
            ₹{tick.current_premium}
          </p>
          <p className={`text-xs font-mono ${isProfit ? 'text-brand-green/70' : 'text-brand-red/70'}`}>
            {premiumΔ >= 0 ? '+' : ''}₹{premiumΔ.toFixed(1)}
          </p>
        </div>
      </div>

      {/* ── Range bar ────────────────────────────────────────────────────── */}
      <PremiumBar
        entry={tick.entry_premium}
        current={tick.current_premium}
        sl={tick.sl_price}
        target={tick.target_price}
        partial={tick.partial_target}
      />

      {/* ── Footer ───────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between mt-2 pt-2 border-t border-brand-border">
        <div className="flex items-center gap-1 text-brand-muted text-xs font-mono">
          <Clock size={10} />
          <span>{fmtTime(tick.entry_time)}</span>
        </div>
        <div className="flex items-center gap-2 text-xs font-mono text-brand-muted">
          <span className="text-brand-accent">
            lot_size={tick.lot_size}
          </span>
          <span className="text-brand-border">·</span>
          <span>{tick.quantity} qty</span>
        </div>
      </div>

      {/* Instrument key — truncated, for debugging */}
      {tick.instrument_key && (
        <p className="text-brand-border text-xs font-mono mt-1 truncate" title={tick.instrument_key}>
          {tick.instrument_key}
        </p>
      )}
    </div>
  );
}

// ── Empty state ────────────────────────────────────────────────────────────────
function EmptyState() {
  return (
    <div className="bg-brand-card card-glow rounded-2xl p-6">
      <div className="flex flex-col items-center gap-3 text-center">
        <div className="w-12 h-12 rounded-2xl bg-brand-surface flex items-center justify-center">
          <Activity size={20} className="text-brand-muted" />
        </div>
        <div>
          <p className="font-display font-bold text-sm text-brand-text">No Active Trades</p>
          <p className="text-brand-muted text-xs font-mono mt-1 leading-relaxed">
            When a trade opens, live Upstox premiums<br/>will appear here in real-time
          </p>
        </div>
        <div className="flex items-center gap-1.5 text-xs font-mono text-brand-muted">
          <Zap size={10} className="text-brand-yellow" />
          <span>Updates every 30s via WebSocket</span>
        </div>
      </div>
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────
export default function TradeTracker({ ticks, currentSpot }: Props) {
  if (!ticks || ticks.length === 0) {
    return <EmptyState />;
  }

  const totalPnl = ticks.reduce((s, t) => s + t.running_pnl, 0);
  const isPos    = totalPnl >= 0;

  return (
    <div className="space-y-3">

      {/* Summary header */}
      <div className="bg-brand-card card-glow rounded-2xl px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-brand-green animate-pulse" />
          <span className="font-display font-bold text-sm">Live Positions</span>
          <span className="bg-brand-green/20 text-brand-green text-xs font-mono px-2 py-0.5 rounded-full border border-brand-green/30">
            {ticks.length} open
          </span>
        </div>
        <div className="text-right">
          <p className={`font-mono font-bold text-base ${isPos ? 'text-brand-green' : 'text-brand-red'}`}>
            {isPos ? '+' : '-'}₹{Math.abs(totalPnl).toFixed(0)}
          </p>
          <p className="text-brand-muted text-xs font-mono">running P&L</p>
        </div>
      </div>

      {/* Trade cards */}
      {ticks.map(tick => (
        <TradeCard key={tick.id} tick={tick} />
      ))}

      {/* Data source note */}
      <div className="flex items-center justify-center gap-1.5 py-1">
        <Zap size={10} className="text-brand-yellow" />
        <p className="text-brand-muted text-xs font-mono">
          Premiums from Upstox API · lot_size from instruments API · expiry from API
        </p>
      </div>

    </div>
  );
}
