'use client';
import { useState, useEffect } from 'react';
import { api } from '@/utils/api';
import { History } from 'lucide-react';

const STATUS_STYLE: Record<string,string> = {
  TARGET_HIT:     'text-brand-green',
  SL_HIT:         'text-brand-red',
  EMERGENCY_STOP: 'text-brand-yellow',
  OPEN:           'text-brand-accent',
};

export default function TradeHistory() {
  const [trades, setTrades] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getTradeHistory(30).then(d => { setTrades(d); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="bg-brand-card card-glow rounded-2xl p-4">
      <div className="h-32 flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-brand-accent border-t-transparent rounded-full animate-spin"/>
      </div>
    </div>
  );

  return (
    <div className="bg-brand-card card-glow rounded-2xl p-4 space-y-3">
      <div className="flex items-center gap-2">
        <History size={14} className="text-brand-accent"/>
        <h2 className="font-display font-bold text-sm">Trade History</h2>
        <span className="text-brand-muted text-xs font-mono">({trades.length} trades)</span>
      </div>

      {!trades.length ? (
        <div className="py-6 text-center text-brand-muted text-xs font-mono">No completed trades yet</div>
      ) : (
        <div className="space-y-1.5 max-h-96 overflow-y-auto pr-1">
          {trades.map((t: any) => {
            const pnlPos = (t.pnl ?? 0) >= 0;
            const isCE   = t.option_type === 'CE';
            const date   = t.entry_time ? new Date(t.entry_time).toLocaleDateString('en-IN',{month:'short',day:'numeric'}) : '--';
            return (
              <div key={t.id} className="flex items-center justify-between bg-brand-surface rounded-lg px-3 py-2 text-xs font-mono">
                <div className="flex items-center gap-2">
                  <span className={`px-1.5 py-0.5 rounded text-xs font-bold ${isCE?'text-brand-green':'text-brand-red'}`}>
                    {t.option_type}
                  </span>
                  <div>
                    <p className="text-brand-text font-semibold">₹{t.strike} <span className="text-brand-muted font-normal">{t.symbol}</span></p>
                    <p className="text-brand-muted">{date} · {t.quantity} qty</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className={`font-bold ${pnlPos?'text-brand-green':'text-brand-red'}`}>
                    {pnlPos?'+':'-'}₹{Math.abs(t.pnl??0).toFixed(0)}
                  </p>
                  <p className={`text-xs ${STATUS_STYLE[t.status]??'text-brand-muted'}`}>
                    {t.status?.replace('_',' ')}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
