'use client';
import { useState, useEffect } from 'react';
import { BarChart2, TrendingUp, TrendingDown } from 'lucide-react';
import { api } from '@/utils/api';

const STRATEGY_ICONS: Record<string, string> = {
  BREAKOUT: '🚀', PULLBACK: '📉', VWAP: '🔥', RETEST: '🎯', BTST: '🌙', UNKNOWN: '❓',
};

export default function StrategyAnalytics() {
  const [data, setData]     = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getStrategyPerformance().then(d => { setData(d); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="bg-brand-card card-glow rounded-2xl p-4">
      <div className="h-24 flex items-center justify-center">
        <div className="w-5 h-5 border-2 border-brand-accent border-t-transparent rounded-full animate-spin"/>
      </div>
    </div>
  );

  return (
    <div className="bg-brand-card card-glow rounded-2xl p-4 space-y-3">
      <div className="flex items-center gap-2">
        <BarChart2 size={14} className="text-brand-accent"/>
        <h2 className="font-display font-bold text-sm">Strategy Analytics</h2>
        <span className="text-brand-muted text-xs font-mono">(adaptive weights)</span>
      </div>

      {!data.length || data.every(s => s.trades === 0) ? (
        <p className="text-center text-brand-muted text-xs font-mono py-4">
          No trades yet — performance tracked per strategy
        </p>
      ) : (
        <div className="space-y-2">
          {data.map(s => {
            const wr      = s.win_rate ?? 0;
            const enabled = s.enabled !== 0;
            const weight  = s.weight_mult ?? 1.0;
            const wrColor = wr >= 60 ? 'text-brand-green' : wr >= 45 ? 'text-brand-yellow' : 'text-brand-red';

            return (
              <div key={s.strategy} className={`bg-brand-surface rounded-xl p-3 border transition-all ${
                enabled ? 'border-brand-border' : 'border-brand-red/30 opacity-60'
              }`}>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span>{STRATEGY_ICONS[s.strategy] || '❓'}</span>
                    <span className="font-mono font-bold text-sm text-brand-text">{s.strategy}</span>
                    {!enabled && (
                      <span className="text-xs font-mono text-brand-red bg-brand-red/10 px-1.5 rounded">AUTO-DISABLED</span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono text-brand-muted">w={weight.toFixed(1)}</span>
                    <span className={`font-mono font-bold text-sm ${wrColor}`}>{wr.toFixed(0)}%</span>
                  </div>
                </div>

                {/* Win rate bar */}
                <div className="h-1 bg-brand-border rounded-full overflow-hidden mb-2">
                  <div className={`h-full rounded-full ${wr >= 60 ? 'bg-brand-green' : wr >= 45 ? 'bg-brand-yellow' : 'bg-brand-red'}`}
                       style={{ width: `${wr}%` }}/>
                </div>

                <div className="grid grid-cols-4 gap-1 text-xs font-mono">
                  <div className="text-center">
                    <p className="text-brand-muted">Trades</p>
                    <p className="font-bold">{s.trades}</p>
                  </div>
                  <div className="text-center">
                    <p className="text-brand-muted">Wins</p>
                    <p className="font-bold text-brand-green">{s.wins}</p>
                  </div>
                  <div className="text-center">
                    <p className="text-brand-muted">Losses</p>
                    <p className="font-bold text-brand-red">{s.losses}</p>
                  </div>
                  <div className="text-center">
                    <p className="text-brand-muted">Avg P&L</p>
                    <p className={`font-bold ${s.avg_pnl >= 0 ? 'text-brand-green' : 'text-brand-red'}`}>
                      {s.avg_pnl >= 0 ? '+' : ''}₹{Math.abs(s.avg_pnl).toFixed(0)}
                    </p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <p className="text-brand-muted text-xs font-mono text-center">
        Weights auto-adjust after 10+ trades per strategy
      </p>
    </div>
  );
}
