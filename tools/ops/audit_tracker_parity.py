"""Read-only inventory of effective Tracker web/mobile/addons on odoo-new.

Output has versions, hashes, module/menu metadata and aggregate counts only.
Never returns credentials, raw GPS frames, phone numbers or device identifiers.
"""
import ast
import configparser
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.request import urlopen
from urllib.parse import urljoin,urlsplit

ENVIRONMENTS={
 'development':('/etc/dev_odoo18.conf','LAB_TAREAS','desarrollo.stepsapp.cl'),
 'demo':('/etc/demo_odoo18.conf','STEPS_DEMO','demo.stepsapp.cl'),
 'cerro':('/etc/odoo18-cerroelplomo.conf','CERRO_EL_PLOMO','cerroelplomo.stepsapp.cl'),
 'qa-cerro':('/etc/odoo18-qa-cerroelplomo.conf','QA-CERROELPLOMO','qa-cerroelplomo.stepsapp.cl'),
 'steps':('/etc/odoo18.conf','karo_consultorias','stepsapp.cl'),
}


def query(db,sql):
 return subprocess.check_output(['sudo','-u','postgres','psql','-v','ON_ERROR_STOP=1','-At','-d',db],input=sql,text=True).strip()


def rows(db,sql):return json.loads(query(db,"SELECT COALESCE(json_agg(result),'[]'::json) FROM ("+sql+") result"))


def digest(value):return hashlib.sha256(value).hexdigest()


def sources(root):
 files={str(p.relative_to(root)):digest(p.read_bytes().replace(b'\r\n',b'\n')) for p in sorted(root.rglob('*')) if p.is_file() and p.suffix in ('.py','.xml','.js','.ts','.tsx','.css','.scss','.csv','.json') and '__pycache__' not in p.parts}
 return {'sha256':digest(json.dumps(files,sort_keys=True).encode()),'files':files}


def frontend(host,path):
 result={'url':'https://'+host+path}
 try:
  with urlopen(result['url'],timeout=20) as response:
   raw=response.read();result.update(status=response.status,final_url=response.url,html_sha256=digest(raw))
  html=raw.decode('utf-8');assets=re.findall(r'(?:src|href)=["\']([^"\']+\.(?:js|css))["\']',html)
  result['assets']={}
  for asset in assets:
   url=urljoin(result['url'],asset)
   if urlsplit(url).hostname!=host:continue
   with urlopen(url,timeout=20) as response:result['assets'][urlsplit(url).path]=digest(response.read())
  result['title']=re.search(r'<title>(.*?)</title>',html,re.S).group(1) if '<title>' in html else None
 except Exception as exc:result['error']=type(exc).__name__
 return result


def main():
 result={'environments':{},'services':{},'api':{},'gps_counts':[]}
 for name,(conf,db,host) in ENVIRONMENTS.items():
  cfg=configparser.ConfigParser(interpolation=None);cfg.read(conf);opts=cfg['options']
  assert db in opts.get('db_name',db).split(',')
  addon_roots=[Path(p.strip()) for p in opts['addons_path'].split(',')]
  item={'database':db,'host':host,'port':opts.get('http_port'),'modules':rows(db,"SELECT name,state,latest_version FROM ir_module_module WHERE (name ILIKE '%tracker%' OR name ILIKE '%truck%' OR name ILIKE '%mobile%' OR name='step_hr') ORDER BY name")}
  for module in item['modules']:
   for root in addon_roots:
    path=root/module['name'];manifest=path/'__manifest__.py'
    if manifest.exists():
     metadata=ast.literal_eval(manifest.read_text())
     module.update(source=str(path),manifest_version=metadata.get('version'),depends=metadata.get('depends'),**sources(path));break
  item['menus']=rows(db,"SELECT d.module,d.name xml_id,m.name,m.active,m.parent_id,m.action FROM ir_model_data d JOIN ir_ui_menu m ON m.id=d.res_id WHERE d.model='ir.ui.menu' AND (d.module ILIKE '%tracker%' OR d.module ILIKE '%truck%') ORDER BY d.module,d.name")
  item['url_actions']=rows(db,"SELECT d.module,d.name xml_id,a.url,a.target FROM ir_model_data d JOIN ir_act_url a ON a.id=d.res_id WHERE d.model='ir.actions.act_url' AND (d.module ILIKE '%tracker%' OR d.module ILIKE '%truck%') ORDER BY d.module,d.name")
  item['gps_model_metadata']=rows(db,"SELECT model,name,state FROM ir_model WHERE model ILIKE '%gps%' OR model ILIKE '%coban%' OR model ILIKE '%tracker%' OR model ILIKE '%truck%' OR name::text ILIKE '%Coban%' ORDER BY model")
  item['hardware_field_metadata']=rows(db,"SELECT model,name,ttype,state FROM ir_model_fields WHERE name ILIKE '%imei%' OR name ILIKE '%coban%' OR name ILIKE '%gps%' OR field_description::text ILIKE '%Coban%' ORDER BY model,name")
  item['coban_view_metadata']=rows(db,"SELECT name,model,active FROM ir_ui_view WHERE arch_db::text ILIKE '%coban%' ORDER BY name")
  item['web']=frontend(host,'/web_tracker/');item['mobile']=frontend(host,'/truck/')
  result['environments'][name]=item
 for service in ('tracker-steps-api','steps-truck-backend','steps-coban','teltonika-ingest','steps-tracker-signal.timer'):
  unit=service if service.endswith('.timer') else service+'.service'
  text=subprocess.check_output(['systemctl','show',unit,'-p','ActiveState','-p','SubState','-p','WorkingDirectory','-p','FragmentPath'],text=True)
  result['services'][service]=dict(line.split('=',1) for line in text.splitlines() if '=' in line)
 backend=Path('/opt/fernando_odoo18/apis/backend/tracker_py')
 result['api']['source']=sources(backend/'app')
 with urlopen('http://127.0.0.1:8000/openapi.json',timeout=10) as response:result['api']['paths']=sorted(json.load(response)['paths'])
 result['gps_counts']=rows('tracker_steps',"SELECT t.issuer,t.company_id,t.name,(SELECT count(*) FROM gps_assets a WHERE a.tenant_id=t.id) assets,(SELECT count(*) FROM gps_device_registrations r WHERE r.tenant_id=t.id) registered_gps,(SELECT count(*) FROM gps_positions p WHERE p.tenant_id=t.id) positions,(SELECT max(p.received_at) FROM gps_positions p WHERE p.tenant_id=t.id) last_position_received FROM gps_tenants t ORDER BY t.issuer,t.company_id")
 receiver=Path('/opt/steps-coban/current').resolve()
 result['coban']={'release':receiver.name,**sources(receiver/'receivers')}
 result['legacy_mobile_frontend']=sources(Path('/var/www/steps-truck-frontend'))
 print(json.dumps(result,ensure_ascii=True,indent=2))


if __name__=='__main__':main()
