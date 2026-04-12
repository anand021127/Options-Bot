'use client';
import { useEffect, useRef, useState } from 'react';
import { BarChart2 } from 'lucide-react';

// TradingView symbol mapping
const TV_SYMBOLS: Record<string,string> = {
  NIFTY:     'NSE:NIFTY',
  BANKNIFTY: 'NSE:BANKNIFTY',
  SENSEX:    'BSE:SENSEX',
  RELIANCE:  'NSE:RELIANCE',
  TCS:       'NSE:TCS',
  INFY:      'NSE:INFY',
  HDFCBANK:  'NSE:HDFCBANK',
};

export default function MarketChart({ symbol = 'NIFTY' }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!containerRef.current) return;
    containerRef.current.innerHTML = '';
    setLoaded(false);

    const script = document.createElement('script');
    script.src   = 'https://s3.tradingview.com/tv.js';
    script.async = true;
    script.onload = () => {
      if (typeof (window as any).TradingView === 'undefined') return;
      new (window as any).TradingView.widget({
        autosize:         true,
        symbol:           TV_SYMBOLS[symbol] ?? `NSE:${symbol}`,
        interval:         '5',
        timezone:         'Asia/Kolkata',
        theme:            'dark',
        style:            '1',       // Candlestick
        locale:           'en',
        toolbar_bg:       '#111827',
        enable_publishing: false,
        withdateranges:   true,
        hide_side_toolbar: false,
        allow_symbol_change: true,
        container_id:     'tv_chart_container',
        studies:          ['MASimple@tv-basicstudies','VWAP@tv-basicstudies'],
        overrides: {
          'mainSeriesProperties.candleStyle.upColor':       '#00FF88',
          'mainSeriesProperties.candleStyle.downColor':     '#FF3B5C',
          'mainSeriesProperties.candleStyle.borderUpColor': '#00FF88',
          'mainSeriesProperties.candleStyle.borderDownColor':'#FF3B5C',
          'mainSeriesProperties.candleStyle.wickUpColor':   '#00FF88',
          'mainSeriesProperties.candleStyle.wickDownColor': '#FF3B5C',
          'paneProperties.background':                      '#0A0E1A',
          'paneProperties.vertGridProperties.color':        '#1A2235',
          'paneProperties.horzGridProperties.color':        '#1A2235',
        },
      });
      setLoaded(true);
    };

    document.head.appendChild(script);
    return () => {
      try { document.head.removeChild(script); } catch {}
    };
  }, [symbol]);

  return (
    <div className="bg-brand-card card-glow rounded-2xl overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-brand-border">
        <BarChart2 size={14} className="text-brand-accent"/>
        <h2 className="font-display font-bold text-sm">{symbol} Chart</h2>
        <span className="text-brand-muted text-xs font-mono">5m · TradingView</span>
      </div>
      <div style={{ height: 380, position:'relative' }}>
        {!loaded && (
          <div className="absolute inset-0 flex items-center justify-center bg-brand-surface">
            <div className="text-center">
              <div className="w-8 h-8 border-2 border-brand-accent border-t-transparent rounded-full animate-spin mx-auto mb-2"/>
              <p className="text-brand-muted text-xs font-mono">Loading chart...</p>
            </div>
          </div>
        )}
        <div id="tv_chart_container" ref={containerRef} style={{width:'100%',height:'100%'}}/>
      </div>
    </div>
  );
}
