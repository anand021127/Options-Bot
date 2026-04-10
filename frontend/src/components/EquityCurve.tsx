'use client';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { TrendingUp } from 'lucide-react';

function CustomTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  const pos = d.capital >= (payload[0].payload.initial ?? d.capital);
  return (
    <div className="bg-brand-card border border-brand-border rounded-lg p-2 text-xs font-mono">
      <p className="text-brand-muted">{d.timestamp?.slice(0,16)?.replace('T',' ')}</p>
      <p className={`font-bold ${pos?'text-brand-green':'text-brand-red'}`}>
        ₹{d.capital?.toLocaleString('en-IN',{maximumFractionDigits:0})}
      </p>
      <p className="text-brand-muted">P&L: ₹{d.total_pnl?.toFixed(0)}</p>
    </div>
  );
}

export default function EquityCurve({ data }: { data: any[] }) {
  if (!data?.length) return (
    <div className="bg-brand-card card-glow rounded-2xl p-4">
      <div className="flex items-center gap-2 mb-3">
        <TrendingUp size={14} className="text-brand-accent"/>
        <h2 className="font-display font-bold text-sm">Equity Curve</h2>
      </div>
      <div className="h-32 flex items-center justify-center text-brand-muted text-xs font-mono">
        No trades yet — start the bot to see performance
      </div>
    </div>
  );

  const initial = data[0]?.capital ?? 100000;
  const latest  = data[data.length-1]?.capital ?? initial;
  const pnlPct  = ((latest - initial) / initial * 100).toFixed(2);
  const isPos   = latest >= initial;

  // Gradient color based on performance
  const strokeColor = isPos ? '#00FF88' : '#FF3B5C';
  const fillId = isPos ? 'equityGreen' : 'equityRed';

  return (
    <div className="bg-brand-card card-glow rounded-2xl p-4">
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <TrendingUp size={14} className="text-brand-accent"/>
          <h2 className="font-display font-bold text-sm">Equity Curve</h2>
        </div>
        <span className={`font-mono font-bold text-sm ${isPos?'text-brand-green':'text-brand-red'}`}>
          {isPos?'+':''}{pnlPct}%
        </span>
      </div>
      <p className="text-brand-muted text-xs font-mono mb-3">{data.length} snapshots</p>

      <ResponsiveContainer width="100%" height={140}>
        <AreaChart data={data} margin={{top:4,right:0,left:0,bottom:0}}>
          <defs>
            <linearGradient id="equityGreen" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="#00FF88" stopOpacity={0.3}/>
              <stop offset="95%" stopColor="#00FF88" stopOpacity={0}/>
            </linearGradient>
            <linearGradient id="equityRed" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="#FF3B5C" stopOpacity={0.3}/>
              <stop offset="95%" stopColor="#FF3B5C" stopOpacity={0}/>
            </linearGradient>
          </defs>
          <XAxis dataKey="timestamp" hide />
          <YAxis domain={['auto','auto']} hide />
          <Tooltip content={<CustomTooltip />} />
          <Area type="monotone" dataKey="capital"
            stroke={strokeColor} strokeWidth={2}
            fill={`url(#${fillId})`} dot={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
