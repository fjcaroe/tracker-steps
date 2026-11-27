"""Exercise weekly hours on synthetic schedules without editing original SyS calendars."""
from odoo import api, Command


def run(shell):
    if shell.cr.dbname not in ('MANAGEMENT_QA_SYS_PREVIRED_20261126U40N','COMMUNITY_SYS_PREVIRED_COHORT_20261126U40I',
                               'COMMUNITY_SYS_PREVIRED_COHORT_20261126U40J'):
        raise ValueError('Use a restored SyS reference or private Community cohort')
    with shell.registry.cursor() as cursor:
        cursor.execute('SET TRANSACTION READ ONLY')
        return capture(cursor)


def capture(cr):
    env = api.Environment(cr,2,dict(uid=2,lang='es_CL',allowed_company_ids=[7],tracking_disable=True))
    calendar = env['resource.calendar']
    assert not env.su and 7 in env.user.company_ids.ids
    def make(name,rows,**extra):
        return calendar.new(dict(name='Synthetic '+name,company_id=7,tz='UTC',attendance_ids=[Command.clear(),
                               *(Command.create(values) for values in rows)],**extra))
    def row(day,start,end,period='morning',**extra):
        return dict(name='Synthetic attendance',dayofweek=day,hour_from=start,hour_to=end,day_period=period,**extra)
    def hours(c):
        calendar._fields['hours_per_week'].compute_value(c)
        return c.hours_per_week
    captured = {}
    field = calendar._fields['hours_per_week']
    captured['depends'] = sorted(field.get_depends(calendar)[0])
    one = make('one week',[row('0',8,12),row('0',12,13,'lunch'),row('1',9,12)])
    captured['one_week']=hours(one)
    one.attendance_ids.filtered(lambda a: a.dayofweek=='1').update({'hour_to':14})
    captured['after_edit']=hours(one)
    one.attendance_ids += env['resource.calendar.attendance'].new(
        row('3',10,13,date_from='2026-10-01',date_to='2026-11-30'))
    captured['date_limited']=hours(one)
    two = make('two weeks',[row('0',8,12,week_type='0'),row('1',8,14,week_type='1')],two_weeks_calendar=True)
    captured['two_weeks']=hours(two)
    flex = make('flexible',[],flexible_hours=True,full_time_required_hours=35)
    captured['flexible']=hours(flex)
    flex.update({'full_time_required_hours':32})
    captured['flexible_after_edit']=hours(flex)
    return captured
