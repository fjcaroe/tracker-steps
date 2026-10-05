import json
import xmlrpc.client
from pathlib import Path

cfg = json.loads((Path.home() / '.odoo/helpdesk_api.json').read_text())
url = 'https://desarrollo.stepsapp.cl'
uid = xmlrpc.client.ServerProxy(url + '/xmlrpc/2/common').authenticate(cfg.get('dev_db', 'LAB_TAREAS'), cfg['username'], cfg['api_key'], {})
print('UID', bool(uid))
if uid:
    rpc = xmlrpc.client.ServerProxy(url + '/xmlrpc/2/object')
    db = cfg.get('dev_db', 'LAB_TAREAS')
    def call(model, method, args, kw=None):
        return rpc.execute_kw(db, uid, cfg['api_key'], model, method, args, kw or {})
    names = ['step_inventory_packing', 'step_packing_operations', 'step_producers', 'step_export']
    print(json.dumps(call('ir.module.module', 'search_read', [[('name', 'in', names)]], {'fields': ['name', 'state', 'installed_version', 'latest_version']}), ensure_ascii=True))
