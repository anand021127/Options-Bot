'use client';
import { useState, useEffect } from 'react';
import { Shield, TrendingDown, Activity, AlertTriangle, BarChart2 } from 'lucide-react';

interface Props {
  botStatus: any;
  stats: any;
}

export default function RiskPanel({ botStatus, stats }: Props) {
  const capital       = botStatus?.capital || 100000;
  const initialCap    = botStatus?.initial_capital || 100000;
  const dailyPnl      = botStatus?.daily_pnl || 0;
  const totalPnl      = botStatus?.total_pnl || 0;
  const maxDrawdown   = botStatus?.max_drawdown || 0;
  const dailyLossCap  = botStatus?.daily_loss_cap || 3;
  const riskPct       = botStatus?.risk_pct || 1.5;
  const consLosses    = botStatus?.consecutive_losses || 0;
  const winStreak     = botStatus?.win_streak || 0;
  const lossStreak    = botStatus?.loss_streak || 0;
  const halted        = botStatus?.trading_halted_today || false;
  const cooldown      = botStatus?.cooldown_active || false;
  const remaining     = botStatus?.remaining_daily_risk || 0;

  // Computed
  const dailyBudget    = initialCap * dailyLossCap / 100;
  const dailyUsedPct   = Math.min(Math.abs(Math.min(dailyPnl, 0)) / dailyBudget * 100, 100);
  const pnlPct         = (totalPnl / Math.max(initialCap, 1)) * 100;
  const riskPerTrade   = capital * riskPct / 100;

  // Stats
  const winRate  = stats?.win_rate || 0;
  const rrRatio  = stats?.rr_ratio || 0;
  const totalTrades = stats?.total_trades || 0;

  return (
    <div className="space-y-4 animate-slide-up">
      {/* Risk Status Header */}
      <div className="bg-brand-card card-glow rounded-2xl p-4">
        <div className="flex items-center gap-2 mb-3">
          <Shield size={16} className="text-brand-accent" />
          <h2 className="font-display font-bold text-sm">Risk Management</h2>
          {halted && (
            <span className="text-xs font-mono bg-brand-red/15 text-brand-red px-2 py-0.5 rounded-lg">
              HALTED
            </span>
          )}
          {cooldown && (
            <span className="text-xs font-mono bg-brand-yellow/15 text-brand-yellow px-2 py-0.5 rounded-lg">
              COOLDOWN
            </span>
          )}
        </div>

        {/* Daily Loss Budget Bar */}
        <div className="mb-4">
          <div className="flex items-center justify-between text-xs font-mono mb-1.5">
            <span className="text-brand-muted">Daily Loss Budget</span>
            <span className={dailyPnl < 0 ? 'text-brand-red font-bold' : 'text-brand-green font-bold'}>
              ₹{Math.abs(Math.min(dailyPnl, 0)).toFixed(0)} / ₹{dailyBudget.toFixed(0)}
            </span>
          </div>
          <div className="w-full h-3 bg-brand-surface rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${
                dailyUsedPct > 80 ? 'bg-brand-red' : dailyUsedPct > 50 ? 'bg-brand-yellow' : 'bg-brand-green'
              }`}
              style={{ width: `${dailyUsedPct}%` }}
            />
          </div>
          <div className="flex justify-between text-xs font-mono text-brand-muted mt-1">
            <span>0%</span>
            <span>{dailyUsedPct.toFixed(0)}% used</span>
            <span>100% → HALT</span>
          </div>
        </div>

        {/* Key Risk Metrics Grid */}
        <div className="grid grid-cols-3 gap-2">
          {[
            { label: 'Risk/Trade',  value: `₹${riskPerTrade.toFixed(0)}`, sub: `${riskPct}%` },
            { label: 'Max DD',      value: `${maxDrawdown.toFixed(1)}%`,
              color: maxDrawdown > 5 ? 'text-brand-red' : 'text-brand-green' },
            { label: 'Remaining',   value: `₹${remaining.toFixed(0)}`,
              color: remaining < dailyBudget * 0.3 ? 'text-brand-red' : 'text-brand-green' },
            { label: 'Consec Loss', value: `${consLosses}`,
              color: consLosses >= 2 ? 'text-brand-red' : 'text-brand-green' },
            { label: 'Win Streak',  value: `${winStreak}`, color: 'text-brand-green' },
            { label: 'Loss Streak', value: `${lossStreak}`,
              color: lossStreak >= 2 ? 'text-brand-red' : 'text-brand-muted' },
          ].map((m, i) => (
            <div key={i} className="bg-brand-surface rounded-xl p-2.5 text-center">
              <p className="text-brand-muted text-xs font-mono leading-none">{m.label}</p>
              <p className={`text-sm font-mono font-bold mt-1 ${m.color || 'text-brand-text'}`}>
                {m.value}
              </p>
              {m.sub && <p className="text-brand-muted text-xs font-mono">{m.sub}</p>}
            </div>
          ))}
        </div>
      </div>

      {/* Performance Metrics */}
      <div className="bg-brand-card card-glow rounded-2xl p-4">
        <div className="flex items-center gap-2 mb-3">
          <BarChart2 size={14} className="text-brand-accent" />
          <p className="font-display font-bold text-sm">Performance Overview</p>
        </div>
        <div className="grid grid-cols-2 gap-3">
          {[
            { label: 'Total P&L',    value: `₹${totalPnl.toFixed(0)}`,
              pct: `${pnlPct >= 0 ? '+' : ''}${pnlPct.toFixed(1)}%`,
              color: totalPnl >= 0 ? 'text-brand-green' : 'text-brand-red' },
            { label: 'Win Rate',     value: `${winRate.toFixed(1)}%`,
              pct: `${totalTrades} trades`,
              color: winRate >= 50 ? 'text-brand-green' : 'text-brand-red' },
            { label: 'R:R Ratio',    value: rrRatio.toFixed(2),
              pct: rrRatio >= 1.5 ? 'Good' : rrRatio >= 1 ? 'Fair' : 'Poor',
              color: rrRatio >= 1.5 ? 'text-brand-green' : 'text-brand-yellow' },
            { label: 'Capital',      value: `₹${capital.toFixed(0)}`,
              pct: `${((capital - initialCap) / initialCap * 100).toFixed(1)}%`,
              color: capital >= initialCap ? 'text-brand-green' : 'text-brand-red' },
          ].map((m, i) => (
            <div key={i} className="bg-brand-surface rounded-xl p-3">
              <p className="text-brand-muted text-xs font-mono">{m.label}</p>
              <p className={`text-lg font-mono font-bold ${m.color}`}>{m.value}</p>
              <p className={`text-xs font-mono ${m.color} opacity-70`}>{m.pct}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Risk Warnings */}
      {(halted || cooldown || consLosses >= 2 || maxDrawdown > 5) && (
        <div className="bg-brand-card card-glow rounded-2xl p-4 space-y-2">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle size={14} className="text-brand-yellow" />
            <p className="font-display font-bold text-sm text-brand-yellow">Active Warnings</p>
          </div>
          {halted && (
            <div className="bg-brand-red/10 border border-brand-red/30 rounded-xl px-3 py-2 text-xs font-mono text-brand-red">
              🛑 Trading halted — daily loss cap reached or manual halt
            </div>
          )}
          {cooldown && (
            <div className="bg-brand-yellow/10 border border-brand-yellow/30 rounded-xl px-3 py-2 text-xs font-mono text-brand-yellow">
              ⏸ Cooldown active — waiting after consecutive losses
            </div>
          )}
          {consLosses >= 2 && !halted && (
            <div className="bg-brand-yellow/10 border border-brand-yellow/30 rounded-xl px-3 py-2 text-xs font-mono text-brand-yellow">
              ⚠️ {consLosses} consecutive losses — position size reduced by 50%
            </div>
          )}
          {maxDrawdown > 5 && (
            <div className="bg-brand-red/10 border border-brand-red/30 rounded-xl px-3 py-2 text-xs font-mono text-brand-red">
              📉 Max drawdown {maxDrawdown.toFixed(1)}% — exceeds 5% threshold
            </div>
          )}
        </div>
      )}
    </div>
  );
}
