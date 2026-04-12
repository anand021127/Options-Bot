'use client';
import { Wifi, WifiOff, TrendingUp, Bell, Zap, ZapOff } from 'lucide-react';

interface HeaderProps {
  connected:        boolean;   // dashboard WebSocket
  price:            any;
  botRunning:       boolean;
  unreadCount?:     number;
  wsDataConnected?: boolean;   // Upstox market data WebSocket
  onBellClick?:     () => void;
}

export default function Header({
  connected, price, botRunning,
  unreadCount = 0, wsDataConnected = false, onBellClick
}: HeaderProps) {
  const pos = (price?.change_pct ?? 0) >= 0;

  return (
    <header className="bg-brand-surface border-b border-brand-border px-4 py-3 flex items-center justify-between">
      {/* Logo */}
      <div className="flex items-center gap-2">
        <TrendingUp size={18} className="text-brand-accent" />
        <span className="font-display font-bold text-brand-accent text-lg tracking-tight">
          OptionsBot
        </span>
        <span className="text-brand-muted text-xs font-mono bg-brand-border/60 px-1.5 py-0.5 rounded">
          v3.1
        </span>
      </div>

      {/* Right side */}
      <div className="flex items-center gap-3">
        {/* NIFTY live price */}
        {price && (
          <div className="text-right">
            <div className={`font-mono font-semibold text-sm ${pos ? 'text-brand-green' : 'text-brand-red'}`}>
              ₹{price.price?.toLocaleString('en-IN')}
            </div>
            <div className={`text-xs font-mono ${pos ? 'text-brand-green' : 'text-brand-red'}`}>
              {pos ? '+' : ''}{price.change_pct}%
            </div>
          </div>
        )}

        {/* Status indicators column */}
        <div className="flex flex-col items-end gap-1">
          {/* Dashboard WS */}
          <div className="flex items-center gap-1">
            {connected
              ? <Wifi size={11} className="text-brand-green" />
              : <WifiOff size={11} className="text-brand-red" />}
            <span className={`text-xs font-mono ${connected ? 'text-brand-green' : 'text-brand-red'}`}>
              {connected ? 'LIVE' : 'OFF'}
            </span>
          </div>

          {/* Upstox data WS */}
          <div className="flex items-center gap-1">
            {wsDataConnected
              ? <Zap size={10} className="text-brand-yellow" />
              : <ZapOff size={10} className="text-brand-muted" />}
            <span className={`text-xs font-mono ${wsDataConnected ? 'text-brand-yellow' : 'text-brand-muted'}`}>
              {wsDataConnected ? 'RT DATA' : 'DELAYED'}
            </span>
          </div>

          {/* Bot status */}
          <div className="flex items-center gap-1">
            <div className={botRunning ? 'dot-live' : 'dot-stopped'} />
            <span className={`text-xs font-mono ${botRunning ? 'text-brand-green' : 'text-brand-muted'}`}>
              {botRunning ? 'BOT ON' : 'IDLE'}
            </span>
          </div>
        </div>

        {/* Notification bell */}
        <button
          onClick={onBellClick}
          className="relative p-1.5 rounded-lg text-brand-muted hover:text-brand-accent hover:bg-brand-accent/10 transition-all"
        >
          <Bell size={16} />
          {unreadCount > 0 && (
            <span className="absolute -top-0.5 -right-0.5 bg-brand-red text-white text-xs font-mono w-4 h-4 rounded-full flex items-center justify-center leading-none">
              {unreadCount > 9 ? '9+' : unreadCount}
            </span>
          )}
        </button>
      </div>
    </header>
  );
}
