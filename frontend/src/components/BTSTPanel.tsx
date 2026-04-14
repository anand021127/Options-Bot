'use client';
import { Moon, Clock } from 'lucide-react';

export default function BTSTPanel({ btst }: { btst: any[] }) {
  if (!btst?.length) return null;

  return (
    <div className="bg-brand-card card-glow rounded-2xl p-4 space-y-3">
      <div className="flex items-center gap-2">
        <Moon size={14} className="text-brand-yellow" />
        <h2 className="font-display font-bold text-sm text-brand-yellow">BTST Positions</h2>
        <span className="bg-brand-yellow/20 text-brand-yellow text-xs font-mono px-2 py-0.5 rounded-full">
          {btst.length} overnight
        </span>
      </div>
      <div className="space-y-2">
        {btst.map((t: any) => {
          const isCE = t.option_type === 'CE';
          const time = t.entry_time
            ? new Date(t.entry_time).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })
            : '--';
          return (
            <div key={t.id} className="bg-brand-surface rounded-xl p-3 border border-brand-yellow/20">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className={`opt-badge px-2 py-0.5 rounded text-xs font-mono font-bold ${
                    isCE ? 'bg-brand-green/15 text-brand-green' : 'bg-brand-red/15 text-brand-red'
                  }`}>{t.option_type}</span>
                  <span className="font-mono text-sm font-bold">₹{t.strike}</span>
                  <span className="text-brand-muted text-xs">{t.symbol}</span>
                </div>
                <div className="flex items-center gap-1 text-brand-muted text-xs font-mono">
                  <Clock size={10} />
                  {time}
                </div>
              </div>
              <div className="grid grid-cols-3 gap-2 text-xs font-mono">
                <div><p className="text-brand-muted">Entry</p><p className="font-semibold">₹{t.entry_price}</p></div>
                <div><p className="text-brand-muted">SL</p><p className="font-semibold text-brand-red">₹{t.sl_price}</p></div>
                <div><p className="text-brand-muted">Target</p><p className="font-semibold text-brand-green">₹{t.target_price}</p></div>
              </div>
              <div className="mt-2 pt-2 border-t border-brand-border text-xs font-mono text-brand-yellow">
                🌙 Exit: 09:20 tomorrow OR +40% gap
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
