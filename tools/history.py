#!/usr/bin/env python3
"""Replays the chain archive into daily stats for the "since launch" chart.

    python3 tools/history.py archive history.json
"""
import json,sys,os,collections,datetime
D=sys.argv[1]; files=sorted(f for f in os.listdir(D) if f.endswith('.json') and f[0].isdigit())
def target(bits): e=bits>>24; m=bits&0xffffff; return m*(1<<(8*(e-3)))
DEAD='000000000000000000000000000000000000000000000000000000000000dead'
rows=[]; burned=0; txcount=0; locks=0; redeems=0; senders=set(); miners_all=set(); first_ts=None
for f in files:
    for h in json.load(open(os.path.join(D,f)))['blocks']:
        b=bytes.fromhex(h); height=int.from_bytes(b[0:4],'big'); ts=int.from_bytes(b[100:108],'big'); bits=int.from_bytes(b[108:112],'big'); miner=b[116:148].hex()
        n=int.from_bytes(b[148:152],'big'); off=152; ntx=0
        for i in range(n):
            tag=b[off:off+4]
            if tag==bytes.fromhex('c01dfeed'):
                to=b[off+36:off+68].hex(); amt=int.from_bytes(b[off+68:off+76],'big')
                if to==DEAD: burned+=amt
                senders.add(b[off+4:off+36].hex()); off+=152; ntx+=1
            elif tag==b'LOCK': locks+=1; off+=156; ntx+=1
            elif tag==b'RDM1':
                sl=int.from_bytes(b[off+84:off+86],'big'); p=off+86+sl; wc=b[p]; p+=1
                for _ in range(wc): p+=2+int.from_bytes(b[p:p+2],'big')
                redeems+=1; off=p; ntx+=1
            else: raise SystemExit(f'unknown tx at {height}')
        txcount+=ntx; miners_all.add(miner)
        rows.append((height,ts,bits,miner,ntx))
rows.sort()
print('blocks',len(rows),'first',rows[0][:2],'last',rows[-1][:2])
print('burned BRC',burned/1e8,'tx',txcount,'locks',locks,'redeems',redeems,'distinct miners ever',len(miners_all),'distinct senders',len(senders))
# daily
day=collections.OrderedDict()
for height,ts,bits,miner,ntx in rows:
    if height==0: continue
    d=datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime('%Y-%m-%d')
    x=day.setdefault(d,dict(n=0,work=0,miners=collections.Counter(),tx=0,h0=height,h1=height,tmin=ts,tmax=ts))
    x['n']+=1; x['work']+=2**256//(target(bits)+1); x['miners'][miner]+=1; x['tx']+=ntx; x['h1']=height; x['tmin']=min(x['tmin'],ts); x['tmax']=max(x['tmax'],ts)
out=[]
for d,x in day.items():
    top=x['miners'].most_common(1)[0][1]
    out.append(dict(d=d,blocks=x['n'],hr=round(x['work']/86400),miners=len(x['miners']),top=round(100*top/x['n'],1),tx=x['tx'],h0=x['h0'],h1=x['h1']))
for o in out[:3]+out[-6:]: print(o)
print(len(out),'days')
json.dump(dict(days=out,burned=burned,tx=txcount,locks=locks,redeems=redeems,minersEver=len(miners_all),archivedHeight=rows[-1][0]),open(sys.argv[2],'w'))
