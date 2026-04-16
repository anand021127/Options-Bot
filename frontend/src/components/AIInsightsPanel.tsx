'use client';
import { useState, useEffect } from 'react';
import { Brain, CheckCircle, XCircle, AlertTriangle, ToggleLeft, ToggleRight, RefreshCw, Zap } from 'lucide-react';
import { api } from '@/utils/api';

export default function AIInsightsPanel() {
  const [status,  setStatus]  = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    try {
      const [s, h] = await Promise.allSettled([api.getAIStatus(), api.getAIHistory(15)]);
      if (s.status === 'fulfilled') setStatus(s.value);
      if (h.status === 'fulfilled') setHistory(h.value || []);
    } catch {} finally { setLoading(false); }
  };

  useEffect(() => { fetchData(); const iv = setInterval(fetchData, 15000); return () => clearInterval(iv); }, []);

  const handleToggle = async () => {
    try {
      const r = await api.toggleAI();
      setStatus((p: any) => ({ ...p, enabled: r.ai_enabled, ready: r.ai_enabled && p?.has_key }));
    } catch {}
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
              <p className="text-brand-muted text-xs font-mono">Gemini-powered signal validation</p>
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

      {/* Recent Verdicts */}
      {history.length > 0 && (
        <div className="bg-brand-card card-glow rounded-2xl p-4">
          <div className="flex items-center justify-between mb-3">
            <p className="font-display font-bold text-sm">Recent AI Verdicts</p>
            <button onClick={fetchData} className="text-brand-muted hover:text-purple-400 transition-all">
              <RefreshCw size={12} />
            </button>
          </div>
          <div className="space-y-2">
            {history.slice(0, 10).map((v: any, i: number) => (
              <div key={i} className={`bg-brand-surface rounded-xl p-3 border ${
                v.approved
                  ? 'border-brand-green/20'
                  : 'border-brand-yellow/30'
              }`}>
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-1.5">
                    {v.approved
                      ? <CheckCircle size={12} className="text-brand-green" />
                      : <AlertTriangle size={12} className="text-brand-yellow" />}
                    <span className={`text-xs font-mono font-bold ${
                      v.approved ? 'text-brand-green' : 'text-brand-yellow'
                    }`}>
                      {v.approved ? 'APPROVED' : 'CAUTION'}
                    </span>
                    <span className="text-brand-muted text-xs font-mono">
                      {v.signal_type} {v.symbol}
                    </span>
                  </div>
                  <div className="flex items-center gap-1">
                    <span className={`text-xs font-mono font-bold ${
                      v.confidence >= 70 ? 'text-brand-green' : v.confidence >= 40 ? 'text-brand-yellow' : 'text-brand-red'
                    }`}>
                      {v.confidence}%
                    </span>
                    <span className="text-brand-muted text-xs font-mono">
                      {v.source === 'cache' ? '(cached)' : `${v.latency_ms}ms`}
                    </span>
                  </div>
                </div>
                <p className="text-brand-text text-xs font-mono">{v.reasoning}</p>
                {v.risk_notes && (
                  <p className="text-brand-muted text-xs font-mono mt-0.5">⚠️ {v.risk_notes}</p>
                )}
                <p className="text-brand-muted/50 text-xs font-mono mt-1">
                  {new Date(v.timestamp).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {history.length === 0 && status?.ready && (
        <div className="bg-brand-card card-glow rounded-2xl p-4 text-center">
          <Brain size={24} className="text-purple-400 mx-auto mb-2 opacity-50" />
          <p className="text-brand-muted text-xs font-mono">
            No AI verdicts yet. Start the bot and AI will analyze signals automatically.
          </p>
        </div>
      )}
    </div>
  );
}
