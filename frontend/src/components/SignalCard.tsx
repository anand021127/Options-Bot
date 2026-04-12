'use client';
import { useState } from 'react';
import { RefreshCw, TrendingUp, TrendingDown, Minus, CheckCircle, XCircle, AlertTriangle, Shield } from 'lucide-react';

const REGIME_STYLE: Record<string, string> = {
  TRENDING:    'text-brand-green bg-brand-green/10 border-brand-green/30',
  SIDEWAYS:    'text-brand-yellow bg-brand-yellow/10 border-brand-yellow/30',
  VOLATILE:    'text-brand-red bg-brand-red/10 border-brand-red/30',
  WEAK_TREND:  'text-brand-muted bg-brand-surface border-brand-border',
  UNKNOWN:     'text-brand-muted bg-brand-surface border-brand-border',
};

const IV_STYLE: Record<string, { color: string; label: string }> = {
  LOW_IV:     { color: 'text-brand-green',  label: '✅ Low (Buy options — cheap)' },
  NORMAL_IV:  { color: 'text-brand-text',   label: '🟡 Normal' },
  HIGH_IV:    { color: 'text-brand-yellow', label: '⚠️ High (Caution)' },
  EXTREME_IV: { color: 'text-brand-red',    label: '🚫 Extreme (Avoid buying)' },
};

const BLOCKED_MESSAGES: Record<string, string> = {
  SIDEWAYS_MARKET: '📊 ADX too low — sideways market, no edge',
  VOLATILE_MARKET: '⚡ Extreme volatility — options overpriced',
  HIGH_IV:         '💰 Premium too expensive — IV too high',
  TIME_FILTER:     '⏰ Outside valid trading hours',
  FAKE_SPIKE:      '🕯️ Candle spike detected — possible manipulation',
  LOW_VOLUME:      '📉 Volume too low — weak signal conviction',
  NO_DATA:         '📡 Data unavailable — check connection',
  NO_OPTION_DATA:  '📋 Options chain unavailable',
};

