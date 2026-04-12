'use client';
import { useEffect, useState, useCallback } from 'react';
import { RefreshCw, ChevronDown, Zap, AlertTriangle } from 'lucide-react';
import { api } from '@/utils/api';

interface Contract {
  strike:          number;
  ltp:             number;
  bid:             number;
  ask:             number;
  volume:          number;
  oi:              number;
  iv:              number;
  delta:           number;
  instrument_key:  string;
  lot_size:        number | null;
}
interface Chain {
  symbol:    string;
  expiry:    string;         // actual from Upstox API
  spot:      number;         // real spot from Upstox
  calls:     Contract[];
  puts:      Contract[];
  timestamp: string;
  source:    string;
}

function fmt(n: number, dec = 0) {
  if (!n && n !== 0) return '--';
  return n.toLocaleString('en-IN', { maximumFractionDigits: dec, minimumFractionDigits: dec });
}
function fmtDate(s: string) {
  if (!s) return '--';
  try {
    return new Date(s).toLocaleDateString('en-IN', {
      day: '2-digit', month: 'short', year: '2-digit', timeZone: 'Asia/Kolkata',
    });
  } catch { return s; }
}

interface Props { symbol: string; spot?: number; }

export default function OptionsChain({ symbol, spot }: Props) {
  const [chain,     setChain]     = useState<Chain | null>(null);
  const [expiries,  setExpiries]  = useState<string[]>([]);
  const [selExpiry, setSelExpiry] = useState('');
  const [loading,   setLoading]   = useState(false);
  const [error,     setError]     = useState('');
  const [view,      setView]      = useState<'both'|'CE'|'PE'>('both');
  const [showAtm,   setShowAtm]   = useState(10); // how many strikes either side of ATM

  // Load expiries from Upstox instruments API
  const loadExpiries = useCallback(async () => {
    try {
      const data = await api.getExpiries(symbol);
      setExpiries(data.expiries || []);
      if (data.expiries?.length && !selExpiry) {
        setSelExpiry(data.expiries[0]);
      }
    } catch (e: any) {
      setError(`Could not load expiries: ${e.message}`);
    }
  }, [symbol, selExpiry]);

  // Fetch option chain
  const fetchChain = useCallback(async () => {
    if (!selExpiry) return;
    setLoading(true);
    setError('');
    try {
      const data = await api.getOptions(symbol, selExpiry);
      setChain(data);
    } catch (e: any) {
      setError(`Chain fetch failed: ${e.message}`);
      setChain(null);
    } finally {
      setLoading(false);
    }
  }, [symbol, selExpiry]);

  useEffect(() => { loadExpiries(); }, [symbol]);
  useEffect(() => { if (selExpiry) fetchChain(); }, [selExpiry]);

  // Auto-refresh every 15s
  useEffect(() => {
    const iv = setInterval(() => { if (selExpiry) fetchChain(); }, 15000);
    return () => clearInterval(iv);
  }, [selExpiry, fetchChain]);

  const currentSpot = chain?.spot || spot || 0;

  // Filter to ATM ± showAtm strikes
  const filterStrikes = (contracts: Contract[]) => {
    if (!currentSpot || !contracts.length) return contracts;
    const sorted = [...contracts].sort((a, b) => a.strike - b.strike);
    const atmIdx = sorted.reduce((best, c, i) =>
      Math.abs(c.strike - currentSpot) < Math.abs(sorted[best].strike - currentSpot) ? i : best, 0);
    return sorted.slice(Math.max(0, atmIdx - showAtm), atmIdx + showAtm + 1);
  };

  const calls  = filterStrikes(chain?.calls || []);
  const puts   = filterStrikes(chain?.puts  || []);
  const atmStr = currentSpot ? Math.round(currentSpot / 50) * 50 : 0;

  return (
    <div className="bg-brand-card card-glow rounded-2xl overflow-hidden">
      {/* Header */}
      <div className="px-4 pt-4 pb-3 border-b border-brand-border space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h2 className="font-display font-bold text-sm">Options Chain</h2>
            {chain?.source === 'upstox' && (
              <span className="flex items-center gap-1 text-xs font-mono text-brand-yellow bg-brand-yellow/10 px-1.5 py-0.5 rounded border border-brand-yellow/20">
                <Zap size={9} />LIVE
              </span>
            )}
          </div>
          <button onClick={fetchChain} disabled={loading}
            className="p-1.5 rounded-lg text-brand-muted hover:text-brand-accent hover:bg-brand-accent/10 transition-all">
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>

        {/* Spot price */}
        {currentSpot > 0 && (
          <div className="flex items-center gap-2">
            <span className="text-brand-muted text-xs font-mono">{symbol} Spot</span>
            <span className="font-mono font-bold text-brand-accent">
              ₹{fmt(currentSpot, 2)}
            </span>
            {chain?.timestamp && (
              <span className="text-brand-border text-xs font-mono">
                {new Date(chain.timestamp).toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata' })}
              </span>
            )}
          </div>
        )}

        {/* Expiry selector — dates from Upstox API */}
        {expiries.length > 0 && (
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-brand-muted text-xs font-mono">Expiry:</span>
            <div className="flex gap-1 flex-wrap">
              {expiries.slice(0, 6).map(exp => (
                <button key={exp} onClick={() => setSelExpiry(exp)}
                  className={`text-xs font-mono px-2 py-1 rounded-lg border transition-all ${
                    selExpiry === exp
                      ? 'bg-brand-accent/20 border-brand-accent text-brand-accent'
                      : 'border-brand-border text-brand-muted hover:border-brand-accent/50'
                  }`}>
                  {fmtDate(exp)}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* View toggle */}
        <div className="flex items-center gap-2">
          <div className="flex rounded-lg overflow-hidden border border-brand-border">
            {(['both', 'CE', 'PE'] as const).map(v => (
              <button key={v} onClick={() => setView(v)}
                className={`px-3 py-1 text-xs font-mono font-bold transition-all ${
                  view === v
                    ? v === 'CE' ? 'bg-brand-green/20 text-brand-green'
                      : v === 'PE' ? 'bg-brand-red/20 text-brand-red'
                      : 'bg-brand-accent/20 text-brand-accent'
                    : 'text-brand-muted'
                }`}>{v}</button>
            ))}
          </div>
          <select value={showAtm} onChange={e => setShowAtm(parseInt(e.target.value))}
            className="bg-brand-surface border border-brand-border rounded-lg px-2 py-1 text-xs font-mono text-brand-muted focus:outline-none">
            {[5, 10, 15, 20].map(n => (
              <option key={n} value={n}>±{n} strikes</option>
            ))}
          </select>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="m-4 flex items-start gap-2 bg-brand-red/10 border border-brand-red/30 rounded-xl p-3">
          <AlertTriangle size={14} className="text-brand-red flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-brand-red text-xs font-mono font-bold">Data Error</p>
            <p className="text-brand-red/70 text-xs font-mono mt-0.5">{error}</p>
            <p className="text-brand-muted text-xs font-mono mt-1">
              Make sure Upstox is logged in and instruments are loaded.
            </p>
          </div>
        </div>
      )}

      {/* No data */}
      {!chain && !loading && !error && (
        <div className="py-10 text-center">
          <p className="text-brand-muted text-xs font-mono">
            {expiries.length === 0
              ? 'Login to Upstox to load instruments & expiries'
              : 'Select an expiry to load chain'}
          </p>
          {expiries.length === 0 && (
            <button onClick={loadExpiries}
              className="mt-2 text-brand-accent text-xs font-mono underline">
              Retry loading instruments
            </button>
          )}
        </div>
      )}

      {/* Chain table */}
      {chain && (
        <div className="overflow-x-auto">
          {/* Column headers */}
          <div className="grid text-xs font-mono text-brand-muted px-2 py-1.5 border-b border-brand-border/50"
            style={{ gridTemplateColumns: view === 'both' ? '1fr 1fr 0.8fr 1fr 1fr' : '1fr 0.8fr 1fr' }}>
            {(view === 'both' || view === 'CE') && (
              <><span className="text-center text-brand-green">CE LTP</span>
                <span className="text-center text-brand-green">CE OI</span></>
            )}
            <span className="text-center font-bold text-brand-text">STRIKE</span>
            {(view === 'both' || view === 'PE') && (
              <><span className="text-center text-brand-red">PE OI</span>
                <span className="text-center text-brand-red">PE LTP</span></>
            )}
          </div>

          {/* Rows */}
          <div className="max-h-[480px] overflow-y-auto">
            {calls.map((ce, i) => {
              const pe      = puts.find(p => p.strike === ce.strike);
              const isATM   = Math.abs(ce.strike - atmStr) < 26;
              const isAbove = ce.strike > currentSpot;

              return (
                <div key={ce.strike}
                  className={`grid text-xs font-mono px-2 py-1.5 border-b border-brand-border/30 transition-colors ${
                    isATM
                      ? 'bg-brand-accent/8 border-brand-accent/30'
                      : i % 2 === 0 ? 'bg-brand-surface/30' : ''
                  }`}
                  style={{ gridTemplateColumns: view === 'both' ? '1fr 1fr 0.8fr 1fr 1fr' : '1fr 0.8fr 1fr' }}>

                  {/* CE side */}
                  {(view === 'both' || view === 'CE') && (
                    <>
                      <span className={`text-center font-semibold ${
                        ce.ltp > 0 ? 'text-brand-green' : 'text-brand-border'
                      }`}>
                        {ce.ltp > 0 ? `₹${fmt(ce.ltp, 1)}` : '--'}
                      </span>
                      <span className="text-center text-brand-muted">
                        {ce.oi > 0 ? (ce.oi >= 1e6 ? `${(ce.oi/1e6).toFixed(1)}M` : `${(ce.oi/1e3).toFixed(0)}K`) : '--'}
                      </span>
                    </>
                  )}

                  {/* Strike */}
                  <span className={`text-center font-bold ${
                    isATM ? 'text-brand-accent' : isAbove ? 'text-brand-muted' : 'text-brand-text'
                  }`}>
                    {fmt(ce.strike)}
                    {isATM && <span className="ml-1 text-brand-accent/60 text-xs">ATM</span>}
                  </span>

                  {/* PE side */}
                  {(view === 'both' || view === 'PE') && (
                    <>
                      <span className="text-center text-brand-muted">
                        {pe?.oi && pe.oi > 0 ? (pe.oi >= 1e6 ? `${(pe.oi/1e6).toFixed(1)}M` : `${(pe.oi/1e3).toFixed(0)}K`) : '--'}
                      </span>
                      <span className={`text-center font-semibold ${
                        pe?.ltp && pe.ltp > 0 ? 'text-brand-red' : 'text-brand-border'
                      }`}>
                        {pe?.ltp && pe.ltp > 0 ? `₹${fmt(pe.ltp, 1)}` : '--'}
                      </span>
                    </>
                  )}
                </div>
              );
            })}
          </div>

          {/* Footer */}
          <div className="px-4 py-2 border-t border-brand-border flex items-center justify-between">
            <span className="text-brand-muted text-xs font-mono">
              {calls.length} strikes · Exp: {fmtDate(chain.expiry)}
            </span>
            {chain.calls[0]?.lot_size && (
              <span className="text-brand-muted text-xs font-mono">
                lot_size={chain.calls[0].lot_size} (from API)
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
