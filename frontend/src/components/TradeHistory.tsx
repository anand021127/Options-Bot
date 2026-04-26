'use client';
import { useState, useEffect, useCallback } from 'react';
import { api } from '@/utils/api';
import { History, RefreshCw, Filter, TrendingUp, TrendingDown, Clock, ChevronDown, ChevronUp } from 'lucide-react';

const STATUS_STYLE: Record<string, { bg: string; text: string; label: string }> = {
  TARGET_HIT:     { bg: 'bg-brand-green/15', text: 'text-brand-green', label: '🎯 Target Hit' },
  SL_HIT:         { bg: 'bg-brand-red/15',   text: 'text-brand-red',   label: '🛑 Stop Loss' },
  EMERGENCY_STOP: { bg: 'bg-brand-yellow/15', text: 'text-brand-yellow',label: '🚨 Emergency' },
  OPEN:           { bg: 'bg-brand-accent/15', text: 'text-brand-accent',label: '● Open' },
};

function fmtTime(iso: string): string {
  if (!iso) return '--';
  try {
    return new Date(iso).toLocaleTimeString('en-IN', {
      hour: '2-digit', minute: '2-digit',
      timeZone: 'Asia/Kolkata',
    });
  } catch { return '--'; }
}

function fmtDate(iso: string): string {
  if (!iso) return '--';
  try {
    return new Date(iso).toLocaleDateString('en-IN', {
      day: '2-digit', month: 'short', year: '2-digit',
      timeZone: 'Asia/Kolkata',
    });
  } catch { return '--'; }
}

function fmtDateTime(iso: string): string {
  if (!iso) return '--';
  try {
    return new Date(iso).toLocaleString('en-IN', {
      day: '2-digit', month: 'short',
      hour: '2-digit', minute: '2-digit',
      timeZone: 'Asia/Kolkata',
    });
  } catch { return '--'; }
}

// Determine ATM/ITM/OTM from notes or signal data
function getMoneyness(trade: any): string {
  const notes = trade.notes || '';
  if (notes.includes('ATM')) return 'ATM';
  if (notes.includes('ITM')) return 'ITM';
  if (notes.includes('OTM')) return 'OTM';
  // Derive from strike_type if stored in signal
  try {
    const sig = typeof trade.signal === 'string' ? JSON.parse(trade.signal) : trade.signal;
    if (sig?.strike_type) return sig.strike_type;
  } catch {}
  return '';
}

