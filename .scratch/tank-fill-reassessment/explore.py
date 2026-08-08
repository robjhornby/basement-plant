"""Exploratory: is the dehumidifier tank better measured in cycles/runtime than days?"""
from __future__ import annotations
import duckdb, numpy as np, polars as pl
from datetime import datetime, timedelta

D = "data/parquet-2026-08-07"
INSTALL = datetime(2026, 7, 1, 21, 0)
TANK_FULL_EVENTS = [  # from data/basement_events.csv
    datetime(2026, 7, 5, 0, 51, 3),
    datetime(2026, 7, 11, 1, 46, 29),
    datetime(2026, 7, 15, 7, 31, 16),
    datetime(2026, 7, 23, 21, 42, 8),
    datetime(2026, 7, 29, 15, 39, 48),
]

con = duckdb.connect()
rowsdb = con.execute(f"""
  select epoch(timestamp)::bigint, relative_humidity_pct, temperature_c, absolute_humidity_g_m3
  from read_parquet('{D}/sensor_readings/**/*.parquet', hive_partitioning=true)
  where location='Basement' and timestamp >= timestamp '2026-07-01 21:00'
  order by timestamp
""").fetchall()
arr = np.array(rowsdb, dtype=float)
ts = arr[:,0].astype("datetime64[s]")
rh = arr[:,1]; tc = arr[:,2]; ah = arr[:,3]
n = len(rh)
minutes = (ts - ts[0]).astype("timedelta64[m]").astype(int)  # minute index (may have gaps)

def rolling_median(x, w):
    half = w // 2
    out = np.empty_like(x)
    for i in range(len(x)):
        out[i] = np.median(x[max(0, i-half):i+half+1])
    return out

srh = rolling_median(rh, 9)

def local_extrema(y, half, prom, kind):
    """Indices of local minima (kind=-1) or maxima (+1) with prominence over +-half window."""
    idx = []
    for i in range(len(y)):
        lo, hi = max(0, i-half), min(len(y), i+half+1)
        seg = y[lo:hi]
        if kind == -1 and y[i] == seg.min():
            left = y[max(0,i-45):i]; right = y[i+1:i+46]
            if len(left) and len(right):
                p = min(left.max(), right.max()) - y[i]
                if p >= prom: idx.append(i)
        if kind == +1 and y[i] == seg.max():
            left = y[max(0,i-45):i]; right = y[i+1:i+46]
            if len(left) and len(right):
                p = y[i] - max(left.min(), right.min())
                if p >= prom: idx.append(i)
    # collapse plateaus / near-duplicates within 15 min
    out = []
    for i in idx:
        if out and i - out[-1] < 15:
            if (kind==-1 and y[i] < y[out[-1]]) or (kind==+1 and y[i] > y[out[-1]]):
                out[-1] = i
        else:
            out.append(i)
    return out

troughs = local_extrema(srh, 10, 0.8, -1)
peaks   = local_extrema(srh, 10, 0.8, +1)
print(f"n={n} troughs(prom0.8)={len(troughs)} peaks={len(peaks)}")

# lower-prominence trough count (catch shallow dry-regime cycles)
troughs_lo = local_extrema(srh, 10, 0.4, -1)
print(f"troughs(prom0.4)={len(troughs_lo)}")

def tstr(dt64): return str(dt64.astype("datetime64[m]")).replace("T"," ")

# ---- emptied time after each tank-full event = when cycling resumes ----
def minute_of(dt): return int((np.datetime64(dt) - ts[0]).astype("timedelta64[m]").astype(int))
def resume_after(full_dt):
    fm = minute_of(full_dt)
    later = [j for j in troughs if minutes[j] > fm + 30]
    for j in later:
        nxt = [k for k in troughs if minutes[j] <= minutes[k] <= minutes[j]+180]
        if len(nxt) >= 3:   # cycling clearly resumed
            return ts[j]
    return np.datetime64(full_dt) + np.timedelta64(6, 'h')

full_times = [np.datetime64(e) for e in TANK_FULL_EVENTS]
emptied_after = [resume_after(e) for e in TANK_FULL_EVENTS]
print("\n=== emptied (cycling-resumed) time after each CSV tank-full event ===")
for e, em in zip(TANK_FULL_EVENTS, emptied_after):
    print(f"  full {e}  ->  emptied≈{tstr(em)}  (+{(minute_of(em)-minute_of(e))/60:.1f}h)")

print("\n=== per fill interval: days vs cycles vs runtime ===")
print("start | full | days | cycles(0.8) | cycles(0.4) | runtime_h | cyc/day")
rows=[]
for k, full in enumerate(full_times):
    start = np.datetime64(INSTALL) if k == 0 else emptied_after[k-1]
    m0 = minute_of(start)
    m1 = minute_of(full)
    sel = [j for j in troughs if m0 <= minutes[j] <= m1]
    sel_lo = [j for j in troughs_lo if m0 <= minutes[j] <= m1]
    # runtime = sum of peak->trough fall durations within interval
    runtime = 0.0
    for tr in sel:
        prev_pk = [p for p in peaks if p < tr and minutes[tr]-minutes[p] < 120]
        if prev_pk:
            runtime += (minutes[tr]-minutes[prev_pk[-1]])
    days = (m1-m0)/1440
    rows.append((days, len(sel), len(sel_lo), runtime/60))
    print(f"{tstr(start)} | {tstr(full)} | {days:.2f} | {len(sel)} | {len(sel_lo)} | {runtime/60:.1f} | {len(sel)/days:.1f}")

