<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Agentscope Dashboard</title>
<style>
:root{--bg:#0b0d10;--card:#11151a;--line:#272e37;--tx:#eef1f4;--mut:#89939f;--acc:#7694ff;--ok:#56d68b;--bad:#ff7373;--warn:#e6ad59}
*{box-sizing:border-box;margin:0;padding:0}html{scroll-behavior:smooth}body{background:var(--bg);color:var(--tx);font:14px/1.5 Inter,ui-sans-serif,system-ui,-apple-system,\"Segoe UI\",sans-serif;padding:18px;width:min(1120px,calc(100% - 24px));margin:0 auto;-webkit-font-smoothing:antialiased}h1{font:800 15px ui-monospace,SFMono-Regular,monospace;letter-spacing:.06em;text-transform:uppercase;margin:2px 0}.sub{color:var(--mut);font:11px ui-monospace,monospace;margin:6px 0 18px}.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-bottom:10px}.kpi,.panel{background:var(--card);border:1px solid var(--line);border-radius:11px}.kpi{padding:15px}.kpi .v{font:800 28px ui-monospace,monospace;color:var(--acc);font-variant-numeric:tabular-nums}.vsub{font-size:13px;color:var(--mut);font-weight:500}.kpi .l{color:var(--mut);font:800 9px ui-monospace,monospace;text-transform:uppercase;letter-spacing:.1em;margin-top:4px}.panel{padding:15px;margin-bottom:10px;overflow-x:auto}.panel h2{font:800 10px ui-monospace,monospace;color:var(--mut);text-transform:uppercase;letter-spacing:.11em;margin-bottom:10px}.panel.attn{border-color:#5e3438}.panel.attn h2{color:#ff9c9c}.panel.calm{opacity:.9}.anom{padding:11px 0;border-top:1px solid var(--line);font-size:12px}.anom:first-of-type{border-top:0}.badge{font:800 9px ui-monospace;padding:4px 7px;border-radius:5px;margin-right:7px}.nowrap{white-space:nowrap}table{width:100%;min-width:620px;border-collapse:collapse;font-size:12px}td{padding:10px 8px;border-top:1px solid var(--line);vertical-align:top}tr:first-child td{border-top:0}.mut{color:var(--mut)}.pill{font:800 9px ui-monospace;padding:4px 7px;border-radius:999px}.pill.on{background:#143323;color:#7de3a6}.pill.off{border:1px solid var(--line);color:#77818c}.st{font-weight:600}.st.f{color:var(--bad)}.st.s{color:var(--ok)}.chips{display:flex;gap:6px;margin-bottom:8px}.chip{font:800 10px ui-monospace;padding:6px 10px;border-radius:7px;border:1px solid var(--line);background:transparent;color:var(--mut);cursor:pointer}.chip.active{background:#252e43;border-color:#3d4f80;color:#dce4ff}.hlth{font:800 10px ui-monospace;padding:3px 7px;border-radius:999px}.hlth.ok{color:var(--ok);background:#143323}.hlth.warn{color:var(--warn);background:#3d2e18}.hlth.bad{color:var(--bad);background:#4a2024}.ackbtn{float:right;font:800 9px ui-monospace;padding:4px 8px;border-radius:7px;border:1px solid var(--line);background:transparent;color:var(--mut);cursor:pointer}.ackbtn:hover{border-color:#56606c}.ackbtn:disabled{cursor:default;opacity:.65}tr.grp td{background:#151a20;color:var(--mut);font:800 9px ui-monospace;text-transform:uppercase;letter-spacing:.1em}footer{color:#66717d;font:10px ui-monospace;text-align:center;margin-top:14px}
@media(max-width: 760px) {
    body { width: calc(100% - 20px); padding: 12px; }
    .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .kpi .v { font-size: 23px; }
    .panel { padding: 12px; }
}
@media(max-width: 420px) {
    .grid { grid-template-columns: 1fr; }
    .kpi .v { font-size: 25px; }
}
@media(prefers-reduced-motion: reduce) {
    * { transition: none !important; }
}
</style>
</head>
<body class="compact">
<h1>Agentscope Dashboard</h1>
<div class="sub">Supervision view · read-only</div>
<div class="grid">
    <div class="kpi"><div class="v">0</div><div class="l">Scheduled jobs on</div></div>
    <div class="kpi"><div class="v" style="color:var(--bad)">0</div><div class="l">Failed runs (24h)</div></div>
    <div class="kpi"><div class="v">0</div><div class="l">OK runs (24h)</div></div>
</div>
</body>
</html>