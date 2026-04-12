'use client';

interface Alert {
  id: number;
  msg: string;
  type: 'success' | 'error' | 'info';
}

const COLORS = {
  success: { bg: '#00FF8815', border: '#00FF8844', text: '#00FF88' },
  error:   { bg: '#FF3B5C15', border: '#FF3B5C44', text: '#FF3B5C' },
  info:    { bg: '#00D4FF15', border: '#00D4FF44', text: '#00D4FF' },
};

export default function AlertToast({ alerts }: { alerts: Alert[] }) {
  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 max-w-xs w-full pointer-events-none">
      {alerts.map(alert => {
        const c = COLORS[alert.type];
        return (
          <div key={alert.id} className="rounded-xl px-4 py-3 text-sm animate-slide-up pointer-events-auto"
               style={{ background: c.bg, border: `1px solid ${c.border}`, color: c.text }}>
            {alert.msg}
          </div>
        );
      })}
    </div>
  );
}
