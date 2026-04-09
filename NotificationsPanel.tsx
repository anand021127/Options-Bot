'use client';

import { useEffect, useState } from 'react';
import { api } from '@/utils/api';
import { RefreshCw } from 'lucide-react';

interface Props {
  symbol: string;
  spot?: number;
}

export default function OptionsChain({ symbol, spot }: Props) {
  const [chain, setChain]     = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [expiry, setExpiry]   = useState<string>('');
  const [view, setView]       = useState<'both'|'CE'|'PE'>('both');

  const fetchChain = async () => {
    setLoading(true);
    try {
      const data = await api.getOptions(symbol);
      setChain(data);
      setExpiry(data.expiry);
    } catch {}
    setLoading(false);
  };

  useEffect(() => { fetchChain(); }, [symbol]);

  if (!chain) return (
    <div className="rounded-xl p-4 card-glow" style={{ background: '#1A2235' }}>
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs font-semibold" style={{ color: '#64748B' }}>OPTIONS CHAIN</p>
        <button onClick={fetchChain} className="p-1.5 rounded-lg" style={{ background: '#243049', color: '#00D4FF' }}>
          <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>
      <p className="text-xs text-center py-8" style={{ color: '#64748B' }}>
        {loading ? 'Loading chain…' : 'No options data. Tap refresh.'}
      </p>
    </div>
  );

  const spotPrice  = spot ?? chain.spot;
  const calls      = chain.calls ?? [];
  const puts       = chain.puts  ?? [];

  // Combine by strike, show ±10 strikes around ATM
  const allStrikes = Array.from(new Set([...calls.map((c: any) => c.strike), ...puts.map((p: any) => p.strike)])).sort((a: any, b: any) => a - b);
  const atmIdx     = allStrikes.reduce((best: number, s: number, i: number) =>
    Math.abs(s - spotPrice) < Math.abs(allStrikes[best] - spotPrice) ? i : best, 0);
  const visStrikes = allStrikes.slice(Math.max(0, atmIdx - 6), atmIdx + 7);

  const callMap = Object.fromEntries(calls.map((c: any) => [c.strike, c]));
  const putMap  = Object.fromEntries(puts.map((p: any)  => [p.strike, p]));

  return (
    <div className="rounded-xl card-glow overflow-hidden" style={{ background: '#1A2235' }}>
      {/* Header */}
      <div className="p-4 flex items-center justify-between" style={{ borderBottom: '1px solid #243049' }}>
        <div>
          <p className="text-xs font-semibold" style={{ color: '#64748B' }}>OPTIONS CHAIN · {symbol}</p>
          <p className="text-xs num mt-0.5" style={{ color: '#00D4FF' }}>Spot: ₹{spotPrice?.toLocaleString('en-IN')}</p>
        </div>
        <div className="flex items-center gap-2">
          {/* Expiry select */}
          {chain.available_expiries?.length > 0 && (
            <select value={expiry} onChange={e => setExpiry(e.target.value)}
                    className="text-xs px-2 py-1 rounded outline-none"
                    style={{ background: '#111827', color: '#E2E8F0', border: '1px solid #243049' }}>
              {chain.available_expiries.map((e: string) => <option key={e} value={e}>{e}</option>)}
            </select>
          )}
          <button onClick={fetchChain} className="p-1.5 rounded-lg" style={{ background: '#243049', color: '#00D4FF' }}>
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {/* View toggle */}
      <div className="flex border-b" style={{ borderColor: '#243049' }}>
        {(['both', 'CE', 'PE'] as const).map(v => (
          <button key={v} onClick={() => setView(v)}
                  className="flex-1 py-2 text-xs font-medium"
                  style={{ color: view === v ? '#00D4FF' : '#64748B',
                           borderBottom: view === v ? '2px solid #00D4FF' : '2px solid transparent' }}>
            {v === 'both' ? 'All' : v}
          </button>
        ))}
      </div>

      {/* Table header */}
      <div className="grid gap-px text-xs" style={{
        gridTemplateColumns: view === 'both' ? '1fr 0.6fr 1fr' : '1fr 1fr 1fr',
        background: '#243049',
      }}>
        {view !== 'PE' && (
          <div className="grid grid-cols-3 px-2 py-1.5" style={{ background: '#1A2235' }}>
            <span style={{ color: '#00FF88' }}>OI</span>
            <span style={{ color: '#00FF88' }}>Vol</span>
            <span style={{ color: '#00FF88' }}>LTP</span>
          </div>
        )}
        <div className="px-2 py-1.5 text-center" style={{ background: '#1A2235' }}>
          <span style={{ color: '#E2E8F0' }}>STRIKE</span>
        </div>
        {view !== 'CE' && (
          <div className="grid grid-cols-3 px-2 py-1.5" style={{ background: '#1A2235' }}>
            <span style={{ color: '#FF3B5C' }}>LTP</span>
            <span style={{ color: '#FF3B5C' }}>Vol</span>
            <span style={{ color: '#FF3B5C' }}>OI</span>
          </div>
        )}
      </div>

      {/* Rows */}
      <div className="overflow-y-auto" style={{ maxHeight: '55vh' }}>
        {visStrikes.map((strike: number) => {
          const call    = callMap[strike] ?? {};
          const put     = putMap[strike]  ?? {};
          const isATM   = Math.abs(strike - spotPrice) < 50;
          const rowBg   = isATM ? '#243049' : 'transparent';

          return (
            <div key={strike} className="grid gap-px text-xs"
                 style={{ gridTemplateColumns: view === 'both' ? '1fr 0.6fr 1fr' : '1fr 1fr 1fr',
                          background: '#243049' }}>
              {view !== 'PE' && (
                <div className="grid grid-cols-3 px-2 py-2" style={{ background: isATM ? '#1e2d40' : '#111827' }}>
                  <span className="num" style={{ color: '#94A3B8' }}>{((call.oi ?? 0)/1000).toFixed(0)}K</span>
                  <span className="num" style={{ color: '#94A3B8' }}>{((call.volume ?? 0)/1000).toFixed(0)}K</span>
                  <span className="num font-semibold" style={{ color: '#00FF88' }}>₹{(call.ltp ?? 0).toFixed(1)}</span>
                </div>
              )}
              <div className="px-2 py-2 text-center font-bold num"
                   style={{ background: isATM ? '#243049' : '#1A2235', color: isATM ? '#00D4FF' : '#E2E8F0' }}>
                {strike.toLocaleString('en-IN')}
                {isATM && <span className="block text-xs" style={{ color: '#64748B', fontSize: 9 }}>ATM</span>}
              </div>
              {view !== 'CE' && (
                <div className="grid grid-cols-3 px-2 py-2" style={{ background: isATM ? '#2d1e24' : '#111827' }}>
                  <span className="num font-semibold" style={{ color: '#FF3B5C' }}>₹{(put.ltp ?? 0).toFixed(1)}</span>
                  <span className="num" style={{ color: '#94A3B8' }}>{((put.volume ?? 0)/1000).toFixed(0)}K</span>
                  <span className="num" style={{ color: '#94A3B8' }}>{((put.oi ?? 0)/1000).toFixed(0)}K</span>
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="px-4 py-2" style={{ borderTop: '1px solid #243049' }}>
        <p className="text-xs" style={{ color: '#64748B' }}>⏱ ~15min delayed via yfinance free API</p>
      </div>
    </div>
  );
}
