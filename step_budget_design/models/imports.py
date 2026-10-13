import base64,io,zipfile
from datetime import date
import openpyxl
from odoo import fields,models,Command,_
from odoo.exceptions import ValidationError
from odoo.addons.step_management_costs.models.budget_import import _norm,_to_float,MONTH_KEY_BY_NUMBER
from .template import season_months
from .excel import ExcelValues


def resolve(env,model,text,company=False,keys=('name',)):
    if text in (None,''):return env[model]
    domain=[]
    if company and 'company_id' in env[model]._fields:domain=['|',('company_id','=',False),('company_id','=',company.id)]
    matches=env[model].search(domain).filtered(lambda r:any(_norm(r[k])==_norm(text) for k in keys if k in r._fields))
    if len(matches)!=1:raise ValidationError(_('Maestro %(model)s: %(value)s tiene %(count)s coincidencias. Use un nombre o código único.',model=env[model]._description,value=text,count=len(matches)))
    return matches


class BudgetImport(models.Model):
    _inherit='step.management.budget.import'
    season_master_id=fields.Many2one('step.temporada',string='Temporada del maestro',check_company=True)
    version_master_id=fields.Many2one('step.management.budget.version',string='Versión del maestro',check_company=True)
    target_budget_type=fields.Selection([('agricultural','Agrícola'),('general','General')],string='Tipo presupuesto',required=True,default='agricultural')

    def _parse_row(self,row_number,mapped):
        prepared=dict(mapped)
        direct=self.target_budget_type=='general' and mapped.get('quantity') in (None,'',0,'0') and _to_float(mapped.get('amount')) is not None
        if direct:prepared.update(quantity=0,amount=0)
        vals=super()._parse_row(row_number,prepared)
        if direct:
            import hashlib
            vals.update(amount=_to_float(mapped.get('amount')),raw_quantity=str(mapped.get('quantity') or ''),raw_amount=str(mapped.get('amount')))
            content='|'.join(_norm(mapped.get(k)) for k in sorted(mapped))
            vals['line_hash']=hashlib.sha256(('%s|%s|%s'%(self.file_hash or '',row_number,content)).encode('utf-8')).hexdigest()
        return vals

    def action_import(self):
        self.ensure_one()
        # Resolve existing masters before the core importer mutates anything.
        rows=self.line_ids.filtered(lambda r:r.state=='ok')
        season=self.season_master_id or resolve(self.env,'step.temporada',self.season,self.company_id,('name','code'))
        version=self.version_master_id or resolve(self.env,'step.management.budget.version',self.budget_version,self.company_id,('name','code'))
        if not version:raise ValidationError(_('Seleccione la versión del maestro.'))
        periods=set(season_months(season))
        for row in rows:
            period=date(row.year,{v:k for k,v in MONTH_KEY_BY_NUMBER.items()}[row.month],1)
            if period not in periods:raise ValidationError(_('El año-mes importado está fuera de la temporada seleccionada.'))
        action=super().action_import()
        budget=self.budget_id
        budget.write({'season_id':season.id,'budget_version_id':version.id,'conversion_rate_type':'estimated','budget_type':self.target_budget_type})
        # Core groups by line identity; match its buckets exactly, including
        # product/units/activity, without loose name matching or guessing.
        for line in budget.line_ids:
            bucket=rows.filtered(lambda r:r.center_id==line.center_id and r.group_id==line.group_id and r.product_id==line.product_id and r.uom_id==line.uom_id and (r.raw_activity or '').strip()==(line.activity or ''))
            activity=resolve(self.env,'account.analytic.account',line.activity,self.company_id,('name','code'))
            origin=line.group_id.origin_id
            if not origin and bucket:
                aliases={'maquinaria':'Maquinarias','mano de obra':'Mano de obra','insumo agricola':'Insumos','gastos y serv':'Gastos y servicios'}
                text=aliases.get(_norm(bucket[0].raw_origin),bucket[0].raw_origin)
                origin=resolve(self.env,'step.management.budget.origin',text)
            line.write({'activity_id':activity.id,'origin_id':origin.id})
            total=sum(bucket.mapped('amount'))
            direct=not line.quantity and total
            if direct:
                # These are newly generated rows in this same transaction.
                # Recreate the entire monthly distribution atomically so the
                # core conservation guard never sees a partial new total.
                months=[]
                for month in line.month_ids:
                    match=bucket.filtered(lambda r:r.month==month.month)
                    years=set(match.mapped('year'))
                    if len(years)!=1:raise ValidationError(_('Cada mes importado debe tener un año inequívoco.'))
                    months.append({'month':month.month,'period_date':date(years.pop(),{v:k for k,v in MONTH_KEY_BY_NUMBER.items()}[month.month],1),'direct_amount':sum(match.mapped('amount'))})
                line.month_ids.unlink()
                line.write({'calculation_mode':'direct','direct_amount':total})
                self.env['step.management.budget.month'].create([dict(vals,budget_line_id=line.id) for vals in months])
                continue
            for month in line.month_ids:
                match=bucket.filtered(lambda r:r.month==month.month)
                years=set(match.mapped('year'))
                if len(years)!=1:raise ValidationError(_('Cada mes importado debe tener un año inequívoco.'))
                vals={'period_date':date(years.pop(),{v:k for k,v in MONTH_KEY_BY_NUMBER.items()}[month.month],1)}
                if direct:vals['direct_amount']=sum(match.mapped('amount'))
                month.write(vals)
        return action


