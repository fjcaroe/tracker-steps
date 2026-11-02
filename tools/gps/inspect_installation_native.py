"""Odoo-shell read-only inventory for a real vehicle installation; private output."""
import json,os,re
from pathlib import Path
assert env.cr.dbname=='CERRO_EL_PLOMO'
facts=json.loads(Path(os.environ['INSTALLATION_FACTS']).read_text());company=env['res.company'].browse(facts['company_id']);norm=lambda s:re.sub('[^A-Z0-9]','',(s or '').upper())
assert norm(company.vat).endswith(norm(facts['company_vat']))
brands=env['fleet.vehicle.model.brand'].search([]).filtered(lambda b:norm(b.name)==norm(facts['brand']))
fields={name:dict(type=f.type,string=str(f.string),comodel=f.comodel_name if f.type in ('many2one','one2many','many2many') else None) for name,f in env['fleet.vehicle']._fields.items() if any(word in name.lower()+' '+str(f.string).lower() for word in ('motor','engine','chasis','chassis','model_year','vin_sn','color','country','description','procedenc'))}
output=dict(company_id=company.id,company_name=company.name,brands=brands.read(['name']),models=env['fleet.vehicle.model'].search([('brand_id','in',brands.ids)]).read(['name','brand_id']),fields=fields)
Path(os.environ['INSTALLATION_RESULT']).write_text(json.dumps(output,default=str,ensure_ascii=False,indent=2));env.cr.rollback();print('INSTALLATION_NATIVE_INVENTORY_OK')
