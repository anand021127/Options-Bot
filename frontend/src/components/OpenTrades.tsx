'use client';
import { Clock } from 'lucide-react';

function TradeRow({ trade, currentPrice }: any) {
  const isCE  = trade.option_type === 'CE';

  const entryTime = trade.entry_time
    ? new Date(trade.entry_time).toLocaleTimeString('en-IN',{
        hour:'2-digit',minute:'2-digit',
        timeZone: 'Asia/Kolkata',
      })
    : '--';

  return (
    <div className="bg-brand-surface rounded-xl p-3 border border-brand-border hover:border-brand-accent/30 transition-all">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className={`px-2 py-0.5 rounded text-xs font-mono font-bold ${
            isCE ? 'bg-brand-green/15 text-brand-green' : 'bg-brand-red/15 text-brand-red'
          }`}>
            {trade.option_type}
          </span>
          <span className="font-mono text-sm font-bold text-brand-text">₹{trade.strike}</span>
          <span className="text-brand-muted text-xs">{trade.symbol}</span>
        </div>
        <div className="flex items-center gap-1 text-brand-muted text-xs font-mono">
          <Clock size={10}/>
          {entryTime}
        </div>
      </div>

      <div className="grid grid-cols-4 gap-1 text-xs font-mono">
        <div>
          <p className="text-brand-muted">Entry</p>
          <p className="text-brand-text font-semibold">₹{trade.entry_price}</p>
        </div>
        <div>
          <p className="text-brand-muted">SL</p>
          <p className="text-brand-red font-semibold">₹{trade.sl_price}</p>
        </div>
        <div>
          <p className="text-brand-muted">Target</p>
          <p className="text-brand-green font-semibold">₹{trade.target_price}</p>
        </div>
        <div>
          <p className="text-brand-muted">Qty</p>
          <p className="text-brand-text font-semibold">{trade.quantity}</p>
        </div>
      </div>

      {/* Note: Accurate live P&L is shown in Live Positions (TradeTracker) */}
      <div className="mt-2 pt-2 border-t border-brand-border flex items-center justify-between">
        <span className="text-brand-muted text-xs font-mono">Live P&L</span>
        <span className="text-brand-accent text-xs font-mono">See Live Positions ↑</span>
      </div>
    </div>
  );
}

export default function OpenTrades({ trades, currentPrice }: any) {
  return (
    <div className="bg-brand-card card-glow rounded-2xl p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="font-display font-bold text-sm">Open Positions</h2>
        <span className="bg-brand-accent/20 text-brand-accent text-xs font-mono px-2 py-0.5 rounded-full">
          {trades?.length ?? 0} active
        </span>
      </div>
      {!trades?.length ? (
        <div className="py-6 text-center text-brand-muted text-xs font-mono">No open positions</div>
      ) : (
        <div className="space-y-2">
          {trades.map((t: any) => <TradeRow key={t.id} trade={t} currentPrice={currentPrice}/>)}
        </div>
      )}
    </div>
  );
}
