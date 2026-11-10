"""Read-only, bounded four-query benchmark; keep the session on its original host."""
import json,os,time,statistics
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import requests
proof=json.loads(Path(os.environ['GPS_BROWSER_PROOF']).read_text())
origin='https://'+proof['host']
cookies={'session_id':proof['session_id'],'cids':str(proof['company_id'])}
snapshot=requests.get(origin+'/steps_tracker/api/fleet/snapshot',cookies=cookies,timeout=20)
snapshot.raise_for_status()
asset=next(a for a in snapshot.json()['items'] if a['plate']==os.environ['GPS_EXPECTED_PLATE'])
end=datetime.now(ZoneInfo('America/Santiago'));start=end.replace(hour=0,minute=0,second=0,microsecond=0)
url=origin+'/steps_tracker/api/assets/'+asset['asset_id']+'/positions'
def complete(limit):
    session=requests.Session();session.cookies.update(cookies)
    params={'since':start.isoformat(),'until':end.isoformat(),'limit':limit}
    rows=set();pages=0;started=time.perf_counter()
    while True:
        response=session.get(url,params=params,timeout=20);response.raise_for_status()
        data=response.json();batch={p['id'] for p in data['items']}
        assert not rows.intersection(batch)
        rows.update(batch);pages+=1
        if not data['next_cursor']:break
        assert pages<20,'Stop at bounded load'
        params['before']=data['next_cursor']
    return {'ms':round((time.perf_counter()-started)*1000),'pages':pages,'rows':len(rows),'ids':rows}
reports={};expected=None
for limit in (500,5000):
    with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(complete,[limit]*4))
    for result in results:
        ids=result.pop('ids')
        if expected is None:expected=ids
        assert ids==expected,'Both modes must read the exact same complete history'
    reports[str(limit)]={'queries':results,'median_ms':statistics.median(r['ms'] for r in results)}
print('HISTORY_BATCH_BENCHMARK_OK '+json.dumps(reports))
