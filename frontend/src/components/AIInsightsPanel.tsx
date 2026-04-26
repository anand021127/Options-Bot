'use client';
import { useState, useEffect, useCallback } from 'react';
import {
  Brain, CheckCircle, XCircle, AlertTriangle, RefreshCw, Zap,
  TrendingUp, TrendingDown, Minus, Activity, Target, Shield, BarChart3,
} from 'lucide-react';
import { api } from '@/utils/api';

interface MarketAnalysis {
  market_outlook: string;
  confidence: number;
  analysis: string;
  key_levels: string;
  recommended_strategies: string[];
  risk_warnings: string;
  source: string;
  timestamp: string;
  symbol?: string;
}

export default function AIInsightsPanel() {
  const [status, setStatus]       = useState<any>(null);
  const [history, setHistory]     = useState<any[]>([]);
  const [analysis, setAnalysis]   = useState<MarketAnalysis | null>(null);
  const [loading, setLoading]     = useState(true);
  const [analyzing, setAnalyzing] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [s, h] = await Promise.allSettled([api.getAIStatus(), api.getAIHistory(15)]);
      if (s.status === 'fulfilled') {
        setStatus(s.value);
        // Use cached analysis from status if available
        if (s.value?.last_analysis) setAnalysis(s.value.last_analysis);
      }
      if (h.status === 'fulfilled') setHistory(h.value || []);
    } catch {} finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchData(); const iv = setInterval(fetchData, 15000); return () => clearInterval(iv); }, [fetchData]);

  const handleToggle = async () => {
    try {
      const r = await api.toggleAI();
      setStatus((p: any) => ({ ...p, enabled: r.ai_enabled, ready: r.ai_enabled && p?.has_key }));
    } catch {}
  };

  const handleAnalyze = async () => {
    setAnalyzing(true);
    try {
      const result = await api.getAIAnalysis('NIFTY');
      if (result) setAnalysis(result);
    } catch {} finally { setAnalyzing(false); }
  };

  const getOutlookIcon = (outlook: string) => {
    switch (outlook) {
      case 'BULLISH':  return <TrendingUp  size={14} className="text-brand-green" />;
      case 'BEARISH':  return <TrendingDown size={14} className="text-brand-red" />;
      case 'CHOPPY':   return <Activity     size={14} className="text-brand-yellow" />;
      default:         return <Minus        size={14} className="text-brand-muted" />;
    }
  };

  const getOutlookColor = (outlook: string) => {
    switch (outlook) {
      case 'BULLISH':  return 'text-brand-green';
      case 'BEARISH':  return 'text-brand-red';
      case 'CHOPPY':   return 'text-brand-yellow';
      default:         return 'text-brand-muted';
    }
  };

  const getOutlookBg = (outlook: string) => {
    switch (outlook) {
      case 'BULLISH':  return 'bg-brand-green/10 border-brand-green/20';
      case 'BEARISH':  return 'bg-brand-red/10 border-brand-red/20';
      case 'CHOPPY':   return 'bg-brand-yellow/10 border-brand-yellow/20';
      default:         return 'bg-brand-surface border-brand-border';
    }
  };

  const getConfidenceColor = (conf: number) => {
    if (conf >= 70) return 'text-brand-green';
    if (conf >= 40) return 'text-brand-yellow';
    return 'text-brand-red';
  };

  if (loading) return (
    <div className="bg-brand-card card-glow rounded-2xl p-4 animate-pulse">
      <div className="h-4 bg-brand-border rounded w-1/3 mb-3" />
      <div className="h-20 bg-brand-border rounded" />
    </div>
  );

  return (
    <div className="space-y-4 animate-slide-up">
      {/* Status Card */}
      <div className="bg-brand-card card-glow rounded-2xl p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Brain size={16} className="text-purple-400" />
            <div>
              <p className="font-display font-bold text-sm">AI Advisor</p>
              <p className="text-brand-muted text-xs font-mono">Gemini-powered market analysis & signal validation</p>
            </div>
          </div>
          <button onClick={handleToggle}
            className={`relative w-14 h-7 rounded-full transition-all duration-300 border-2 focus:outline-none ${
              status?.enabled ? 'bg-purple-500 border-purple-500' : 'bg-brand-border border-brand-border'
            }`}>
            <div className={`absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-all duration-300 ${
              status?.enabled ? 'right-0.5' : 'left-0.5'
            }`} />
          </button>
        </div>

        <div className="grid grid-cols-3 gap-2">
          {[
            { label: 'Status',  value: status?.ready ? 'READY' : status?.enabled ? 'NO KEY' : 'OFF',
              ok: status?.ready, icon: status?.ready ? <Zap size={10}/> : <AlertTriangle size={10}/> },
            { label: 'Cache',   value: `${status?.cache_size || 0} entries`, ok: true },
            { label: 'Verdicts', value: `${status?.history_count || 0} total`, ok: true },
          ].map((item, i) => (
            <div key={i} className="bg-brand-surface rounded-xl p-2 text-center">
              <p className="text-brand-muted text-xs font-mono">{item.label}</p>
              <p className={`text-xs font-mono font-bold mt-0.5 ${item.ok ? 'text-purple-400' : 'text-brand-muted'}`}>
                {item.value}
              </p>
            </div>
          ))}
        </div>

        {!status?.has_key && status?.enabled && (
          <div className="mt-3 bg-brand-yellow/10 border border-brand-yellow/30 rounded-xl p-2.5 text-xs font-mono text-brand-yellow">
            <AlertTriangle size={11} className="inline mr-1" />
            Set GEMINI_API_KEY in your .env file to enable AI analysis
          </div>
        )}
      </div>

      {/* Market Analysis Card — Proactive AI */}
      <div className="bg-brand-card card-glow rounded-2xl p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <BarChart3 size={14} className="text-purple-400" />
            <p className="font-display font-bold text-sm">Market Analysis</p>
          </div>
          <button onClick={handleAnalyze} disabled={analyzing || !status?.ready}
            className={`flex items-center gap-1 text-xs font-mono px-2.5 py-1 rounded-lg transition-all ${
              analyzing ? 'bg-purple-500/20 text-purple-400' :
              status?.ready ? 'bg-brand-surface text-brand-muted hover:text-purple-400 hover:bg-purple-500/10' :
              'bg-brand-surface text-brand-muted/30 cursor-not-allowed'
            }`}>
            <RefreshCw size={10} className={analyzing ? 'animate-spin' : ''} />
            {analyzing ? 'Analyzing...' : 'Analyze Now'}
          </button>
        </div>

        {analysis && analysis.source !== 'fallback' ? (
          <div className="space-y-3">
            {/* Outlook Badge */}
            <div className={`rounded-xl border p-3 ${getOutlookBg(analysis.market_outlook)}`}>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  {getOutlookIcon(analysis.market_outlook)}
                  <span className={`text-sm font-display font-bold ${getOutlookColor(analysis.market_outlook)}`}>
                    {analysis.market_outlook}
                  </span>
                  {analysis.symbol && (
                    <span className="text-brand-muted text-xs font-mono">{analysis.symbol}</span>
                  )}
                </div>
                <div className="flex items-center gap-1.5">
                  <span className={`text-xs font-mono font-bold ${getConfidenceColor(analysis.confidence)}`}>
                    {analysis.confidence}%
                  </span>
                  <span className="text-brand-muted/50 text-xs font-mono">conf</span>
                </div>
              </div>
              <p className="text-brand-text text-xs font-mono leading-relaxed">
                {analysis.analysis}
              </p>
            </div>

            {/* Key Levels & Strategies */}
            <div className="grid grid-cols-2 gap-2">
              {analysis.key_levels && (
                <div className="bg-brand-surface rounded-xl p-2.5">
                  <div className="flex items-center gap-1 mb-1">
                    <Target size={10} className="text-purple-400" />
                    <span className="text-brand-muted text-xs font-mono">Key Levels</span>
                  </div>
                  <p className="text-brand-text text-xs font-mono leading-relaxed">
                    {analysis.key_levels}
                  </p>
                </div>
              )}
              {analysis.recommended_strategies?.length > 0 && (
                <div className="bg-brand-surface rounded-xl p-2.5">
                  <div className="flex items-center gap-1 mb-1.5">
                    <Zap size={10} className="text-purple-400" />
                    <span className="text-brand-muted text-xs font-mono">Strategies</span>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {analysis.recommended_strategies.map((s, i) => (
                      <span key={i} className="text-xs font-mono bg-purple-500/15 text-purple-300 px-1.5 py-0.5 rounded">
                        {s}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Risk Warnings */}
            {analysis.risk_warnings && (
              <div className="bg-brand-red/5 border border-brand-red/15 rounded-xl p-2.5">
                <div className="flex items-center gap-1 mb-1">
                  <Shield size={10} className="text-brand-red" />
                  <span className="text-brand-red text-xs font-mono font-bold">Risk Warning</span>
                </div>
                <p className="text-brand-muted text-xs font-mono">{analysis.risk_warnings}</p>
              </div>
            )}

            {/* Timestamp */}
            <p className="text-brand-muted/40 text-xs font-mono text-right">
              {analysis.timestamp ? new Date(analysis.timestamp).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) : ''} · {analysis.source}
            </p>
          </div>
        ) : (
          <div className="text-center py-4">
            <Brain size={24} className="text-purple-400 mx-auto mb-2 opacity-30" />
            <p className="text-brand-muted text-xs font-mono">
              {status?.ready
                ? 'Click "Analyze Now" or wait for automatic analysis during market hours'
                : 'Enable AI and set GEMINI_API_KEY to use market analysis'}
            </p>
          </div>
        )}
      </div>

      {/* Recent Verdicts */}
      {history.length > 0 && (
        <div className="bg-brand-card card-glow rounded-2xl p-4">
          <div className="flex items-center justify-between mb-3">
            <p className="font-display font-bold text-sm">Recent AI Activity</p>
            <button onClick={fetchData} className="text-brand-muted hover:text-purple-400 transition-all">
              <RefreshCw size={12} />
            </button>
          </div>
          <div className="space-y-2">
            {history.slice(0, 10).map((v: any, i: number) => (
              <div key={i} className={`bg-brand-surface rounded-xl p-3 border ${
                v.type === 'analysis'
                  ? 'border-purple-500/20'
                  : v.approved
                    ? 'border-brand-green/20'
                    : 'border-brand-yellow/30'
              }`}>
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-1.5">
                    {v.type === 'analysis'
                      ? <BarChart3 size={12} className="text-purple-400" />
                      : v.approved
                        ? <CheckCircle size={12} className="text-brand-green" />
                        : <AlertTriangle size={12} className="text-brand-yellow" />}
                    <span className={`text-xs font-mono font-bold ${
                      v.type === 'analysis' ? 'text-purple-400' :
                      v.approved ? 'text-brand-green' : 'text-brand-yellow'
                    }`}>
                      {v.type === 'analysis' ? 'ANALYSIS' : v.approved ? 'APPROVED' : 'CAUTION'}
                    </span>
                    <span className="text-brand-muted text-xs font-mono">
                      {v.signal_type} {v.symbol}
                    </span>
                  </div>
                  <div className="flex items-center gap-1">
                    <span className={`text-xs font-mono font-bold ${getConfidenceColor(v.confidence || 0)}`}>
                      {v.confidence}%
                    </span>
                    <span className="text-brand-muted text-xs font-mono">
                      {v.source === 'cache' ? '(cached)' : v.latency_ms ? `${v.latency_ms}ms` : ''}
                    </span>
                  </div>
                </div>
                <p className="text-brand-text text-xs font-mono">{v.reasoning}</p>
                {v.risk_notes && (
                  <p className="text-brand-muted text-xs font-mono mt-0.5">⚠️ {v.risk_notes}</p>
                )}
                <p className="text-brand-muted/50 text-xs font-mono mt-1">
                  {v.timestamp ? new Date(v.timestamp).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) : ''}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {history.length === 0 && !analysis && status?.ready && (
        <div className="bg-brand-card card-glow rounded-2xl p-4 text-center">
          <Brain size={24} className="text-purple-400 mx-auto mb-2 opacity-50" />
          <p className="text-brand-muted text-xs font-mono">
            No AI activity yet. Start the bot and AI will analyze the market automatically during trading hours.
          </p>
        </div>
      )}
    </div>
  );
}
