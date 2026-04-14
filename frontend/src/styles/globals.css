@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;700;800&family=DM+Sans:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  --bg:      #0A0E1A;
  --surface: #111827;
  --card:    #1A2235;
  --border:  #243049;
  --accent:  #00D4FF;
  --green:   #00FF88;
  --red:     #FF3B5C;
  --yellow:  #FFB800;
}

* { box-sizing: border-box; }

html, body {
  background: var(--bg);
  color: #E2E8F0;
  font-family: 'DM Sans', sans-serif;
  -webkit-font-smoothing: antialiased;
}

/* Custom scrollbar */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: var(--surface); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }
::-webkit-scrollbar-thumb:hover { background: var(--accent); }

/* Glowing card border */
.card-glow {
  border: 1px solid var(--border);
  box-shadow: 0 0 0 1px rgba(0,212,255,0.05), inset 0 1px 0 rgba(255,255,255,0.03);
}

.card-glow:hover {
  border-color: rgba(0,212,255,0.25);
  box-shadow: 0 0 20px rgba(0,212,255,0.08);
  transition: all 0.3s ease;
}

/* Numeric values */
.num { font-family: 'JetBrains Mono', monospace; }

/* Positive / Negative coloring */
.pos { color: var(--green); }
.neg { color: var(--red); }

/* Status dot */
.dot-live {
  width: 8px; height: 8px;
  border-radius: 50%;
  background: var(--green);
  box-shadow: 0 0 8px var(--green);
  animation: pulse 2s ease infinite;
}
.dot-stopped {
  width: 8px; height: 8px;
  border-radius: 50%;
  background: var(--red);
}

/* Mobile-safe bottom padding */
.pb-safe { padding-bottom: max(16px, env(safe-area-inset-bottom)); }
