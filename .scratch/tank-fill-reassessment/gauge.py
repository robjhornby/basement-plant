"""Moisture-drawdown fuel gauge: live state + honest leave-one-out backtest."""
from __future__ import annotations
import duckdb, numpy as np
from datetime import datetime

D="data/parquet-2026-08-07"
INSTALL=datetime(2026,7,1,21,0)
FULLS=[datetime(2026,7,5,0,51,3),datetime(2026,7,11,1,46,29),datetime(2026,7,15,7,31,16),
       datetime(2026,7,23,21,42,8),datetime(2026,7,29,15,39,48)]
con=duckdb.connect()
r=con.execute(f"""select epoch(timestamp)::bigint, relative_humidity_pct, absolute_humidity_g_m3
  from read_parquet('{D}/sensor_readings/**/*.parquet',hive_partitioning=true)
  where location='Basement' and timestamp>=timestamp '2026-07-01 21:00' order by timestamp""").fetchall()
a=np.array(r,dtype=float); ts=a[:,0].astype("datetime64[s]"); rh=a[:,1]; ah=a[:,2]
minutes=(ts-ts[0]).astype("timedelta64[m]").astype(int)
def rmed(x,w):
    h=w//2; return np.array([np.median(x[max(0,i-h):i+h+1]) for i in range(len(x))])
srh=rmed(rh,9)
def extrema(y,half,prom,kind):
    idx=[]
    for i in range(len(y)):
        seg=y[max(0,i-half):min(len(y),i+half+1)]
        ok=(y[i]==seg.min()) if kind==-1 else (y[i]==seg.max())
        if not ok: continue
        L=y[max(0,i-45):i]; R=y[i+1:i+46]
        if not len(L) or not len(R): continue
        p=(min(L.max(),R.max())-y[i]) if kind==-1 else (y[i]-max(L.min(),R.min()))
        if p>=prom: idx.append(i)
    out=[]
    for i in idx:
        if out and i-out[-1]<15:
            if (kind==-1 and y[i]<y[out[-1]]) or (kind==+1 and y[i]>y[out[-1]]): out[-1]=i
        else: out.append(i)
    return out
troughs=extrema(srh,10,0.8,-1); peaks=extrema(srh,10,0.8,+1)
def prev_peak(tr):
    ps=[p for p in peaks if p<tr and minutes[tr]-minutes[p]<120]; return ps[-1] if ps else None
# per-cycle AH drawdown, indexed by trough time (minute)
cyc=[]  # (minute_at_trough, ah_drawdown)
for tr in troughs:
    p=prev_peak(tr)
    if p is not None:
        cyc.append((minutes[tr], max(0.0, ah[p]-ah[tr])))
cyc.sort()
cyc_m=np.array([c[0] for c in cyc]); cyc_d=np.array([c[1] for c in cyc])
def mnt(dt): return int((np.datetime64(dt)-ts[0]).astype("timedelta64[m]").astype(int))
def resume_after(full):
    fm=mnt(full)
    for j in troughs:
        if minutes[j]>fm+30 and len([k for k in troughs if minutes[j]<=minutes[k]<=minutes[j]+180])>=3:
            return ts[j]
    return np.datetime64(full)+np.timedelta64(6,'h')
emptied=[resume_after(f) for f in FULLS]
def dose(m0,m1): return float(cyc_d[(cyc_m>=m0)&(cyc_m<=m1)].sum())

# calibration: AH-drawdown sum per completed tank
starts=[np.datetime64(INSTALL)]+emptied
tanks=[]
for k,full in enumerate(FULLS):
    m0=mnt(starts[k]); m1=mnt(full); d=dose(m0,m1); days=(m1-m0)/1440
    tanks.append((d,days));
tanks=np.array(tanks)
calib=tanks[:,0].mean()
print("per-tank AH-drawdown dose / days / dose-per-day:")
for i,(d,days) in enumerate(tanks): print(f"  tank{i+1}: dose={d:.1f}  days={days:.2f}  dose/day={d/days:.2f}")
print(f"CALIBRATION amplitude-per-tank = {calib:.1f} g/m3 (=25 L)  scatter ±{tanks[:,0].std()/calib*100:.0f}%")

# ---- LIVE STATE of current open tank (since last emptied) ----
now=minutes[-1]; open_start=mnt(emptied[-1])
open_dose=dose(open_start,now)
frac=open_dose/calib
elapsed=(now-open_start)/1440
# recent rate: dose/day over trailing 3 days
r3=dose(now-3*1440,now)/3
r_all=open_dose/elapsed
remaining_dose=max(0.0,calib-open_dose)
# per-cycle mean amplitude recently -> cycles remaining
recent_cyc=cyc_d[(cyc_m>=now-3*1440)&(cyc_m<=now)]
amp_per_cycle=float(np.median(recent_cyc)) if len(recent_cyc) else float(np.median(cyc_d))
cycles_remaining=remaining_dose/amp_per_cycle
recent_cyc_per_day=len(recent_cyc)/3
print(f"\n--- LIVE (data ends {str(ts[-1])[:16]}) ---")
print(f"open tank emptied ≈ {str(emptied[-1])[:16]}, elapsed {elapsed:.1f} d")
print(f"cumulative drawdown dose = {open_dose:.1f} / {calib:.1f}  =>  ~{frac*100:.0f}% full ({frac*25:.1f} of 25 L)")
print(f"remaining dose = {remaining_dose:.1f}  |  recent amp/cycle = {amp_per_cycle:.3f}  =>  cycles remaining ≈ {cycles_remaining:.0f}")
print(f"recent cycles/day (3d) = {recent_cyc_per_day:.1f}  =>  time remaining ≈ {cycles_remaining/max(recent_cyc_per_day,1e-9):.1f} d")
print(f"rate check: dose/day recent(3d)={r3:.2f}  whole-open={r_all:.2f}  => time via dose = {remaining_dose/max(r3,1e-9):.1f} d (recent), {remaining_dose/max(r_all,1e-9):.1f} d (avg)")
naive_days=tanks[:,1].mean()
print(f"\nNAIVE days-model would predict full at emptied+{naive_days:.1f}d = {str(emptied[-1]+np.timedelta64(int(naive_days*1440),'m'))[:16]} (already elapsed {elapsed:.1f}d)")

# ---- honest backtest: predict each tank's duration from a causal mid-interval gauge ----
print("\n--- backtest: at 50% of each tank's ACTUAL time, predict remaining ---")
print("tank | true_days | gauge_pred_days | naive_pred_days")
loo_err_g=[]; loo_err_n=[]
for k,full in enumerate(FULLS):
    m0=mnt(starts[k]); m1=mnt(full); true_days=(m1-m0)/1440
    tmid=m0+(m1-m0)//2
    dmid=dose(m0,tmid)
    # calibration excluding this tank (leave-one-out)
    others=[tanks[j,0] for j in range(len(tanks)) if j!=k]; cal=np.mean(others)
    rate=dmid/((tmid-m0)/1440)  # dose/day so far this tank
    pred_remaining=max(0.0,cal-dmid)/max(rate,1e-9)
    gauge_pred=(tmid-m0)/1440+pred_remaining
    naive=np.mean([tanks[j,1] for j in range(len(tanks)) if j!=k])
    loo_err_g.append(gauge_pred-true_days); loo_err_n.append(naive-true_days)
    print(f"  {k+1}   |  {true_days:.2f}    |   {gauge_pred:.2f}        |   {naive:.2f}")
print(f"gauge  MAE={np.mean(np.abs(loo_err_g)):.2f} d   naive MAE={np.mean(np.abs(loo_err_n)):.2f} d")