class TemplateImport(models.TransientModel):
    _name='step.management.template.import.wizard'
    _description='Cargar plantilla agrícola Excel (Anexo 1.6.2.2)'
    company_id=fields.Many2one('res.company',required=True,default=lambda self:self.env.company)
    name=fields.Char(string='Nombre plantilla',required=True)
    season_id=fields.Many2one('step.temporada',string='Temporada',required=True,check_company=True)
    budget_version_id=fields.Many2one('step.management.budget.version',string='Versión',required=True,check_company=True)
    species_id=fields.Many2one('step.especie',string='Especie',required=True,check_company=True)
    variety_id=fields.Many2one('step.variedad',string='Variedad')
    export_category_id=fields.Many2one('step.management.fruit.category',string='Categoría exportación',check_company=True)
    commercial_category_id=fields.Many2one('step.management.fruit.category',string='Categoría comercial',check_company=True)
    industrial_category_id=fields.Many2one('step.management.fruit.category',string='Categoría industrial',check_company=True)
    waste_category_id=fields.Many2one('step.management.fruit.category',string='Categoría merma',check_company=True)
    file=fields.Binary(string='Archivo Excel',required=True)
    filename=fields.Char()

    def action_import(self):
        self.ensure_one()
        if self.company_id not in self.env.companies:raise ValidationError(_('Seleccione una empresa habilitada.'))
        raw=base64.b64decode(self.file)
        if len(raw)>10*1024*1024 or not (self.filename or '').lower().endswith('.xlsx'):raise ValidationError(_('Use un archivo .xlsx de hasta 10 MB.'))
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            if sum(i.file_size for i in archive.infolist())>80*1024*1024:raise ValidationError(_('El libro excede el tamaño permitido.'))
        book=openpyxl.load_workbook(io.BytesIO(raw),data_only=False,read_only=True,keep_links=False)
        data=next((s for s in book if _norm(s.title)=='datos'),None)
        distribution=next((s for s in book if _norm(s.title) in ('distribucion cantidad','distrib cantidad')),None)
        if not data or not distribution or max(data.max_row,distribution.max_row)>5000 or max(data.max_column,distribution.max_column)>100:raise ValidationError(_('El libro debe contener las hojas datos y distribución cantidad del anexo.'))
        values=ExcelValues(book);get=lambda c:values.value(data.title,c)
        shares=[];categories={}
        for row,field in ((13,'export_category_id'),(14,'commercial_category_id'),(15,'industrial_category_id'),(16,'waste_category_id')):
            percentage=float(get('C%s'%row) or 0)*100;category=self[field]
            if percentage and not category:raise ValidationError(_('Seleccione las categorías del maestro para los porcentajes del Excel.'))
            if category:shares.append(Command.create({'category_id':category.id,'percentage':percentage}));categories[row]=category
        template=self.env['step.management.budget.template'].create({'name':self.name,'company_id':self.company_id.id,'currency_id':self.company_id.currency_id.id,
            'season_id':self.season_id.id,'budget_version_id':self.budget_version_id.id,'species_id':self.species_id.id,'variety_id':self.variety_id.id,
            'base_hectares':get('B10'),'base_plants':get('B11'),'base_kg':get('B12'),'fruit_share_ids':shares})
        periods=season_months(self.season_id)
        distribution_rows={}
        for row in range(6,distribution.max_row+1):
            key=tuple(_norm(values.value(distribution.title,'%s%s'%(c,row))) for c in 'BCD')
            if key[2]:distribution_rows.setdefault(key,[]).append(row)
        for row in range(20,data.max_row+1):
            group_text=get('B%s'%row);product_text=get('D%s'%row)
            if not group_text or not product_text:continue
            group=resolve(self.env,'step.management.budget.group',group_text,self.company_id,('name','code'))
            product=resolve(self.env,'product.product',product_text,self.company_id,('name','default_code'))
            activity=resolve(self.env,'account.analytic.account',get('C%s'%row),self.company_id,('name','code'))
            basis_alias={'hectarea':'HA','hectareas':'HA','plantas':'PLANTS','jornadas':'DAYS','unidad':'UNITS','kilo':'KG','kg':'KG'}
            calculation=resolve(self.env,'step.management.budget.calculation.uom',basis_alias.get(_norm(get('E%s'%row)),get('E%s'%row)),keys=('name','code'))
            origin=group.origin_id
            if not origin:
                aliases={'maquinaria':'Maquinarias','gastos y serv':'Gastos y servicios'}
                origin=resolve(self.env,'step.management.budget.origin',aliases.get(_norm(get('A%s'%row)),get('A%s'%row)))
            uom=resolve(self.env,'uom.uom',get('H%s'%row))
            key=tuple(_norm(get('%s%s'%(c,row))) for c in 'BCD')
            matches=distribution_rows.get(key,[])
            if len(matches)!=1:raise ValidationError(_('La distribución de %(product)s debe tener una fila única.',product=product_text))
            drow=matches[0];months=[]
            for i in range(12):
                quantity=values.value(distribution.title,openpyxl.utils.get_column_letter(7+i)+str(drow)) or 0
                if i>=len(periods):
                    if quantity:raise ValidationError(_('El Excel tiene cantidades fuera de la temporada.'))
                else:months.append(Command.create({'period_date':periods[i],'quantity':quantity}))
            category=False
            if origin.flow_type=='income':
                formula=data['F%s'%row].value
                for share_row,share_category in categories.items():
                    if isinstance(formula,str) and formula.replace('$','').lstrip('=+')=='D%s'%share_row:category=share_category.id
                if not category:raise ValidationError(_('La fruta de ingreso debe referir a la categoría de la base (D13, D14 o D15).'))
            self.env['step.management.budget.template.line'].create({'template_id':template.id,'indicator':product_text,'origin_id':origin.id,
                'group_id':group.id,'activity_id':activity.id,'product_id':product.id,'uom_id':uom.id,'calculation_uom_id':calculation.id,
                'yield_quantity':1 if origin.flow_type=='income' else get('F%s'%row) or 0,'unit_price':get('G%s'%row) or 0,
                'base_quantity':get('I%s'%row) or 0,'fruit_category_id':category,'month_ids':months})
        template._validate_design()
        return {'type':'ir.actions.act_window','res_model':template._name,'res_id':template.id,'view_mode':'form'}
