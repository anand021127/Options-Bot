'use client';
import { useState, useEffect } from 'react';
import { Bell, X, CheckCheck, AlertTriangle, TrendingUp, Info } from 'lucide-react';
import { api } from '@/utils/api';

const TYPE_STYLE: Record<string, { icon: any; color: string; bg: string }> = {
  TRADE:     { icon: TrendingUp,    color: 'text-brand-green',  bg: 'bg-brand-green/10 border-brand-green/25' },
  WARNING:   { icon: AlertTriangle, color: 'text-brand-yellow', bg: 'bg-brand-yellow/10 border-brand-yellow/25' },
  EMERGENCY: { icon: X,             color: 'text-brand-red',    bg: 'bg-brand-red/10 border-brand-red/25' },
  INFO:      { icon: Info,          color: 'text-brand-accent', bg: 'bg-brand-accent/10 border-brand-accent/25' },
};

export default function NotificationsPanel({ onClose }: { onClose: () => void }) {
  const [notifs, setNotifs]   = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getNotifications(30).then(d => { setNotifs(d); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  const markRead = async () => {
    await api.markNotificationsRead();
    setNotifs(n => n.map(x => ({ ...x, read: 1 })));
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-brand-card w-full max-w-md rounded-t-2xl sm:rounded-2xl p-4 max-h-[80vh] flex flex-col animate-slide-up border border-brand-border">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Bell size={15} className="text-brand-accent"/>
            <h2 className="font-display font-bold text-sm">Notifications</h2>
            {notifs.some(n => !n.read) && (
              <span className="bg-brand-red text-white text-xs font-mono px-1.5 py-0.5 rounded-full">
                {notifs.filter(n => !n.read).length}
              </span>
            )}
          </div>
          <div className="flex gap-2">
            <button onClick={markRead} className="text-brand-muted hover:text-brand-accent text-xs flex items-center gap-1">
              <CheckCheck size={12}/> Mark read
            </button>
            <button onClick={onClose} className="text-brand-muted hover:text-brand-red p-1">
              <X size={15}/>
            </button>
          </div>
        </div>

        <div className="overflow-y-auto flex-1 space-y-2 pr-1">
          {loading ? (
            <div className="text-center py-8"><div className="w-6 h-6 border-2 border-brand-accent border-t-transparent rounded-full animate-spin mx-auto"/></div>
          ) : !notifs.length ? (
            <div className="text-center py-8 text-brand-muted text-sm font-mono">No notifications yet</div>
          ) : notifs.map((n: any) => {
            const style = TYPE_STYLE[n.type] || TYPE_STYLE.INFO;
            const Icon  = style.icon;
            const time  = n.timestamp ? new Date(n.timestamp).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) : '';
            return (
              <div key={n.id} className={`flex gap-3 p-3 rounded-xl border ${style.bg} ${n.read ? 'opacity-60' : ''}`}>
                <Icon size={14} className={`${style.color} flex-shrink-0 mt-0.5`}/>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-1">
                    <p className={`text-xs font-mono font-bold ${style.color}`}>{n.title}</p>
                    <span className="text-brand-muted text-xs font-mono flex-shrink-0">{time}</span>
                  </div>
                  <p className="text-brand-text text-xs mt-0.5 font-mono break-words">{n.message}</p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
