"""Compare the stored and runtime workday inputs with the emitted field 93 on private SyS."""

from collections import Counter
from datetime import date
from types import SimpleNamespace

from odoo import api
from odoo.http import Response, _request_stack


def run(shell):
    if shell.cr.dbname not in ('MANAGEMENT_QA_SYS_PREVIRED_20261126U40N','COMMUNITY_SYS_PREVIRED_COHORT_20261126U40I',
                               'COMMUNITY_SYS_PREVIRED_COHORT_20261126U40J'):
        raise ValueError('A reviewed private SyS export database is required')
    env = api.Environment(shell.cr,2,dict(uid=2,lang='es_CL',allowed_company_ids=[7]))
    assert not env.su and 7 in env.user.company_ids.ids and env.user.has_group('hr_payroll.group_hr_payroll_manager')
    env['ir.http'].routing_map()
    req = SimpleNamespace(env=env, make_response=Response, update_env=lambda **kw: None)
    _request_stack.push(req)
    try:
        cal = env['resource.calendar']
        names = ('full_time_required_hours','hours_per_week','previred_workday_type')
        fields = {n: (str(cal._fields[n].compute),cal._fields[n].store,cal._fields[n]._module)
                  if n in cal._fields else None for n in names}
        wizard = env['step.previred.export.wizard'].create(dict(company_id=7,date_from=date(2026,10,1),
            date_to=date(2026,10,31),allow_without_department=True,scope='consolidated',output='txt'))
        dataset = wizard._build()
        by_calendar = {}
        for record in dataset.records:
            slip = env['hr.payslip'].browse(record.payslip_id)
            slip.check_access('read')
            obj = slip.contract_id.resource_calendar_id
            obj.check_access('read')
            if obj.id not in by_calendar:
                by_calendar[obj.id] = {'read':{n:getattr(obj,n,None) for n in names},
                                        'principals':Counter(),'annexes':Counter()}
            by_calendar[obj.id]['principals'][record.principal[92]] += 1
            by_calendar[obj.id]['annexes'].update(row[92] for row in record.annexes)
        return {'fields':fields,'results':by_calendar}
    finally:
        _request_stack.pop()
        shell.cr.rollback()