// Compact trade row (collapsed view)
function TradeRow({ trade, expanded, onToggle }: { trade: any; expanded: boolean; onToggle: () => void }) {
  const pnl = trade.pnl ?? 0;
  const isProfit = pnl > 0;
  const isLoss = pnl < 0;
  const isCE = trade.option_type === 'CE';
  const status = STATUS_STYLE[trade.status] || STATUS_STYLE.OPEN;
  const moneyness = getMoneyness(trade);
  const pnlPoints = trade.exit_price && trade.entry_price
    ? (trade.exit_price - trade.entry_price).toFixed(1)
    : '--';

  return (
    <div className={`rounded-xl border transition-all ${
      isProfit ? 'border-brand-green/15' : isLoss ? 'border-brand-red/15' : 'border-brand-border'
    }`}>
      {/* Compact header — always visible */}
      <div
        className="flex items-center justify-between px-3 py-2.5 cursor-pointer hover:bg-brand-surface/50 transition-all rounded-xl"
        onClick={onToggle}
      >
        <div className="flex items-center gap-2 min-w-0">
          <span className={`px-1.5 py-0.5 rounded text-xs font-mono font-bold flex-shrink-0 ${
            isCE ? 'bg-brand-green/15 text-brand-green' : 'bg-brand-red/15 text-brand-red'
          }`}>
            {trade.option_type}
          </span>
          <div className="min-w-0">
            <p className="text-brand-text font-mono font-semibold text-xs leading-tight truncate">
              ₹{trade.strike} {trade.symbol}
              {moneyness && (
                <span className="text-brand-muted font-normal ml-1">· {moneyness}</span>
              )}
            </p>
            <p className="text-brand-muted text-xs font-mono leading-tight">
              {fmtDate(trade.entry_time)} {fmtTime(trade.entry_time)}
              {trade.expiry && <span className="ml-1 text-brand-border">· exp {trade.expiry}</span>}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          <div className="text-right">
            <p className={`font-mono font-bold text-sm leading-tight ${
              isProfit ? 'text-brand-green' : isLoss ? 'text-brand-red' : 'text-brand-muted'
            }`}>
              {isProfit ? '+' : isLoss ? '' : ''}₹{Math.abs(pnl).toFixed(0)}
            </p>
            <p className={`text-xs font-mono leading-tight ${status.text}`}>
              {status.label}
            </p>
          </div>
          {expanded
            ? <ChevronUp size={12} className="text-brand-muted"/>
            : <ChevronDown size={12} className="text-brand-muted"/>
          }
        </div>
      </div>

      {/* Expanded details */}
      {expanded && (
        <div className="px-3 pb-3 pt-1 border-t border-brand-border/30 animate-slide-up">
          {/* Price grid */}
          <div className="grid grid-cols-4 gap-2 mb-2">
            <div className="bg-brand-surface rounded-lg p-2">
              <p className="text-brand-muted text-xs font-mono leading-none mb-0.5">Entry</p>
              <p className="text-brand-accent text-xs font-mono font-bold">₹{trade.entry_price}</p>
            </div>
            <div className="bg-brand-surface rounded-lg p-2">
              <p className="text-brand-muted text-xs font-mono leading-none mb-0.5">Exit</p>
              <p className={`text-xs font-mono font-bold ${
                trade.exit_price ? (isProfit ? 'text-brand-green' : 'text-brand-red') : 'text-brand-muted'
              }`}>
                {trade.exit_price ? `₹${trade.exit_price}` : '—'}
              </p>
            </div>
            <div className="bg-brand-surface rounded-lg p-2">
              <p className="text-brand-muted text-xs font-mono leading-none mb-0.5">Δ Points</p>
              <p className={`text-xs font-mono font-bold ${
                parseFloat(pnlPoints) > 0 ? 'text-brand-green' : parseFloat(pnlPoints) < 0 ? 'text-brand-red' : 'text-brand-muted'
              }`}>
                {pnlPoints !== '--' ? (parseFloat(pnlPoints) > 0 ? '+' : '') + pnlPoints : '--'}
              </p>
            </div>
            <div className="bg-brand-surface rounded-lg p-2">
              <p className="text-brand-muted text-xs font-mono leading-none mb-0.5">Qty</p>
              <p className="text-brand-text text-xs font-mono font-bold">
                {trade.lots && trade.lots > 0 ? `${trade.lots}L ×` : ''} {trade.quantity}
              </p>
            </div>
          </div>

          {/* SL / Target row */}
          <div className="grid grid-cols-3 gap-2 mb-2">
            <div className="bg-brand-surface rounded-lg p-2">
              <p className="text-brand-muted text-xs font-mono leading-none mb-0.5">SL</p>
              <p className="text-brand-red text-xs font-mono font-bold">₹{trade.sl_price}</p>
            </div>
            <div className="bg-brand-surface rounded-lg p-2">
              <p className="text-brand-muted text-xs font-mono leading-none mb-0.5">Target</p>
              <p className="text-brand-green text-xs font-mono font-bold">₹{trade.target_price}</p>
            </div>
            <div className="bg-brand-surface rounded-lg p-2">
              <p className="text-brand-muted text-xs font-mono leading-none mb-0.5">Strategy</p>
              <p className="text-brand-accent text-xs font-mono font-bold truncate">
                {trade.strategy_type || '—'}
              </p>
            </div>
          </div>

          {/* Time info */}
          <div className="flex items-center justify-between text-xs font-mono text-brand-muted">
            <div className="flex items-center gap-1">
              <Clock size={10}/>
              <span>Entry: {fmtDateTime(trade.entry_time)}</span>
            </div>
            {trade.exit_time && (
              <span>Exit: {fmtDateTime(trade.exit_time)}</span>
            )}
          </div>

          {/* Score & confidence */}
          {(trade.score > 0 || trade.confidence) && (
            <div className="flex gap-2 mt-1.5">
              {trade.score > 0 && (
                <span className="text-xs font-mono bg-brand-accent/10 text-brand-accent px-2 py-0.5 rounded-lg">
                  Score: {trade.score}
                </span>
              )}
              {trade.confidence && trade.confidence !== 'LOW' && (
                <span className="text-xs font-mono bg-brand-yellow/10 text-brand-yellow px-2 py-0.5 rounded-lg">
                  {trade.confidence}
                </span>
              )}
              {trade.regime && (
                <span className="text-xs font-mono bg-brand-surface text-brand-muted px-2 py-0.5 rounded-lg">
                  {trade.regime}
                </span>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

interface Props {
  refreshKey?: number;   // increment to trigger re-fetch
}

export default function TradeHistory({ refreshKey = 0 }: Props) {
  const [trades, setTrades] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'all' | 'wins' | 'losses' | 'open'>('all');
  const [expanded, setExpanded] = useState<number | null>(null);
  const [limit, setLimit] = useState(30);

  const fetchTrades = useCallback(async () => {
    try {
      const data = await api.getTradeHistory(limit);
      setTrades(data || []);
    } catch {} finally {
      setLoading(false);
    }
  }, [limit]);

  // Fetch on mount, on refreshKey change, and periodically
  useEffect(() => {
    fetchTrades();
  }, [fetchTrades, refreshKey]);

  useEffect(() => {
    const iv = setInterval(fetchTrades, 30000);
    return () => clearInterval(iv);
  }, [fetchTrades]);

  const filtered = trades.filter(t => {
    if (filter === 'wins') return (t.pnl ?? 0) > 0 && t.status !== 'OPEN';
    if (filter === 'losses') return (t.pnl ?? 0) < 0 && t.status !== 'OPEN';
    if (filter === 'open') return t.status === 'OPEN';
    return true;
  });

  // Summary stats
  const closed = trades.filter(t => t.status !== 'OPEN');
  const totalPnl = closed.reduce((s, t) => s + (t.pnl ?? 0), 0);
  const wins = closed.filter(t => (t.pnl ?? 0) > 0).length;
  const losses = closed.filter(t => (t.pnl ?? 0) < 0).length;

  if (loading) return (
    <div className="bg-brand-card card-glow rounded-2xl p-4">
      <div className="h-32 flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-brand-accent border-t-transparent rounded-full animate-spin"/>
      </div>
    </div>
  );

  return (
    <div className="bg-brand-card card-glow rounded-2xl p-4 space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <History size={14} className="text-brand-accent"/>
          <h2 className="font-display font-bold text-sm">Trade History</h2>
          <span className="text-brand-muted text-xs font-mono">({trades.length})</span>
        </div>
        <button onClick={fetchTrades} className="text-brand-muted hover:text-brand-accent transition-all p-1">
          <RefreshCw size={12}/>
        </button>
      </div>

      {/* Summary bar */}
      {closed.length > 0 && (
        <div className="flex gap-2">
          <div className={`flex-1 text-center py-1.5 rounded-lg text-xs font-mono font-bold ${
            totalPnl >= 0 ? 'bg-brand-green/10 text-brand-green' : 'bg-brand-red/10 text-brand-red'
          }`}>
            {totalPnl >= 0 ? '+' : ''}₹{totalPnl.toFixed(0)} P&L
          </div>
          <div className="flex-1 text-center py-1.5 rounded-lg bg-brand-green/10 text-brand-green text-xs font-mono font-bold">
            {wins}W
          </div>
          <div className="flex-1 text-center py-1.5 rounded-lg bg-brand-red/10 text-brand-red text-xs font-mono font-bold">
            {losses}L
          </div>
          {closed.length > 0 && (
            <div className="flex-1 text-center py-1.5 rounded-lg bg-brand-surface text-brand-text text-xs font-mono font-bold">
              {((wins / Math.max(closed.length, 1)) * 100).toFixed(0)}%
            </div>
          )}
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-1.5">
        {(['all', 'wins', 'losses', 'open'] as const).map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`text-xs font-mono px-2.5 py-1 rounded-lg transition-all capitalize ${
              filter === f
                ? 'bg-brand-accent/20 text-brand-accent border border-brand-accent/30'
                : 'text-brand-muted bg-brand-surface hover:bg-brand-border/30'
            }`}
          >
            {f}
          </button>
        ))}
      </div>

      {/* Trade list */}
      {!filtered.length ? (
        <div className="py-6 text-center text-brand-muted text-xs font-mono">
          {filter === 'all' ? 'No completed trades yet' : `No ${filter} trades`}
        </div>
      ) : (
        <div className="space-y-1.5 max-h-[500px] overflow-y-auto pr-1 scrollbar-none">
          {filtered.map((t: any) => (
            <TradeRow
              key={t.id}
              trade={t}
              expanded={expanded === t.id}
              onToggle={() => setExpanded(expanded === t.id ? null : t.id)}
            />
          ))}
        </div>
      )}

      {/* Load more */}
      {trades.length >= limit && (
        <button
          onClick={() => setLimit(l => l + 30)}
          className="w-full text-center text-xs font-mono text-brand-accent hover:text-brand-accent/80 py-2"
        >
          Load more trades...
        </button>
      )}
    </div>
  );
}