a = np.array(rows)
def cov(x): return np.std(x)/np.mean(x)

# ---- moisture-rebound signal: AH slope right after each compressor-off (trough) ----
def rebound_at(tr, span=15):
    """g/m^3 per hour that AH rises in the `span` minutes after a trough."""
    m_tr = minutes[tr]
    j = tr
    while j < len(minutes)-1 and minutes[j] < m_tr + span:
        j += 1
    dt_h = (minutes[j]-m_tr)/60
    if dt_h <= 0: return None
    return (ah[j]-ah[tr])/dt_h

reb = {tr: rebound_at(tr) for tr in troughs}
print("\n=== moisture-rebound (off-phase AH rise) per interval ===")
print("start | days | median_rebound_gm3ph | dose = rebound*days")
doses=[]
for k, full in enumerate(full_times):
    start = np.datetime64(INSTALL) if k == 0 else emptied_after[k-1]
    m0, m1 = minute_of(start), minute_of(full)
    vals = [reb[j] for j in troughs if m0 <= minutes[j] <= m1 and reb[j] is not None and reb[j] > 0]
    med = float(np.median(vals)) if vals else 0.0
    days = (m1-m0)/1440
    dose = med*days
    doses.append(dose)
    print(f"{tstr(start)} | {days:.2f} | {med:.3f} | {dose:.3f}")
doses=np.array(doses)

print("\n=== coefficient of variation across tanks (lower = better fuel gauge) ===")
print(f"  days/tank        mean={a[:,0].mean():.2f}   CoV={cov(a[:,0]):.3f}")
print(f"  cycles/tank(0.8) mean={a[:,1].mean():.1f}  CoV={cov(a[:,1]):.3f}")
print(f"  cycles/tank(0.4) mean={a[:,2].mean():.1f}  CoV={cov(a[:,2]):.3f}")
print(f"  runtime_h/tank   mean={a[:,3].mean():.1f}   CoV={cov(a[:,3]):.3f}")
print(f"  rebound-dose     mean={doses.mean():.3f}  CoV={cov(doses):.3f}")

# ---- candidate "doses" that should equal 25 L each tank if the proxy is right ----
# per-cycle amplitude: preceding peak minus trough, in RH and AH
def prev_peak(tr):
    ps=[p for p in peaks if p<tr and minutes[tr]-minutes[p]<120]
    return ps[-1] if ps else None
amp_rh={}; amp_ah={}
for tr in troughs:
    p=prev_peak(tr)
    if p is not None:
        amp_rh[tr]=max(0.0, srh[p]-srh[tr])
        amp_ah[tr]=max(0.0, ah[p]-ah[tr])

def interval_troughs(k):
    start = np.datetime64(INSTALL) if k==0 else emptied_after[k-1]
    m0,m1=minute_of(start),minute_of(full_times[k])
    return [j for j in troughs if m0<=minutes[j]<=m1],(m1-m0)/1440

def dose_cov(fn):
    ds=[]
    for k in range(len(full_times)):
        trs,days=interval_troughs(k)
        ds.append(fn(trs,days))
    ds=np.array(ds); return ds, cov(ds)

print("\n=== candidate dose invariance (each should be constant if it tracks 25 L) ===")
cands={
 "sum cycle RH-amplitude": lambda trs,days: sum(amp_rh.get(t,0) for t in trs),
 "sum cycle AH-amplitude": lambda trs,days: sum(amp_ah.get(t,0) for t in trs),
 "count cycles":           lambda trs,days: len(trs),
 "days":                   lambda trs,days: days,
}
for name,fn in cands.items():
    ds,c=dose_cov(fn)
    print(f"  {name:24s} CoV={c:.3f}  vals={[round(float(x),1) for x in ds]}")

# moisture-weighted runtime: runtime_h * (meanAH - AH0), scan AH0
print("\n  moisture-weighted runtime  runtime_h*(meanAH-AH0):")
for AH0 in [6,7,8,8.5,9]:
    ds=[]
    for k in range(len(full_times)):
        trs,days=interval_troughs(k)
        rt=0.0
        for tr in trs:
            p=prev_peak(tr)
            if p is not None: rt+=(minutes[tr]-minutes[p])
        m0=minute_of(np.datetime64(INSTALL) if k==0 else emptied_after[k-1]); m1=minute_of(full_times[k])
        mask=(minutes>=m0)&(minutes<=m1)
        meanAH=ah[mask].mean()
        ds.append(rt/60*(meanAH-AH0))
    ds=np.array(ds); print(f"    AH0={AH0}: CoV={cov(ds):.3f}  vals={[round(float(x),1) for x in ds]}")

# daily rebound trend (is the basement drying?)
print("\n=== daily median off-phase rebound (drying trend) ===")
import collections
byday=collections.defaultdict(list)
for tr in troughs:
    if reb[tr] is not None and reb[tr]>0:
        d=str(ts[tr].astype('datetime64[D]')); byday[d].append(reb[tr])
for d in sorted(byday):
    v=byday[d]; print(f"  {d}  n={len(v):3d}  med={np.median(v):.3f}")
