'use client';
import { TrendingUp, TrendingDown, Zap, Shield, Target, BarChart2, Moon, AlertOctagon } from 'lucide-react';

export default function PortfolioCard({ botStatus }: any) {
  const {
    capital = 100000, initial_capital = 100000,
    daily_pnl = 0, total_pnl = 0, pnl_pct = 0,
    open_trades = 0, btst_trades = 0,
    daily_trades = 0, max_daily_trades = 5,
    max_drawdown = 0, win_streak = 0, loss_streak = 0,
    consecutive_losses = 0, cooldown_active = false,
    trading_halted_today = false, remaining_daily_risk = 3000,
    mode = 'paper',
  } = botStatus || {};

  const dailyPos = daily_pnl >= 0;
  const totalPos = total_pnl >= 0;
  const pnlPos   = pnl_pct   >= 0;
  const fmt      = (n: number) =>
    `₹${Math.abs(n).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;

  const tradesUsedPct  = Math.min((daily_trades / Math.max(max_daily_trades, 1)) * 100, 100);
  const dailyCapAmount = initial_capital * (botStatus?.daily_loss_cap || 3) / 100;
  const riskUsedPct    = Math.max(0, 100 - (remaining_daily_risk / Math.max(dailyCapAmount, 1)) * 100);

  return (
    <div className="bg-brand-card card-glow rounded-2xl p-4 space-y-4">
      {/* Header row */}
      <div className="flex items-start justify-between">
        <div>
          <p className="text-brand-muted text-xs font-mono uppercase tracking-widest mb-1">
            Portfolio Value
          </p>
          <p className="font-mono font-bold text-2xl">
            {fmt(capital)}
          </p>
          <div className="flex items-center gap-2 mt-0.5">
            {pnlPos
              ? <TrendingUp size={12} className="text-brand-green" />
              : <TrendingDown size={12} className="text-brand-red" />}
            <span className={`font-mono text-sm ${pnlPos ? 'text-brand-green' : 'text-brand-red'}`}>
              {pnlPos ? '+' : ''}{pnl_pct.toFixed(2)}% all time
            </span>
          </div>
        </div>

        <div className="flex flex-col items-end gap-1.5">
          <span className={`px-2.5 py-1 rounded-lg text-xs font-mono font-bold border ${
            mode === 'live'
              ? 'bg-brand-red/10 border-brand-red/40 text-brand-red'
              : 'bg-brand-accent/10 border-brand-accent/40 text-brand-accent'
          }`}>
            {mode.toUpperCase()} v3
          </span>

          {trading_halted_today && (
            <div className="flex items-center gap-1 bg-brand-red/10 border border-brand-red/30 px-2 py-0.5 rounded-lg">
              <AlertOctagon size={10} className="text-brand-red" />
              <span className="text-brand-red text-xs font-mono font-bold">DAY STOP</span>
            </div>
          )}
          {cooldown_active && !trading_halted_today && (
            <span className="text-brand-yellow text-xs font-mono bg-brand-yellow/10 px-2 py-0.5 rounded border border-brand-yellow/30">
              ⏸ COOLDOWN
            </span>
          )}
        </div>
      </div>

      {/* P&L grid */}
      <div className="grid grid-cols-3 gap-2">
        <div className="bg-brand-surface rounded-xl p-3">
          <div className="flex items-center gap-1 mb-1">
            <Zap size={10} className="text-brand-muted" />
            <span className="text-brand-muted text-xs">Today</span>
          </div>
          <p className={`font-mono font-bold text-sm ${dailyPos ? 'text-brand-green' : 'text-brand-red'}`}>
            {dailyPos ? '+' : '-'}{fmt(daily_pnl)}
          </p>
        </div>

        <div className="bg-brand-surface rounded-xl p-3">
          <div className="flex items-center gap-1 mb-1">
            <BarChart2 size={10} className="text-brand-muted" />
            <span className="text-brand-muted text-xs">Total P&L</span>
          </div>
          <p className={`font-mono font-bold text-sm ${totalPos ? 'text-brand-green' : 'text-brand-red'}`}>
            {totalPos ? '+' : '-'}{fmt(total_pnl)}
          </p>
        </div>

        <div className="bg-brand-surface rounded-xl p-3">
          <div className="flex items-center gap-1 mb-1">
            <Shield size={10} className="text-brand-muted" />
            <span className="text-brand-muted text-xs">Max DD</span>
          </div>
          <p className={`font-mono font-bold text-sm ${max_drawdown > 5 ? 'text-brand-red' : max_drawdown > 2 ? 'text-brand-yellow' : 'text-brand-green'}`}>
            -{max_drawdown.toFixed(1)}%
          </p>
        </div>
      </div>

      {/* Progress bars */}
      <div className="space-y-2.5">
        {/* Daily trades */}
        <div>
          <div className="flex justify-between text-xs font-mono mb-1">
            <span className="text-brand-muted">Trades today</span>
            <span className={daily_trades >= max_daily_trades ? 'text-brand-red font-bold' : 'text-brand-text'}>
              {daily_trades}/{max_daily_trades}
            </span>
          </div>
          <div className="h-1.5 bg-brand-border rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${
                tradesUsedPct >= 100 ? 'bg-brand-red'
                : tradesUsedPct >= 80 ? 'bg-brand-yellow'
                : 'bg-brand-green'
              }`}
              style={{ width: `${tradesUsedPct}%` }}
            />
          </div>
        </div>

        {/* Daily risk */}
        <div>
          <div className="flex justify-between text-xs font-mono mb-1">
            <span className="text-brand-muted">Daily risk remaining</span>
            <span className={`font-bold ${remaining_daily_risk < 1000 ? 'text-brand-red' : 'text-brand-green'}`}>
              {fmt(remaining_daily_risk)}
            </span>
          </div>
          <div className="h-1.5 bg-brand-border rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${riskUsedPct >= 80 ? 'bg-brand-red' : 'bg-brand-accent'}`}
              style={{ width: `${riskUsedPct}%` }}
            />
          </div>
        </div>
      </div>

      {/* Streak + positions row */}
      <div className="flex gap-2">
        <div className={`flex-1 text-center py-2 rounded-lg border text-xs font-mono font-bold ${
          win_streak > 0
            ? 'bg-brand-green/10 border-brand-green/30 text-brand-green'
            : 'bg-brand-surface border-brand-border text-brand-muted'
        }`}>
          🔥 {win_streak} Win{win_streak !== 1 ? 's' : ''}
        </div>

        <div className={`flex-1 text-center py-2 rounded-lg border text-xs font-mono font-bold ${
          consecutive_losses > 0
            ? 'bg-brand-red/10 border-brand-red/30 text-brand-red'
            : 'bg-brand-surface border-brand-border text-brand-muted'
        }`}>
          ❌ {consecutive_losses} Loss{consecutive_losses !== 1 ? 'es' : ''}
        </div>

        <div className="flex-1 text-center py-2 rounded-lg border border-brand-border bg-brand-surface text-xs font-mono">
          <span className="text-brand-accent font-bold">{open_trades}</span>
          <span className="text-brand-muted"> intra</span>
          {btst_trades > 0 && (
            <>
              <span className="text-brand-yellow font-bold"> +{btst_trades}</span>
              <span className="text-brand-muted"> 🌙</span>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