export default function SignalCard({ signal, symbol, onRefresh }: any) {
  const [loading, setLoading] = useState(false);

  const refresh = async () => { setLoading(true); try { await onRefresh(); } finally { setLoading(false); } };

  const isBull   = signal?.signal_type === 'BUY_CE';
  const isBear   = signal?.signal_type === 'BUY_PE';
  const noTrade  = !signal || signal.signal_type === 'NO_TRADE';
  const score    = signal?.score ?? 0;
  const maxScore = signal?.max_score ?? 12;
  const blocked  = signal?.blocked_by;
  const regime   = signal?.indicators?.regime || signal?.regime;
  const ivData   = signal?.indicators?.iv_rank || {};
  const ivRegime = ivData.regime || 'NORMAL_IV';
  const mtfBias  = signal?.mtf_bias || signal?.indicators?.mtf_bias;
  const adxVal   = signal?.adx || signal?.indicators?.adx;

  const scoreColor = score >= 7 ? 'text-brand-green' : score >= 5 ? 'text-brand-yellow' : 'text-brand-red';

  return (
    <div className="bg-brand-card card-glow rounded-2xl p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="font-display font-bold text-sm">Signal Engine</h2>
        <div className="flex items-center gap-2">
          {regime && (
            <span className={`text-xs font-mono font-bold px-2 py-0.5 rounded border ${REGIME_STYLE[regime] || REGIME_STYLE.UNKNOWN}`}>
              {regime}
            </span>
          )}
          <button onClick={refresh} disabled={loading}
            className="p-1.5 rounded-lg text-brand-muted hover:text-brand-accent hover:bg-brand-accent/10 transition-all">
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''}/>
          </button>
        </div>
      </div>

      {/* Blocked reason */}
      {blocked && (
        <div className="bg-brand-yellow/5 border border-brand-yellow/25 rounded-xl px-3 py-2 flex items-start gap-2">
          <AlertTriangle size={13} className="text-brand-yellow mt-0.5 flex-shrink-0"/>
          <p className="text-brand-yellow text-xs font-mono">
            {BLOCKED_MESSAGES[blocked] || `Blocked: ${blocked}`}
          </p>
        </div>
      )}

      {/* Signal badge */}
      <div className={`rounded-xl p-3 border text-center ${
        isBull ? 'bg-brand-green/10 border-brand-green/30'
        : isBear ? 'bg-brand-red/10 border-brand-red/30'
        : 'bg-brand-surface border-brand-border'
      }`}>
        <div className="flex items-center justify-center gap-2 mb-1">
          {isBull ? <TrendingUp size={18} className="text-brand-green"/>
           : isBear ? <TrendingDown size={18} className="text-brand-red"/>
           : <Minus size={18} className="text-brand-muted"/>}
          <span className={`font-display font-bold text-xl ${isBull ? 'text-brand-green' : isBear ? 'text-brand-red' : 'text-brand-muted'}`}>
            {signal?.signal_type ?? 'WAITING...'}
          </span>
        </div>

        {/* Score bar */}
        <div className="flex items-center justify-center gap-2">
          <span className="text-brand-muted text-xs font-mono">Score</span>
          <span className={`font-mono font-bold text-sm ${scoreColor}`}>{score}/{maxScore}</span>
          <div className="flex gap-0.5">
            {Array.from({ length: maxScore }).map((_, i) => (
              <div key={i} className={`w-1.5 h-3 rounded-sm ${
                i < score
                  ? isBull ? 'bg-brand-green' : isBear ? 'bg-brand-red' : 'bg-brand-yellow'
                  : 'bg-brand-border'
              }`}/>
            ))}
          </div>
        </div>
      </div>

      {/* Market context row */}
      <div className="grid grid-cols-3 gap-2">
        {/* ADX */}
        <div className="bg-brand-surface rounded-lg p-2 text-center">
          <p className="text-brand-muted text-xs font-mono">ADX</p>
          <p className={`font-mono font-bold text-sm ${adxVal >= 25 ? 'text-brand-green' : adxVal >= 20 ? 'text-brand-yellow' : 'text-brand-red'}`}>
            {adxVal ? adxVal.toFixed(0) : '--'}
          </p>
          <p className="text-brand-muted text-xs">{adxVal >= 25 ? 'Trend' : adxVal >= 20 ? 'Weak' : 'Chop'}</p>
        </div>

        {/* MTF */}
        <div className="bg-brand-surface rounded-lg p-2 text-center">
          <p className="text-brand-muted text-xs font-mono">15m Bias</p>
          <p className={`font-mono font-bold text-sm ${mtfBias === 'BULL' ? 'text-brand-green' : mtfBias === 'BEAR' ? 'text-brand-red' : 'text-brand-muted'}`}>
            {mtfBias || 'NEUTRAL'}
          </p>
          <p className="text-brand-muted text-xs">Multi-TF</p>
        </div>

        {/* IV Rank */}
        <div className="bg-brand-surface rounded-lg p-2 text-center">
          <p className="text-brand-muted text-xs font-mono">IV Rank</p>
          <p className={`font-mono font-bold text-sm ${IV_STYLE[ivRegime]?.color || 'text-brand-text'}`}>
            {ivData.iv_rank != null ? `${ivData.iv_rank}` : '--'}
          </p>
          <p className="text-brand-muted text-xs">{ivRegime.replace('_IV', '')}</p>
        </div>
      </div>

      {/* Option details */}
      {signal?.option && (
        <div className="bg-brand-surface rounded-xl p-3 space-y-2">
          <p className="text-brand-muted text-xs font-mono uppercase tracking-widest">
            {signal.strike_type || 'ATM'} Option — {signal.option.expiry}
          </p>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div><p className="text-brand-muted text-xs">Strike</p><p className="font-mono font-bold text-sm">₹{signal.option.strike}</p></div>
            <div><p className="text-brand-muted text-xs">LTP</p><p className="font-mono font-bold text-sm text-brand-accent">₹{signal.option.ltp}</p></div>
            <div><p className="text-brand-muted text-xs">IV</p><p className="font-mono font-bold text-sm">{((signal.option.iv || 0) * 100).toFixed(0)}%</p></div>
          </div>
          <div className="grid grid-cols-3 gap-2 pt-1 border-t border-brand-border">
            <div className="text-center">
              <p className="text-brand-muted text-xs">SL (-{signal.sl_pct}%)</p>
              <p className="font-mono font-bold text-sm text-brand-red">₹{signal.sl_price || signal.option.ltp * (1 - signal.sl_pct/100)}</p>
            </div>
            <div className="text-center">
              <p className="text-brand-muted text-xs">T1 (1:1)</p>
              <p className="font-mono font-bold text-sm text-brand-yellow">₹{signal.partial_target?.toFixed(1)}</p>
            </div>
            <div className="text-center">
              <p className="text-brand-muted text-xs">T2 (+{signal.target_pct}%)</p>
              <p className="font-mono font-bold text-sm text-brand-green">₹{signal.target_price || signal.option.ltp * (1 + signal.target_pct/100)}</p>
            </div>
          </div>
          {/* Risk:Reward display */}
          <div className="flex items-center justify-between text-xs font-mono pt-1 border-t border-brand-border">
            <span className="text-brand-muted">Risk:Reward</span>
            <div className="flex items-center gap-1">
              <Shield size={11} className="text-brand-green"/>
              <span className="text-brand-green font-bold">1:{(signal.target_pct / signal.sl_pct).toFixed(1)}</span>
            </div>
          </div>
        </div>
      )}

      {/* Analysis reasons */}
      {signal?.reasons?.length > 0 && (
        <div className="space-y-1">
          <p className="text-brand-muted text-xs font-mono uppercase tracking-widest">Analysis</p>
          <div className="max-h-48 overflow-y-auto space-y-1 pr-1">
            {signal.reasons.map((r: string, i: number) => {
              const isPos = r.includes('✅') || r.includes('🚀') || r.includes('🔥') || r.includes('📈');
              const isNeg = r.includes('🚫') || r.includes('⚠️') || r.includes('❌');
              return (
                <div key={i} className="flex items-start gap-1.5 text-xs">
                  {isPos ? <CheckCircle size={11} className="text-brand-green mt-0.5 flex-shrink-0"/>
                   : isNeg ? <XCircle size={11} className="text-brand-red mt-0.5 flex-shrink-0"/>
                   : <div className="w-2.5 h-2.5 rounded-full border border-brand-border mt-0.5 flex-shrink-0"/>}
                  <span className={`font-mono leading-relaxed ${isPos ? 'text-brand-green/80' : isNeg ? 'text-brand-red/80' : 'text-brand-muted'}`}>{r}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
