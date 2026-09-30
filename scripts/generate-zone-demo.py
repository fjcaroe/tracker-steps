"""Deterministic synthetic report using the production geometry engine."""
import json
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'backend/tracker_py'))
from app.services.zone_metrics import summarize, polygon_info

start=datetime(2026,9,30,12,tzinfo=timezone.utc)
vertices=[{'lat':y,'lon':x} for x,y in [(-70.66,-33.45),(-70.65,-33.45),(-70.65,-33.44),(-70.66,-33.44)]]
zone=dict(id='demo-zone',name='Base de operaciones · ejemplo',purpose='base',color='#4d7c3d',vertices=vertices,active=True,version=1,created_at=start,updated_at=start,**polygon_info(vertices))
points=[]
for minute in range(61):
    if 39<minute<48:continue
    lon=-70.665+min(minute,20)*.0008 if minute<20 else -70.649-(minute-20)*.0006 if minute<35 else -70.658
    points.append(SimpleNamespace(recorded_at=start+timedelta(minutes=minute),lat=-33.445,lon=lon,speed_kmh=5 if minute<35 else 0,quality='gps',assignment_id='demo'))
report={'zone':zone,'asset':{'id':'demo-vehicle','name':'Camioneta de servicio · ejemplo','plate':'DEMO'},'start':start,'end':start+timedelta(hours=1),'generated_at':start+timedelta(hours=1),**summarize(vertices,points,start,start+timedelta(hours=1))}
(root/'src/demo/zone-report.json').write_text(json.dumps(report,default=lambda x:x.isoformat(),ensure_ascii=False,indent=2)+'\n',encoding='utf8')
