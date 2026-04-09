'use client';
import { useState } from 'react';
import {
  Play, Square, AlertOctagon, Settings, SlidersHorizontal,
  ChevronDown, ChevronUp, Moon, Pause, RotateCcw, Calendar,
} from 'lucide-react';
import { api } from '@/utils/api';

const SYMBOLS    = ['NIFTY', 'BANKNIFTY', 'SENSEX', 'RELIANCE', 'TCS', 'INFY'];
const FILTERS    = [
  { key: 'use_adx_filter',    label: 'ADX Filter',    desc: 'Block ADX<20 sideways markets' },
  { key: 'use_iv_filter',     label: 'IV Filter',     desc: 'Block high-IV option buying' },
  { key: 'use_time_filter',   label: 'Time Filter',   desc: 'Skip first/last 15min' },
  { key: 'use_mtf',           label: 'Multi-TF',      desc: '15min bias confirmation' },
  { key: 'use_volume_filter', label: 'Volume Filter', desc: 'Require above-avg volume' },
  { key: 'use_spike_filter',  label: 'Spike Filter',  desc: 'Reject fake spike candles' },
];

interface Props {
  botStatus:       any;
  onStart:         (s: string, c: number, m: string) => Promise<void>;
  onStop:          () => Promise<void>;
  onEmergencyStop: () => Promise<void>;
  onConfigChange:  () => void;
}

