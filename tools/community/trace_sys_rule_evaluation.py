"""Observe SyS duplicate conditions, rule values and resulting lines on disposable drafts."""
from contextlib import ExitStack
from decimal import Decimal
import re
from unittest.mock import patch
from uuid import uuid4

from probe_sys_october_drafts import amounts, digest, prepare_draft, protect_existing


def number(value):
    return format(Decimal(str(value)).normalize(), 'f')


def rule_trace(rules, method, events):
    operation = getattr(type(rules), method)
    def observe(rule, *args, **kwargs):
        if rule.id == 50 and method == '_satisfy_condition':
            categories = args[0]['categories']
            events.append([rule.id, 'category_types', {
                key: type(categories.get(key)).__name__
                for key in ('GROSS','AFP','SALUD','AFC_T','STEPS_UNKNOWN_CATEGORY')}])
            missing = 'STEPS_UNKNOWN_CATEGORY'
            events.append([rule.id, 'category_fallbacks', [
                categories.get(missing), categories.get(missing, None), categories.get(missing, 42)]])
        try:
            value = operation(rule, *args, **kwargs)
        except Exception as exc:
            reasons = []
            cause = exc
            seen = set()
            while cause is not None and id(cause) not in seen:
                seen.add(id(cause))
                terms = re.findall(r"(?:has no attribute|name|KeyError:) ['\"]([A-Za-z_][A-Za-z0-9_.]*)['\"]",str(cause))
                if isinstance(cause,(NameError, AttributeError)) and getattr(cause, 'name', None):
                    terms.append(cause.name)
                if isinstance(cause,KeyError) and re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_.]*',str(cause.args[0])):
                    terms.append(str(cause.args[0]))
                if isinstance(cause,TypeError) and re.fullmatch(r"[A-Za-z0-9 _',()+*/.:-]{1,145}",str(cause)):
                    terms.append(str(cause))
                reasons.append([type(cause).__name__, sorted(set(terms))])
                cause = cause.__cause__ or cause.__context__
            events.append([rule.id, 'failed_' + method, reasons])
            raise
        if rule.code in ('MOV_7', 'NET'):
            if method == '_satisfy_condition':
                result = bool(value)
            elif isinstance(value, dict):
                result = [number(value[k]) for k in ('amount','quantity','rate')]
            else:
                result = [number(v) for v in value[:3]]
            events.append([rule.id, method, result])
        return value
    return patch.object(type(rules), method, observe)


def movement(draft):
    env = draft.env
    kind = env['hr.employee.movement.type'].browse(7)
    assert kind.exists()
    kind.check_access('read')
    label = 'STEPS_PRIVATE_' + uuid4().hex
    header = env['hr.employee.movement'].create({'name':label, 'date':draft.date_to,
                        'company_id':draft.company_id.id,'movement_type_id':kind.id})
    env['hr.employee.movement.line'].create({'name':label,'movement_id':header.id,
                                             'employee_id':draft.employee_id.id,'amount':1000})
    env.flush_all()


def check_configuration_scope(env, company, uid):
    scope = env['hr.payroll.structure'].with_user(uid).with_context(allowed_company_ids=[company])
    profile = scope.env.ref('l10n_cl_simpledigital_payroll.structure_chile')
    report = profile._step_configuration_report()
    assert not report['errors'] and report['verified_duplicate_result_ids'] == {'MOV_7':68,'NET':32}
    rules = profile._step_effective_rule_scope()['rules']
    duplicates = report['duplicate_code_ids']
    assert profile._step_verified_rule_collisions(rules,duplicates) == report['verified_duplicate_result_ids']
    # Keep the count and both duplicated codes unchanged but substitute one
    # other real rule. Its complete configuration must no longer be recognized.
    other = scope.env['hr.salary.rule'].search([('id','not in',rules.ids),('code','not in',list(duplicates))],limit=1)
    assert other
    remove = rules.filtered(lambda r: r.code not in duplicates)[:1]
    assert len(rules - remove | other)==len(rules)
    assert profile._step_verified_rule_collisions(rules - remove | other,duplicates) == {}
    alternate = (scope.env.user.company_ids - scope.env.company)[:1]
    assert alternate
    assert profile.with_company(alternate)._step_verified_rule_collisions(rules,duplicates) == {}
    assert profile._step_verified_rule_collisions(rules,dict(duplicates,UNREVIEWED=[8,32])) == {}
    return {'original_rules': len(rules), 'distinct_collisions':len(duplicates),
            'altered_rule_rejected':True,'other_company_rejected':True,'unreviewed_collision_rejected':True}


