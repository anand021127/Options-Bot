'use client';
import { useState, useEffect, useCallback } from 'react';
import { FileSearch, RefreshCw, CheckCircle, XCircle, AlertTriangle, ChevronDown, ChevronUp, Filter } from 'lucide-react';
import { api } from '@/utils/api';

interface SignalEntry {
  id: number;
  timestamp: string;
  symbol: string;
  signal_type: string;
  reason: string;
  blocked_by: string;
  price: number;
  score: number;
  strategy: string;
  acted: number;
}

export default function SignalDecisionLog() {
  const [signals,  setSignals]  = useState<SignalEntry[]>([]);
  const [loading,  setLoading]  = useState(true);
  const [filter,   setFilter]   = useState<'all' | 'acted' | 'blocked'>('all');
  const [expanded, setExpanded] = useState<number | null>(null);

  const fetchSignals = useCallback(async () => {
    try {
      const data = await api.getSignalLog(80);
      setSignals(data || []);
    } catch {} finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchSignals(); const iv = setInterval(fetchSignals, 10000); return () => clearInterval(iv); }, [fetchSignals]);

  const filtered = signals.filter(s => {
    // Never show market-closed signals in the UI (noise from weekends/holidays)
    if (s.blocked_by === 'MARKET_CLOSED') return false;
    if (filter === 'acted') return s.acted === 1;
    if (filter === 'blocked') return s.blocked_by && s.blocked_by !== '';
    return true;
  });

  const getIcon = (s: SignalEntry) => {
    if (s.acted) return <CheckCircle size={12} className="text-brand-green" />;
    if (s.blocked_by) return <XCircle size={12} className="text-brand-red" />;
    return <AlertTriangle size={12} className="text-brand-yellow" />;
  };

  const getStatusColor = (s: SignalEntry) => {
    if (s.acted) return 'border-brand-green/20 bg-brand-green/5';
    if (s.blocked_by) return 'border-brand-red/10';
    return 'border-brand-border';
  };

  const getSignalColor = (type: string) => {
    if (type.includes('BULL') || type.includes('CE')) return 'text-brand-green';
    if (type.includes('BEAR') || type.includes('PE')) return 'text-brand-red';
    return 'text-brand-muted';
  };

  if (loading) return (
    <div className="bg-brand-card card-glow rounded-2xl p-4 animate-pulse">
      <div className="h-4 bg-brand-border rounded w-1/3 mb-3" />
      <div className="space-y-2">
        {[1,2,3].map(i => <div key={i} className="h-12 bg-brand-border rounded" />)}
      </div>
    </div>
  );

  const actedCount   = signals.filter(s => s.acted).length;
  const blockedCount = signals.filter(s => s.blocked_by).length;

  return (
    <div className="bg-brand-card card-glow rounded-2xl p-4 space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <FileSearch size={14} className="text-brand-accent" />
          <h2 className="font-display font-bold text-sm">Signal Decision Log</h2>
        </div>
        <button onClick={fetchSignals} className="text-brand-muted hover:text-brand-accent transition-all">
          <RefreshCw size={12} />
        </button>
      </div>

      {/* Stats bar */}
      <div className="flex gap-2">
        <span className="text-xs font-mono bg-brand-surface px-2 py-1 rounded-lg text-brand-muted">
          {signals.length} total
        </span>
        <span className="text-xs font-mono bg-brand-green/10 px-2 py-1 rounded-lg text-brand-green">
          {actedCount} acted
        </span>
        <span className="text-xs font-mono bg-brand-red/10 px-2 py-1 rounded-lg text-brand-red">
          {blockedCount} blocked
        </span>
      </div>

      {/* Filter pills */}
      <div className="flex gap-1.5">
        {(['all', 'acted', 'blocked'] as const).map(f => (
          <button key={f} onClick={() => setFilter(f)}
            className={`text-xs font-mono px-2.5 py-1 rounded-lg transition-all capitalize ${
              filter === f
                ? 'bg-brand-accent/20 text-brand-accent border border-brand-accent/30'
                : 'text-brand-muted bg-brand-surface hover:bg-brand-border/30'
            }`}>
            {f}
          </button>
        ))}
      </div>

      {/* Signal entries */}
      <div className="space-y-1.5 max-h-[400px] overflow-y-auto scrollbar-none">
        {filtered.length === 0 && (
          <p className="text-brand-muted text-xs font-mono text-center py-4">
            No signals matching filter
          </p>
        )}
        {filtered.slice(0, 30).map((s) => (
          <div key={s.id}
            className={`rounded-xl border transition-all ${getStatusColor(s)}`}>
            <div
              className="flex items-center gap-2 px-3 py-2 cursor-pointer"
              onClick={() => setExpanded(expanded === s.id ? null : s.id)}>
              {getIcon(s)}
              <span className={`text-xs font-mono font-bold flex-shrink-0 ${getSignalColor(s.signal_type)}`}>
                {s.signal_type || 'NO_TRADE'}
              </span>
              <span className="text-xs font-mono text-brand-muted truncate flex-1">
                {s.blocked_by ? `⛔ ${s.blocked_by}` : s.strategy || '—'}
              </span>
              <span className={`text-xs font-mono font-bold flex-shrink-0 ${
                s.score >= 5 ? 'text-brand-green' : s.score >= 3 ? 'text-brand-yellow' : 'text-brand-muted'
              }`}>
                {s.score > 0 ? `${s.score}pts` : ''}
              </span>
              <span className="text-brand-muted/50 text-xs font-mono flex-shrink-0">
                {new Date(s.timestamp).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}
              </span>
              {expanded === s.id ? <ChevronUp size={10} className="text-brand-muted"/> : <ChevronDown size={10} className="text-brand-muted"/>}
            </div>

            {expanded === s.id && (
              <div className="px-3 pb-2.5 pt-0 text-xs font-mono space-y-1 border-t border-brand-border/30 mt-0.5">
                {s.price > 0 && (
                  <p className="text-brand-text">Price: ₹{s.price.toFixed(2)}</p>
                )}
                {s.reason && (
                  <div className="space-y-0.5">
                    {s.reason.split(';').map((r, i) => (
                      <p key={i} className="text-brand-muted">{r.trim()}</p>
                    ))}
                  </div>
                )}
                {s.strategy && s.strategy !== 'UNKNOWN' && (
                  <p className="text-brand-accent">Strategy: {s.strategy}</p>
                )}
                <p className="text-brand-muted/50">
                  {new Date(s.timestamp).toLocaleString('en-IN')}
                </p>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