export default function BotControls({ botStatus, onStart, onStop, onEmergencyStop, onConfigChange }: Props) {
  const [loading, setLoading]         = useState(false);
  const [panel, setPanel]             = useState<'none'|'config'|'filters'|'btst'|'events'>('none');
  const [symbol, setSymbol]           = useState('NIFTY');
  const [capital, setCapital]         = useState('100000');
  const [mode, setMode]               = useState<'paper'|'live'>('paper');
  const [riskPct, setRiskPct]         = useState('1.5');
  const [maxTrades, setMaxTrades]     = useState('5');
  const [minScore, setMinScore]       = useState('5');
  const [dailyCap, setDailyCap]       = useState('3');
  const [slippage, setSlippage]       = useState('0.5');
  const [eventDate, setEventDate]     = useState('');
  const [eventReason, setEventReason] = useState('');
  const [saving, setSaving]           = useState(false);

  const running  = botStatus?.is_running;
  const halted   = botStatus?.trading_halted_today;
  const filters  = botStatus?.filters || {};
  const btstOn   = botStatus?.btst_enabled;

  const toggle = (p: typeof panel) => setPanel(prev => prev === p ? 'none' : p);

  const handleStart = async () => {
    setLoading(true);
    try {
      await api.updateBotConfig({
        risk_pct: parseFloat(riskPct), max_daily_trades: parseInt(maxTrades),
        min_score: parseInt(minScore),  daily_loss_cap: parseFloat(dailyCap),
        slippage_pct: parseFloat(slippage),
      });
      await onStart(symbol, parseFloat(capital), mode);
    } finally { setLoading(false); }
  };

  const handleStop = async () => {
    setLoading(true);
    try { await onStop(); } finally { setLoading(false); }
  };

  const toggleFilter = async (key: string) => {
    const curr = filters[key] !== false;
    await api.updateFilters({ [key]: !curr });
    onConfigChange();
  };

  const toggleBTST = async () => {
    await api.updateBotConfig({ btst_enabled: !btstOn });
    onConfigChange();
  };

  const handleHalt = async () => {
    if (!halted) { await api.haltTrading(); } else { await api.resumeTrading(); }
    onConfigChange();
  };

  const saveConfig = async () => {
    setSaving(true);
    try {
      await api.updateBotConfig({
        risk_pct: parseFloat(riskPct), max_daily_trades: parseInt(maxTrades),
        min_score: parseInt(minScore),  daily_loss_cap: parseFloat(dailyCap),
        slippage_pct: parseFloat(slippage),
      });
      onConfigChange();
    } finally { setSaving(false); }
  };

  const addEvent = async () => {
    if (!eventDate || !eventReason) return;
    await api.addBlockedDate(eventDate, eventReason);
    setEventDate(''); setEventReason('');
    onConfigChange();
  };

  const PanelBtn = ({ id, icon: Icon, label, color = '' }: any) => (
    <button
      onClick={() => toggle(id)}
      className={`flex items-center gap-1 text-xs px-2 py-1 rounded-lg transition-all
        ${panel === id
          ? `${color || 'text-brand-accent bg-brand-accent/10'}`
          : 'text-brand-muted hover:text-brand-text hover:bg-brand-border/30'}`}
    >
      <Icon size={11} />{label}
      {panel === id ? <ChevronUp size={9} /> : <ChevronDown size={9} />}
    </button>
  );

  return (
    <div className="bg-brand-card card-glow rounded-2xl p-4 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="font-display font-bold text-sm">Bot Control v3</h2>
        <div className="flex flex-wrap gap-1 justify-end">
          {!running && <PanelBtn id="config"  icon={Settings}        label="Config" />}
          <PanelBtn id="filters" icon={SlidersHorizontal} label="Filters" />
          <PanelBtn id="btst"    icon={Moon}               label="BTST" color="text-brand-yellow bg-brand-yellow/10" />
          <PanelBtn id="events"  icon={Calendar}            label="Events" color="text-brand-red bg-brand-red/10" />
        </div>
      </div>

      {/* ── CONFIG PANEL ── */}
      {panel === 'config' && !running && (
        <div className="bg-brand-surface rounded-xl p-3 space-y-3 animate-slide-up">
          {/* Symbol */}
          <div>
            <label className="text-brand-muted text-xs font-mono mb-1.5 block">SYMBOL</label>
            <div className="flex flex-wrap gap-1.5">
              {SYMBOLS.map(s => (
                <button key={s} onClick={() => setSymbol(s)}
                  className={`px-2.5 py-1 rounded-lg text-xs font-mono border transition-all ${
                    symbol === s ? 'bg-brand-accent/20 border-brand-accent text-brand-accent' : 'border-brand-border text-brand-muted'
                  }`}>{s}</button>
              ))}
            </div>
          </div>

          {/* Capital */}
          <div>
            <label className="text-brand-muted text-xs font-mono mb-1 block">TODAY'S CAPITAL (₹)</label>
            <input type="number" value={capital} onChange={e => setCapital(e.target.value)}
              className="w-full bg-brand-card border border-brand-border rounded-lg px-3 py-2 font-mono text-sm focus:outline-none focus:border-brand-accent"
              min="10000" step="10000" />
          </div>

          {/* 2×3 risk grid */}
          <div className="grid grid-cols-2 gap-2">
            {[
              { label: 'RISK % / TRADE', val: riskPct, set: setRiskPct, min: '0.5', max: '3',   step: '0.5', unit: '%' },
              { label: 'DAILY LOSS CAP', val: dailyCap, set: setDailyCap, min: '1',   max: '10',  step: '0.5', unit: '%' },
              { label: 'MAX TRADES/DAY', val: maxTrades, set: setMaxTrades, min: '1', max: '20',  step: '1',   unit: '' },
              { label: 'MIN SCORE (≤12)', val: minScore, set: setMinScore, min: '3',  max: '10',  step: '1',   unit: '' },
              { label: 'SLIPPAGE %',      val: slippage, set: setSlippage, min: '0',  max: '2',   step: '0.1', unit: '%' },
            ].map(f => (
              <div key={f.label}>
                <label className="text-brand-muted text-xs font-mono mb-1 block">{f.label}</label>
                <div className="relative">
                  <input type="number" value={f.val} onChange={e => f.set(e.target.value)}
                    className="w-full bg-brand-card border border-brand-border rounded-lg px-3 py-2 pr-6 font-mono text-sm focus:outline-none focus:border-brand-accent"
                    min={f.min} max={f.max} step={f.step} />
                  {f.unit && <span className="absolute right-2 top-2 text-brand-muted text-xs font-mono">{f.unit}</span>}
                </div>
              </div>
            ))}
          </div>

          {/* Mode */}
          <div>
            <label className="text-brand-muted text-xs font-mono mb-1 block">MODE</label>
            <div className="flex rounded-lg overflow-hidden border border-brand-border">
              {(['paper', 'live'] as const).map(m => (
                <button key={m} onClick={() => setMode(m)}
                  className={`flex-1 py-2 text-xs font-mono font-bold transition-all ${
                    mode === m ? (m === 'paper' ? 'bg-brand-accent/20 text-brand-accent' : 'bg-brand-red/20 text-brand-red') : 'text-brand-muted'
                  }`}>{m.toUpperCase()}</button>
              ))}
            </div>
            {mode === 'live' && (
              <p className="text-brand-red text-xs mt-1 font-mono">⚠ Set BROKER_API_KEY + BROKER_TOTP_SECRET in .env</p>
            )}
          </div>
        </div>
      )}

      {/* ── FILTERS PANEL ── */}
      {panel === 'filters' && (
        <div className="bg-brand-surface rounded-xl p-3 space-y-2 animate-slide-up">
          <div className="flex items-center justify-between mb-1">
            <p className="text-brand-muted text-xs font-mono uppercase tracking-wider">Strategy Filters</p>
            {running && <span className="text-brand-green text-xs font-mono">● Live</span>}
          </div>
          {FILTERS.map(f => {
            const active = filters[f.key] !== false;
            return (
              <div key={f.key} onClick={() => toggleFilter(f.key)}
                className="flex items-center justify-between py-2 px-1 cursor-pointer rounded-lg hover:bg-brand-border/20 transition-all">
                <div className="flex-1">
                  <p className="text-xs font-mono font-semibold">{f.label}</p>
                  <p className="text-xs text-brand-muted">{f.desc}</p>
                </div>
                <div className={`w-10 h-5 rounded-full transition-all relative flex-shrink-0 ${active ? 'bg-brand-green' : 'bg-brand-border'}`}>
                  <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all ${active ? 'right-0.5' : 'left-0.5'}`} />
                </div>
              </div>
            );
          })}
          {/* Score slider */}
          <div className="pt-2 border-t border-brand-border">
            <div className="flex justify-between text-xs font-mono mb-1">
              <span className="text-brand-muted">Min Score</span>
              <span className="text-brand-accent font-bold">{botStatus?.min_score || 5}/12</span>
            </div>
            <input type="range" min="3" max="10" step="1"
              value={botStatus?.min_score || 5}
              onChange={async e => {
                setMinScore(e.target.value);
                if (running) { await api.updateBotConfig({ min_score: parseInt(e.target.value) }); onConfigChange(); }
              }}
              className="w-full accent-brand-accent" />
            <div className="flex justify-between text-xs text-brand-muted font-mono">
              <span>3 (frequent)</span><span>10 (elite only)</span>
            </div>
          </div>
        </div>
      )}

      {/* ── BTST PANEL ── */}
      {panel === 'btst' && (
        <div className="bg-brand-surface rounded-xl p-3 space-y-3 animate-slide-up">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-mono font-bold text-brand-yellow">🌙 BTST Module</p>
              <p className="text-xs text-brand-muted mt-0.5">Buy Today Sell Tomorrow overnight strategy</p>
            </div>
            <div onClick={toggleBTST}
              className={`w-12 h-6 rounded-full cursor-pointer transition-all relative ${btstOn ? 'bg-brand-yellow' : 'bg-brand-border'}`}>
              <div className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-all ${btstOn ? 'right-1' : 'left-1'}`} />
            </div>
          </div>
          {btstOn && (
            <div className="space-y-1.5 text-xs font-mono text-brand-muted">
              <div className="bg-brand-card rounded-lg p-2 space-y-1">
                <p className="text-brand-text font-semibold">Entry: 14:45–15:10 IST</p>
                <p>• ADX ≥ 25 (strong trend required)</p>
                <p>• Confirmed 15min breakout</p>
                <p>• Volume above avg + RSI 25–72</p>
                <p>• IVR &lt; 60 (no expensive premium)</p>
                <p>• Skips expiry days + event days</p>
              </div>
              <div className="bg-brand-card rounded-lg p-2 space-y-1">
                <p className="text-brand-text font-semibold">Exit: 09:20 IST next day</p>
                <p>• OR +40% gap profit → early exit</p>
                <p>• OR SL hit (30% on premium)</p>
                <p>• Risk: 1% of capital max</p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── EVENTS PANEL ── */}
      {panel === 'events' && (
        <div className="bg-brand-surface rounded-xl p-3 space-y-3 animate-slide-up">
          <p className="text-xs font-mono text-brand-muted uppercase tracking-wider">Block Trading on Event Days</p>
          <div className="space-y-2">
            <input type="date" value={eventDate} onChange={e => setEventDate(e.target.value)}
              className="w-full bg-brand-card border border-brand-border rounded-lg px-3 py-2 font-mono text-sm focus:outline-none focus:border-brand-red text-brand-text" />
            <input type="text" placeholder="Reason (e.g. RBI Policy)" value={eventReason}
              onChange={e => setEventReason(e.target.value)}
              className="w-full bg-brand-card border border-brand-border rounded-lg px-3 py-2 font-mono text-sm focus:outline-none focus:border-brand-red text-brand-text placeholder:text-brand-muted" />
            <button onClick={addEvent} disabled={!eventDate || !eventReason}
              className="w-full py-2 bg-brand-red/20 border border-brand-red/40 text-brand-red font-mono text-xs font-bold rounded-lg hover:bg-brand-red/30 transition-all disabled:opacity-40">
              + Block This Date
            </button>
          </div>
          <p className="text-brand-muted text-xs font-mono">
            Blocked dates prevent ALL trades (intraday + BTST) on that day.
          </p>
        </div>
      )}

      {/* ── ACTION BUTTONS ── */}
      <div className="space-y-2">
        {!running ? (
          <button onClick={handleStart} disabled={loading}
            className="w-full flex items-center justify-center gap-2 bg-brand-green text-brand-bg font-bold py-3 rounded-xl text-sm hover:opacity-90 active:scale-95 disabled:opacity-50 transition-all">
            {loading
              ? <div className="w-4 h-4 border-2 border-brand-bg border-t-transparent rounded-full animate-spin" />
              : <Play size={16} fill="currentColor" />}
            Start Bot v3
          </button>
        ) : (
          <div className="space-y-2">
            <div className="flex gap-2">
              <button onClick={handleStop} disabled={loading}
                className="flex-1 flex items-center justify-center gap-2 bg-brand-surface border border-brand-border text-brand-text font-bold py-3 rounded-xl text-sm hover:border-brand-muted active:scale-95 transition-all">
                <Square size={14} fill="currentColor" /> Stop
              </button>
              <button onClick={handleHalt}
                className={`flex items-center justify-center gap-1.5 font-bold px-3 py-3 rounded-xl text-xs border transition-all ${
                  halted
                    ? 'bg-brand-green/10 border-brand-green/40 text-brand-green hover:bg-brand-green/20'
                    : 'bg-brand-yellow/10 border-brand-yellow/40 text-brand-yellow hover:bg-brand-yellow/20'
                }`}>
                {halted ? <><RotateCcw size={12} />Resume</> : <><Pause size={12} />Halt</>}
              </button>
              <button onClick={onEmergencyStop}
                className="flex items-center justify-center gap-1.5 bg-brand-red/10 border border-brand-red/40 text-brand-red font-bold px-3 py-3 rounded-xl text-xs hover:bg-brand-red/20 active:scale-95 transition-all">
                <AlertOctagon size={12} /> E-Stop
              </button>
            </div>
            <div className={`flex items-center gap-2 rounded-xl px-3 py-2 border ${
              halted
                ? 'bg-brand-yellow/5 border-brand-yellow/20'
                : 'bg-brand-green/5 border-brand-green/20'
            }`}>
              <div className={halted ? 'dot-stopped' : 'dot-live'} />
              <span className={`text-xs font-mono ${halted ? 'text-brand-yellow' : 'text-brand-green'}`}>
                {halted ? 'HALTED — no new trades' : `${botStatus?.symbol} | ${botStatus?.mode?.toUpperCase()} | Score≥${botStatus?.min_score} | Risk ${botStatus?.risk_pct?.toFixed(1)}%`}
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
