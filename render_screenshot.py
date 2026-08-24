#!/usr/bin/env python3
"""Render the agentscope marketing screenshot with PIL (no browser needed).
Recreates the dashboard's dark theme faithfully at 2x for crisp README display."""
from PIL import Image, ImageDraw, ImageFont
import os

W, H = 1600, 1200
S = 2  # supersample
W, H = W*S, H*S

# tokens (dark theme, matches generate.py)
BG="#101418"; CARD="#181e25"; LINE="#2a323c"; TX="#e8edf2"; MUT="#8a97a5"; ACC="#5b8def"
OK="#4ade80"; BAD="#f87171"; WARNBG="#fef3c7"; WARNFG="#b45309"; FAILBG="#fee2e2"; FAILFG="#b91c1c"

def font(size, bold=False):
    for p in ["/data/data/com.termux/files/usr/share/fonts/TTF/DejaVuSans-Bold.ttf" if bold else "/data/data/com.termux/files/usr/share/fonts/TTF/DejaVuSans.ttf",
              "/system/fonts/Roboto-Regular.ttf"]:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)
f_title=font(34*S,True); f_sub=font(20*S); f_kpi=font(52*S,True); f_vsub=font(26*S); f_lab=font(17*S)
f_h2=font(18*S,True); f_row=font(20*S); f_small=font(18*S); f_badge=font(14*S,True); f_pill=font(14*S,True)
f_mono=font(18*S)

PAD=48*S
# title
d.ellipse([PAD, 40*S, PAD+16*S, 56*S], fill=ACC)
d.text((PAD+30*S, 34*S), "AGENT COMMAND", font=f_title, fill=TX)
d.text((PAD, 84*S), "Mon 24 Aug · 08:00 — supervision view · read-only", font=f_sub, fill=MUT)

# KPI row
kpis=[("3/9","SCHEDULED JOBS ON",ACC),("5","FAILED RUNS (24H)",BAD),("0","OK RUNS (24H)",ACC),("1/1","ACTIVE LEADS",ACC)]
kw=(W-PAD*2-3*16*S)//4
ky=130*S; kh=120*S
for i,(v,l,c) in enumerate(kpis):
    x=PAD+i*(kw+16*S)
    d.rounded_rectangle([x,ky,x+kw,ky+kh], radius=12*S, fill=CARD, outline=LINE, width=1*S)
    d.text((x+16*S, ky+14*S), v, font=f_kpi, fill=c)
    d.text((x+16*S, ky+82*S), l, font=f_lab, fill=MUT)

def panel(y, h, title):
    d.rounded_rectangle([PAD, y, W-PAD, y+h], radius=12*S, fill=CARD, outline=LINE, width=1*S)
    d.text((PAD+18*S, y+14*S), title, font=f_h2, fill=MUT)
    return y

# needs attention panel
ay=panel(ky+kh+18*S, 250*S, "⚠  NEEDS ATTENTION")
items=[("WARN","6 scheduled job(s) disabled: Loopii Daily Summary, Payment Reminders, BOQ Intake…",WARNFG,WARNBG),
       ("FAIL","'FS Tender Discovery' skipping runs — inference/config drift detected. Re-pin its config to restore.",FAILFG,FAILBG),
       ("FAIL","'FS Tender Weekly Learning' skipping runs — inference/config drift detected. Re-pin its config to restore.",FAILFG,FAILBG)]
iy=ay+52*S
for tag,msg,fg,bg in items:
    bw=52*S
    d.rounded_rectangle([PAD+18*S, iy, PAD+18*S+bw, iy+26*S], radius=99*S, fill=bg)
    tw=d.textlength(tag,font=f_badge)
    d.text((PAD+18*S+(bw-tw)//2, iy+4*S), tag, font=f_badge, fill=fg)
    d.text((PAD+18*S+bw+14*S, iy+2*S), msg[:78], font=f_row, fill=TX)
    iy+=64*S

# scheduled jobs panel
jy=panel(ay+250*S+18*S, 250*S, "SCHEDULED JOBS")
jobs=[("FS Tender Discovery","every 360m","ON"),("Taste Index weekly curator","0 8 * * 1","ON"),
      ("Loopii Daily Summary","0 18 * * *","OFF"),("BOQ Intake Daily Summary","0 17 * * *","OFF")]
jy2=jy+52*S
for name,sched,st in jobs:
    d.text((PAD+18*S, jy2), name, font=f_row, fill=TX)
    d.text((PAD+560*S, jy2), sched, font=f_row, fill=MUT)
    pw=46*S
    px=W-PAD-18*S-pw
    if st=="ON":
        d.rounded_rectangle([px, jy2-2*S, px+pw, jy2+22*S], radius=99*S, fill=ACC)
        d.text((px+14*S, jy2+2*S), "ON", font=f_pill, fill="#fff")
    else:
        d.rounded_rectangle([px, jy2-2*S, px+pw, jy2+22*S], radius=99*S, outline=LINE, width=1*S)
        d.text((px+11*S, jy2+2*S), "OFF", font=f_pill, fill=MUT)
    jy2+=48*S

out = os.path.expanduser("~/agent-supervision/docs/screenshot.png")
img = img.resize((W//S, H//S), Image.LANCZOS)
img.save(out, optimize=True)
print("saved", out, img.size)
