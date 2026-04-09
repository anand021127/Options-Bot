'use client';
export default function StatsBar({ stats }: any) {
  if (!stats) return null;
  const rr = stats.rr_ratio ?? 0;
  const items = [
    { label: 'Win Rate', value: `${stats.win_rate ?? 0}%`, color: (stats.win_rate ?? 0) >= 50 ? 'text-brand-green' : 'text-brand-red' },
    { label: 'Trades',  value: stats.total_trades ?? 0,   color: 'text-brand-text' },
    { label: 'Wins',    value: stats.wins    ?? 0,         color: 'text-brand-green' },
    { label: 'Losses',  value: stats.losses  ?? 0,         color: 'text-brand-red' },
    { label: 'R:R',     value: `1:${rr}`,                  color: rr >= 1.5 ? 'text-brand-green' : 'text-brand-yellow' },
    { label: 'Best',    value: `₹${Math.abs(stats.best_trade ?? 0).toFixed(0)}`, color: 'text-brand-green' },
    { label: 'Worst',   value: `-₹${Math.abs(stats.worst_trade ?? 0).toFixed(0)}`, color: 'text-brand-red' },
    { label: 'Avg P&L', value: `${(stats.avg_pnl ?? 0) >= 0 ? '+' : ''}₹${(stats.avg_pnl ?? 0).toFixed(0)}`,
      color: (stats.avg_pnl ?? 0) >= 0 ? 'text-brand-green' : 'text-brand-red' },
  ];

  return (
    <div className="flex overflow-x-auto border-b border-brand-border bg-brand-surface/50">
      {items.map((it, i) => (
        <div key={i} className="flex-shrink-0 px-3 py-2 text-center border-r border-brand-border last:border-r-0 min-w-[60px]">
          <p className="text-brand-muted text-xs font-mono">{it.label}</p>
          <p className={`font-mono font-bold text-xs ${it.color}`}>{it.value}</p>
        </div>
      ))}
    </div>
  );
}