def probe(shell, company, uid, native, write_draft=False):
    assert (shell.cr.dbname == 'COMMUNITY_SYS_FINAL_RESTORED_20261127U46R' or
            re.fullmatch(r'(?:MANAGEMENT_QA_SYS_PREVIRED_|COMMUNITY_SYS_PREVIRED_COHORT_)[A-Z0-9_]+', shell.cr.dbname))
    scope = shell['hr.payslip'].with_user(uid).with_context(allowed_company_ids=[company], tracking_disable=True)
    cr = scope.env.cr
    assert not scope.env.su and scope.env.company.id == company
    assert native == bool(scope.env['ir.module.module'].sudo().search_count([('license','=','OEEL-1'),('state','=','installed')]))
    try:
        protect_existing(cr, 'hr_payslip', (('hr_payslip','id'),('hr_payslip_line','slip_id'),
                         ('hr_payslip_worked_days','payslip_id'),('hr_payslip_input','payslip_id')))
        cr.execute("""SELECT id,employee_id,contract_id,struct_id FROM hr_payslip WHERE company_id=%s
                      AND date_from='2026-10-01' AND date_to='2026-10-31' AND state IN('done','paid') ORDER BY id""",[company])
        cohort = cr.fetchall()
        assert len(cohort) == 5
        samples = []
        for case, technical in [(r, False) for r in cohort] + [(cohort[0], True)]:
            events = []
            sample = {'slip': case[0], 'synthetic_movement': technical, 'events': events}
            try:
                with cr.savepoint() as trial:
                    original, draft, stored, *_ = prepare_draft(scope,*case,day_source='stored_worked_days')
                    if technical:
                        movement(draft)
                    rules = scope.env['hr.salary.rule']
                    with ExitStack() as watch:
                        for method in ('_satisfy_condition','_compute_rule'):
                            watch.enter_context(rule_trace(rules, method, events))
                        if native or write_draft:
                            draft.compute_sheet()
                            draft.env.flush_all()
                            rows = amounts(cr,draft.id)
                        else:
                            # The OCA quotation API calculates values without writing payroll
                            # lines. Its own original-configuration checks remain in place.
                            lines = draft.get_lines_dict()
                            rows = sorted([(v['salary_rule_id'], v['code'], *(number(v[k]) for k in
                                          ('amount','quantity','rate','total'))) for v in lines.values()])
                    assert original.state in ('done','paid') and stored == amounts(cr,original.id)
                    sample.update(lines=len(rows), result_sha256=digest(rows), stored_match=rows==stored,
                                  rule_ids=[r[0] for r in rows], line_hashes={str(r[0]):digest([r]) for r in rows})
                    if not technical:
                        by_rule = {r[0]:r for r in stored}
                        sample['differences'] = {
                            r[0]: [key for key, x, y in zip(('code','amount','quantity','rate','total'),
                                                 r[1:],by_rule[r[0]][1:]) if x != y]
                            for r in rows if r[0] in by_rule and r != by_rule[r[0]]}
                    trial.rollback()
            except Exception as exc:
                # The complete message can include private formula inputs. Keep the exception
                # name and innermost method in the receipt for controlled diagnosis.
                import traceback
                sample.update(error=type(exc).__name__, call=traceback.extract_tb(exc.__traceback__)[-1].name)
                details = str(exc)
                sample['technical_names'] = re.findall(
                    r"(?:has no attribute|is not defined:|KeyError:) ['\"]([A-Za-z_][A-Za-z0-9_.]*)['\"]", details)
                sample['failed_stage'] = [frame.name for frame in traceback.extract_tb(exc.__traceback__)[-6:]]
                if type(exc).__name__ == 'UserError' and re.fullmatch(r'[A-Za-z0-9_, :./-]{1,210}', details):
                    sample['validation_message'] = details
            samples.append(sample)
        return {'native':native,'new_draft_calculated':native or write_draft,'samples':samples}
    finally:
        cr.rollback()
