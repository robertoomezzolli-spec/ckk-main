#!/usr/bin/env python3
"""Raw ILRS normal-point ingestion gate for LARES-2/LAGEOS.

External harness only. CKK kernel remains untouched.

Purpose:
- Download public monthly CRDv2 normal-point files from EDC for the 1050-day
  interval used in the 2026 Nature frame-dragging analysis (starting 2022-07-17).
- Parse measurement records and station/satellite metadata.
- Verify that both satellites have overlapping, multi-station, multi-epoch coverage
  sufficient to support a later held-out orbit-determination test.

This script deliberately does NOT claim a new residual: raw ranges alone are not
nodal residuals. A physics result requires full orbit determination with frozen
force, tide, station, EOP and gravity models.
"""
from __future__ import annotations
import urllib.request, urllib.error
import datetime as dt, json, math
from pathlib import Path
from collections import Counter, defaultdict

BASE='https://edc.dgfi.tum.de/pub/slr/data/npt_crd_v2/{sat}/{year}/{sat}_{year}{month:02d}.np2'
START=dt.date(2022,7,17)
END=START+dt.timedelta(days=1050)
SATS=('lares2','lageos1')
OUT=Path(__file__).resolve().parents[1]/'results'/'satellite_raw_ingest_gate.json'
CACHE=Path(__file__).resolve().parents[1]/'results'/'raw_ilrs_cache'


def months_between(a,b):
    y,m=a.year,a.month
    while (y,m) <= (b.year,b.month):
        yield y,m
        if m==12: y,m=y+1,1
        else: m+=1


def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':'ckk-external-evidence-gate/1.0'})
    with urllib.request.urlopen(req,timeout=60) as r:
        return r.read().decode('utf-8','replace')


def parse_crd(text,sat):
    station=None
    station_records=[]
    ranges=[]
    for raw in text.splitlines():
        line=raw.strip()
        if not line: continue
        parts=line.split()
        if parts[0]=='H2' and len(parts)>=5:
            # marker, pad id, system no, occupancy no
            station=':'.join(parts[1:5])
        elif parts[0]=='H4' and len(parts)>=8:
            try:
                y,mo,d,hh,mi,ss=map(int,parts[2:8])
                station_records.append((dt.datetime(y,mo,d,hh,mi,ss),station))
            except Exception:
                pass
        elif parts[0]=='11' and len(parts)>=4:
            try:
                sec=float(parts[1]); tof=float(parts[2])
                ranges.append((station,sec,tof))
            except Exception:
                pass
    return station_records,ranges


def main():
    CACHE.mkdir(parents=True,exist_ok=True)
    summary={}
    all_dates={}
    for sat in SATS:
        downloads=[]; misses=[]; stations=Counter(); n_obs=0; pass_starts=[]
        for y,m in months_between(START,END):
            url=BASE.format(sat=sat,year=y,month=m)
            path=CACHE/f'{sat}_{y}{m:02d}.np2'
            try:
                if path.exists(): txt=path.read_text(errors='replace')
                else:
                    txt=fetch(url); path.write_text(txt)
                downloads.append(url)
            except Exception as e:
                misses.append({'url':url,'error':type(e).__name__})
                continue
            starts,ranges=parse_crd(txt,sat)
            for t,st in starts:
                if START <= t.date() <= END:
                    pass_starts.append(t)
                    if st: stations[st]+=1
            n_obs += sum(1 for st,sec,tof in ranges)
        pass_starts.sort()
        all_dates[sat]=set(t.date() for t in pass_starts)
        summary[sat]={
            'downloaded_months':len(downloads),
            'missing_months':len(misses),
            'missing':misses,
            'pass_headers_in_window':len(pass_starts),
            'range_records_total_downloads':n_obs,
            'unique_stations_in_window':len(stations),
            'first_pass':pass_starts[0].isoformat() if pass_starts else None,
            'last_pass':pass_starts[-1].isoformat() if pass_starts else None,
            'top_stations':stations.most_common(12),
        }
    overlap=sorted(all_dates['lares2'] & all_dates['lageos1'])
    tests={
        'lares2_monthly_data_downloaded':summary['lares2']['downloaded_months']>=30,
        'lageos1_monthly_data_downloaded':summary['lageos1']['downloaded_months']>=30,
        'lares2_multistation':summary['lares2']['unique_stations_in_window']>=5,
        'lageos1_multistation':summary['lageos1']['unique_stations_in_window']>=5,
        'temporal_overlap_days_ge_100':len(overlap)>=100,
        'lares2_has_many_passes':summary['lares2']['pass_headers_in_window']>=100,
        'lageos1_has_many_passes':summary['lageos1']['pass_headers_in_window']>=100,
    }
    ready=all(tests.values())
    result={
        'schema':'ckk.external.satellite-raw-ingest.v1',
        'status':'RAW_ILRS_DATA_READY_FOR_OD' if ready else 'RAW_ILRS_DATA_NOT_READY',
        'window':{'start':START.isoformat(),'end':END.isoformat(),'days':1050},
        'satellites':summary,
        'overlap_days':len(overlap),
        'first_overlap_day':overlap[0].isoformat() if overlap else None,
        'last_overlap_day':overlap[-1].isoformat() if overlap else None,
        'tests':tests,
        'claim_boundary':'This is a raw-data readiness test only. CRDv2 normal points are light-time observations, not frame-dragging residuals. A discovery claim requires full precision orbit determination and held-out residual analysis with predeclared nuisance models.',
        'next_required_stage':'Fit orbit/force nuisance model on training arcs for one satellite or subset, freeze it, then evaluate held-out arcs and the second satellite for a common orientation-sensitive residual.'
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,indent=2,sort_keys=True))
    raise SystemExit(0 if ready else 2)

if __name__=='__main__': main()
