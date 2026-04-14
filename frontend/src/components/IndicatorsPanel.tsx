'use client';
import { RefreshCw, ArrowUpCircle, ArrowDownCircle, MinusCircle, Zap } from 'lucide-react';

const REGIME_COLOR: Record<string, string> = {
  TRENDING:   'text-brand-green bg-brand-green/10 border-brand-green/30',
  SIDEWAYS:   'text-brand-yellow bg-brand-yellow/10 border-brand-yellow/30',
  VOLATILE:   'text-brand-red bg-brand-red/10 border-brand-red/30',
  WEAK_TREND: 'text-brand-muted bg-brand-surface border-brand-border',
};

const STRUCT_ICONS: Record<string, any> = {
  BULLISH: ArrowUpCircle,
  BEARISH: ArrowDownCircle,
  SIDEWAYS: MinusCircle,
};

export default function IndicatorsPanel({ indicators, onRefresh, symbol }: any) {
  const iv    = indicators?.iv_rank || {};
  const sr    = indicators?.sr || indicators;
  const adx   = indicators?.adx;
  const pDI   = indicators?.plus_di;
  const mDI   = indicators?.minus_di;
  const regime = indicators?.regime || 'UNKNOWN';
  const struct = indicators?.structure || 'SIDEWAYS';
  const StructIcon = STRUCT_ICONS[struct] || MinusCircle;

  return (
    <div className="bg-brand-card card-glow rounded-2xl p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="font-display font-bold text-sm">Indicators v3</h2>
        <button onClick={onRefresh}
          className="p-1.5 rounded-lg text-brand-muted hover:text-brand-accent hover:bg-brand-accent/10 transition-all">
          <RefreshCw size={13} />
        </button>
      </div>

      {!indicators ? (
        <div className="py-6 text-center">
          <button onClick={onRefresh} className="text-brand-accent text-xs font-mono hover:underline">
            Load indicators for {symbol}
          </button>
        </div>
      ) : (
        <div className="space-y-2">
          {/* EMA trend */}
          <div className="bg-brand-surface rounded-xl p-3">
            <p className="text-brand-muted text-xs font-mono uppercase tracking-wider mb-2">EMA Trend</p>
            <div className="grid grid-cols-3 gap-2 font-mono text-xs text-center mb-2">
              {[
                { k: 'Price',  v: indicators.close, color: '' },
                { k: 'EMA 9',  v: indicators.ema9,  color: indicators.close > indicators.ema9 ? 'text-brand-green' : 'text-brand-red' },
                { k: 'EMA 20', v: indicators.ema20, color: indicators.close > indicators.ema20 ? 'text-brand-green' : 'text-brand-red' },
                { k: 'EMA 50', v: indicators.ema50, color: indicators.close > indicators.ema50 ? 'text-brand-green' : 'text-brand-red' },
                { k: 'VWAP',   v: indicators.vwap,  color: indicators.close > indicators.vwap ? 'text-brand-green' : 'text-brand-red' },
                { k: 'ATR',    v: indicators.atr,   color: 'text-brand-text' },
              ].map(({ k, v, color }) => (
                <div key={k}>
                  <p className="text-brand-muted">{k}</p>
                  <p className={`font-bold ${color}`}>₹{typeof v === 'number' ? v.toFixed(0) : '--'}</p>
                </div>
              ))}
            </div>
            <div className="flex justify-between text-xs font-mono border-t border-brand-border pt-2">
              <span className="text-brand-muted">VWAP bias</span>
              <span className={`font-bold ${indicators.close > indicators.vwap ? 'text-brand-green' : 'text-brand-red'}`}>
                {indicators.close > indicators.vwap ? '↑ Bullish' : '↓ Bearish'}
              </span>
            </div>
          </div>

          {/* ADX panel */}
          {adx !== undefined && (
            <div className="bg-brand-surface rounded-xl p-3">
              <p className="text-brand-muted text-xs font-mono uppercase tracking-wider mb-2">ADX Trend Strength</p>
              <div className="grid grid-cols-3 gap-2 text-center font-mono text-xs">
                <div>
                  <p className="text-brand-muted">ADX</p>
                  <p className={`font-bold text-sm ${adx >= 25 ? 'text-brand-green' : adx >= 20 ? 'text-brand-yellow' : 'text-brand-red'}`}>
                    {adx?.toFixed(0)}
                  </p>
                </div>
                <div>
                  <p className="text-brand-muted">+DI</p>
                  <p className={`font-bold text-sm ${pDI > mDI ? 'text-brand-green' : 'text-brand-muted'}`}>{pDI?.toFixed(0)}</p>
                </div>
                <div>
                  <p className="text-brand-muted">-DI</p>
                  <p className={`font-bold text-sm ${mDI > pDI ? 'text-brand-red' : 'text-brand-muted'}`}>{mDI?.toFixed(0)}</p>
                </div>
              </div>
              <div className="mt-2 h-1.5 bg-brand-border rounded-full overflow-hidden">
                <div className={`h-full rounded-full ${adx >= 25 ? 'bg-brand-green' : adx >= 20 ? 'bg-brand-yellow' : 'bg-brand-red'}`}
                     style={{ width: `${Math.min((adx / 50) * 100, 100)}%` }} />
              </div>
              <div className="flex justify-between text-xs font-mono text-brand-muted mt-0.5">
                <span>0 (flat)</span><span>25 (trend)</span><span>50+ (strong)</span>
              </div>
            </div>
          )}

          {/* RSI */}
          <div className="bg-brand-surface rounded-xl p-3">
            <div className="flex justify-between items-center font-mono text-xs mb-2">
              <span className="text-brand-muted">RSI (14)</span>
              <span className={`font-bold ${
                indicators.rsi > 70 ? 'text-brand-red'
                : indicators.rsi < 30 ? 'text-brand-green'
                : 'text-brand-yellow'
              }`}>{indicators.rsi?.toFixed(1)}</span>
            </div>
            <div className="h-2 bg-brand-border rounded-full overflow-hidden">
              <div className={`h-full rounded-full ${
                indicators.rsi > 70 ? 'bg-brand-red'
                : indicators.rsi < 30 ? 'bg-brand-green' : 'bg-brand-yellow'
              }`} style={{ width: `${Math.min(indicators.rsi, 100)}%` }} />
            </div>
            <div className="flex justify-between text-xs text-brand-muted font-mono mt-0.5">
              <span>Oversold 30</span><span>Overbought 70</span>
            </div>
          </div>

          {/* Structure + S/R + Regime */}
          <div className="bg-brand-surface rounded-xl p-3 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-brand-muted text-xs font-mono">Structure</span>
              <div className="flex items-center gap-1">
                <StructIcon size={12} className={
                  struct === 'BULLISH' ? 'text-brand-green'
                  : struct === 'BEARISH' ? 'text-brand-red' : 'text-brand-yellow'
                } />
                <span className={`text-xs font-mono font-bold px-2 py-0.5 rounded border ${REGIME_COLOR[struct] || REGIME_COLOR.SIDEWAYS}`}>
                  {struct}
                </span>
              </div>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-brand-muted text-xs font-mono">Regime</span>
              <span className={`text-xs font-mono font-bold px-2 py-0.5 rounded border ${REGIME_COLOR[regime] || REGIME_COLOR.SIDEWAYS}`}>
                {regime}
              </span>
            </div>
            {sr?.resistance?.length > 0 && (
              <div className="flex justify-between text-xs font-mono">
                <span className="text-brand-muted">Resistance</span>
                <span className="text-brand-red">{sr.resistance.slice(0,2).map((v: number) => `₹${v}`).join(' · ')}</span>
              </div>
            )}
            {sr?.support?.length > 0 && (
              <div className="flex justify-between text-xs font-mono">
                <span className="text-brand-muted">Support</span>
                <span className="text-brand-green">{sr.support.slice(0,2).map((v: number) => `₹${v}`).join(' · ')}</span>
              </div>
            )}
          </div>

          {/* IV summary */}
          {iv.iv_rank !== undefined && (
            <div className="bg-brand-surface rounded-xl p-3">
              <div className="flex justify-between text-xs font-mono mb-1.5">
                <span className="text-brand-muted">IV Rank Proxy (HV)</span>
                <span className={`font-bold ${
                  iv.iv_rank < 30 ? 'text-brand-green'
                  : iv.iv_rank < 60 ? 'text-brand-text' : 'text-brand-red'
                }`}>{iv.iv_rank} — {iv.regime?.replace('_IV','')}</span>
              </div>
              <div className="grid grid-cols-3 gap-1 text-xs font-mono text-center">
                <div><p className="text-brand-muted">HV Low</p><p>{iv.hv_low}%</p></div>
                <div><p className="text-brand-muted">Current</p><p className="font-bold">{iv.hv_current}%</p></div>
                <div><p className="text-brand-muted">HV High</p><p>{iv.hv_high}%</p></div>
              </div>
            </div>
          )}

          {/* Entry patterns */}
          {(indicators.conf_breakout || indicators.vwap_bounce || indicators.pullback) && (
            <div className="bg-brand-surface rounded-xl p-3 space-y-1.5">
              <p className="text-brand-muted text-xs font-mono uppercase tracking-wider">Entry Patterns</p>
              {indicators.conf_breakout && (
                <div className={`text-xs font-mono font-bold py-1 px-2 rounded ${
                  indicators.conf_breakout.includes('UP')
                    ? 'text-brand-green bg-brand-green/10'
                    : 'text-brand-red bg-brand-red/10'
                }`}>
                  🚀 {indicators.conf_breakout.replace(/_/g, ' ')}
                </div>
              )}
              {indicators.vwap_bounce && (
                <div className={`text-xs font-mono font-bold py-1 px-2 rounded ${
                  indicators.vwap_bounce === 'BOUNCE_BULL'
                    ? 'text-brand-green bg-brand-green/10'
                    : 'text-brand-red bg-brand-red/10'
                }`}>
                  🔥 {indicators.vwap_bounce.replace(/_/g, ' ')}
                </div>
              )}
              {indicators.pullback && (
                <div className={`text-xs font-mono font-bold py-1 px-2 rounded ${
                  indicators.pullback.includes('BULL')
                    ? 'text-brand-green bg-brand-green/10'
                    : 'text-brand-red bg-brand-red/10'
                }`}>
                  📉 {indicators.pullback.replace(/_/g, ' ')}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
