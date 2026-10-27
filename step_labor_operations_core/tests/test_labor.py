from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import Form, TransactionCase, tagged

from ..calendar import weekly_hours
from ..hooks import adopt_legacy_records, preserve_legacy_xmlids
from ..ownership import RECORDS, MODELS, RELATIONS


@tagged('post_install', '-at_install')
class LaborOperationsCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'name':'Labor Community fixture'})
        cls.user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name':'Labor fixture operator','login':'labor-community-fixture',
            'company_id':cls.company.id,'company_ids':[Command.set(cls.company.ids)],
            'groups_id':[Command.set([cls.env.ref(g).id for g in (
                'base.group_user','hr.group_hr_user','hr_contract.group_hr_contract_manager',
                'product.group_product_pricelist','sales_team.group_sale_manager')])],
        })
        cls.scoped = cls.env(user=cls.user.id, context=dict(cls.env.context, allowed_company_ids=cls.company.ids), su=False)
        # Keep original customer counters intact even on sequences with nextval.
        for code in ('cuadrilla_propia_seq','cuadrilla_contratista_seq','registro_propia_seq','registro_contratista_seq'):
            cls.env['ir.sequence'].create({'name':'Labor fixture '+code,'code':code,'company_id':cls.company.id,'prefix':'QA'})
        cls.calendar = cls.env['resource.calendar'].create({
            'name':'Labor fixture calendar','company_id':cls.company.id,
            'attendance_ids':[Command.clear()] + [Command.create({
                'name':'Morning','dayofweek':str(d),'day_period':'morning','hour_from':8,'hour_to':16,
            }) for d in range(5)],
        })
        cls.employee = cls.scoped['hr.employee'].create({'name':'Labor fixture employee',
            'company_id':cls.company.id,'is_propio':True})
        cls.contract = cls.scoped['hr.contract'].create({'name':'Labor fixture contract',
            'employee_id':cls.employee.id,'company_id':cls.company.id,'date_start':'2026-01-01',
            'resource_calendar_id':cls.calendar.id,'wage':800000})

    def crew(self, kind='propio'):
        return self.scoped['hr.salary.custom'].create({'name':'Community crew','group_type':kind,
            'company_id':self.company.id,'salary_line':[Command.create({
                'employee_id':self.employee.id,'contract_id':self.contract.id,'hours':8})] if kind=='propio' else []})

    def tarja(self):
        crew = self.crew()
        return self.scoped['step.tarja'].create({'salary_id':crew.id,'tarja_type':'propio',
            'date':'2026-10-27','company_id':self.company.id,'tarja_line':[Command.create({
                'employee_id':self.employee.id,'contract_id':self.contract.id,'hrs':4,'hrs_extra':1})]})

    def test_original_ids_and_idempotence(self):
        for name in RECORDS:
            self.assertEqual(self.env.ref('step_hr.'+name),self.env.ref('step_labor_operations_core.'+name),name)
        before={name:self.env.ref('step_hr.'+name).id for name in RECORDS}
        adopt_legacy_records(self.env); preserve_legacy_xmlids(self.env)
        self.assertEqual(before,{name:self.env.ref('step_hr.'+name).id for name in RECORDS})

    def test_crew_form_defaults_sequences_and_real_contract(self):
        with Form(self.scoped['hr.salary.custom'].with_context(step_default_propio=True),
                  view='step_hr.view_hr_salary_custom_form') as form:
            form.name='Own fixture crew'
        self.assertTrue(form.record.name.startswith('QA'))
        self.assertEqual(form.record.group_type,'propio')
        crew=self.crew(); self.assertEqual(crew.salary_line.contract_id,self.contract)
        self.assertEqual(crew.salary_line.employee_id,self.employee)

    def test_native_contract_cost_inputs_and_weekly_hours(self):
        self.assertEqual(weekly_hours(self.calendar),40)
        self.assertEqual(self.contract.sueldo_base,800000)
        self.assertAlmostEqual(self.contract.cost_hora,self.contract.total_cost/160)
        self.assertTrue(self.contract.get_view(self.env.ref('step_hr.step_view_hr_contract_form').id,'form')['arch'])

    def test_community_weekly_hours_excludes_lunch_and_sections(self):
        # Exercise the native branch even in the Enterprise compatibility copy.
        calendar=self.calendar
        self.env['resource.calendar.attendance'].create({'name':'Lunch','calendar_id':calendar.id,
            'dayofweek':'0','day_period':'lunch','hour_from':12,'hour_to':13})
        class NativeCalendar:
            _fields={}
            attendance_ids=calendar.attendance_ids
            two_weeks_calendar=False
            flexible_hours=False
            full_time_required_hours=32
            def ensure_one(self): return self
        self.assertEqual(weekly_hours(NativeCalendar()),40)
        NativeCalendar.two_weeks_calendar=True
        self.assertEqual(weekly_hours(NativeCalendar()),20)
        NativeCalendar.flexible_hours=True
        self.assertEqual(weekly_hours(NativeCalendar()),32)

    def test_tarja_costs_and_accounted_values_are_not_recomputed(self):
        tarja=self.tarja(); line=tarja.tarja_line
        self.assertEqual(line.hrs_total,5)
        self.assertGreaterEqual(line.cost_empresa,0)
        tarja.action_auto(); tarja.action_costeo(); self.assertEqual(tarja.state,'costo')
        original=line.read(['hrs_total','total_trato','cost_empresa','cost_sueldo'])[0]
        # A historical accounted tarja retains the legacy frozen computations.
        tarja.state='conta'; line.hrs=6
        self.assertEqual(line.read(['hrs_total','total_trato','cost_empresa','cost_sueldo'])[0],original)

    def test_portal_has_no_access_to_original_labor_models(self):
        portal=self.env['res.users'].create({'name':'Labor portal fixture','login':'labor-portal-fixture',
            'groups_id':[Command.set(self.env.ref('base.group_portal').ids)]})
        for model in MODELS:
            with self.subTest(model=model),self.assertRaises(AccessError):
                self.env[model].with_user(portal).check_access('read')

    def test_optional_payroll_fields_and_controls_stay_in_bridge(self):
        installed=self.env['ir.module.module'].search_count([('name','=','step_hr'),('state','=','installed')])
        self.assertEqual('payslip_run_id' in self.env['hr.salary.custom']._fields,bool(installed))
        self.assertEqual('struct_id' in self.env['hr.salary.custom']._fields,bool(installed))
        arch=self.env['step.tarja'].get_view(self.env.ref('step_hr.view_step_tarja_form').id,'form')['arch']
        self.assertEqual('name="envio_nomina"' in arch,bool(installed))

    def test_sequence_customizations_survive_adoption(self):
        sequence=self.env.ref('step_hr.seq_cuadrilla_propia')
        sequence.write({'prefix':'CUSTOM/','padding':9})
        before=sequence.number_next_actual
        adopt_legacy_records(self.env); preserve_legacy_xmlids(self.env)
        self.assertEqual(sequence.prefix,'CUSTOM/');self.assertEqual(sequence.padding,9)
        self.assertEqual(sequence.number_next_actual,before)

    def test_rate_form_and_contractor_cost_keep_actual_product_relations(self):
        labor=self.env['product.template'].create({'name':'Labor rate fixture','is_labor':True})
        unit=self.env.ref('uom.product_uom_unit')
        with Form(self.scoped['product.pricelist'].with_context(step_default_contratista=True),
                  view='step_hr.step_pricelist_view_inherit') as form:
            form.name='Contractor rate fixture'
            with form.item_ids.new() as item:
                item.display_applied_on='1_product'
                item.product_tmpl_id=labor
                item.labor_id=labor
                item.uom_id=unit
                item.compute_price='fixed'
                item.fixed_price=20
        rate=form.record
        self.assertEqual(rate.item_ids.labor_id,labor)
        self.assertEqual(rate.item_ids.uom_id,unit)
        with Form(self.scoped['product.pricelist.item'].with_context(default_pricelist_id=rate.id),
                  view='step_hr.product_pricelist_item_form_inherit_step') as standalone:
            standalone.display_applied_on='1_product'
            standalone.product_tmpl_id=labor
            standalone.labor_id=labor
            standalone.uom_id=unit
            standalone.compute_price='fixed'
            standalone.fixed_price=20
        partner=self.env['res.partner'].create({'name':'Contractor rate fixture','step_contra':True})
        self.employee.write({'is_contratista':True,'contratista_id':partner.id})
        crew=self.crew('contratista')
        tarja=self.scoped['step.tarja'].create({'tarja_type':'contratista','salary_id_contrac':crew.id,
            'partner_id':partner.id,'company_id':self.company.id,'date':'2026-10-27','pricelist_id':rate.id,
            'tarja_cost_line':[Command.create({'employee_id':self.employee.id,'labor_id':labor.id,'quantity':3})]})
        line=tarja.tarja_cost_line
        self.assertEqual(line.labor_id,labor)
        self.assertEqual(line.uom_id,unit)
        self.assertEqual(line.tarifa,20)
        self.assertEqual(line.trato_total,60)

    def test_relation_metadata_owner_preserves_ids_and_is_idempotent(self):
        data=self.env['ir.model.relation'].search([('name','in',RELATIONS)])
        before={row.id:(row.name,row.model.id,row.module.id) for row in data}
        legacy=self.env['ir.module.module'].search([('name','=','step_hr')])
        self.assertFalse(data.filtered(lambda row:row.module==legacy))
        adopt_legacy_records(self.env)
        self.assertEqual(before,{row.id:(row.name,row.model.id,row.module.id) for row in data})

    def test_conflicting_alias_aborts(self):
        alias=self.env['ir.model.data'].search([('module','=','step_labor_operations_core'),('name','=','action_step_tarja')])
        alias.res_id=self.env.ref('step_labor_operations_core.action_hr_salary_custom').id
        with self.assertRaises(UserError):adopt_legacy_records(self.env)
