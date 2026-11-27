"""Permit one verified negative-net settlement while retaining every other protected payroll column."""
import hashlib


ORIGINAL = "f1a5e86ecc12eee03babf050997a2d52f66b93ecc3d899b0b260baa6eb9a337b"
MARKER = "        old_values := to_jsonb(OLD);"
SETTLEMENT = """
        IF OLD.has_negative_net_to_report IS TRUE AND NEW.has_negative_net_to_report IS FALSE
           AND OLD.state IN ('done','paid')
           AND (to_jsonb(OLD) - ARRAY['has_negative_net_to_report','write_uid','write_date'])
             = (to_jsonb(NEW) - ARRAY['has_negative_net_to_report','write_uid','write_date'])
           AND OLD.id = ANY(string_to_array(nullif(current_setting('steps.negative_net_sources',true),''),',')::integer[])
           AND EXISTS (SELECT FROM public.ir_module_module WHERE name='step_payroll_oca_sys_history'
                        AND state='installed' AND latest_version ~ '^[0-9]+([.][0-9]+)+$'
                        AND string_to_array(latest_version,'.')::integer[] >= ARRAY[18,0,1,6,3])
           AND EXISTS (
               SELECT FROM public.hr_payslip_input i
               JOIN public.hr_payslip target ON target.id=i.payslip_id
               JOIN public.hr_payslip_input_type kind ON kind.id=i.input_type_id
               JOIN public.ir_model_data d ON d.model='hr.payslip.input.type' AND d.res_id=kind.id
                   AND d.module='hr_payroll' AND d.name='input_deduction'
               WHERE i.id=nullif(current_setting('steps.negative_net_input',true),'')::integer
                 AND txid_status(txid_current()-age(i.xmin)::bigint)='in progress'
                 AND i.create_date=i.write_date AND i.create_uid=i.write_uid
                 AND i.create_uid=NEW.write_uid AND i.amount>0 AND kind.code='DEDUCTION'
                 AND target.id<>OLD.id AND target.employee_id=OLD.employee_id AND target.company_id=OLD.company_id
                 AND target.state IN ('draft','verify') AND NOT coalesce(target.paid,false)
                 AND i.amount=(SELECT abs(sum(s.net_wage)) FROM public.hr_payslip s
                     WHERE s.employee_id=OLD.employee_id AND s.company_id=OLD.company_id AND s.state IN ('done','paid')
                       AND s.id=ANY(string_to_array(current_setting('steps.negative_net_sources',true),',')::integer[]))
           )
        THEN
            RETURN NEW;
        END IF;
"""


def migrate_guard(cr, owner=False):
    cr.execute("""SELECT p.prosrc, t.tgenabled FROM pg_proc p JOIN pg_trigger t ON t.tgfoid=p.oid
                  WHERE t.tgrelid='public.hr_payslip'::regclass AND t.tgname='steps_sys_history_guard_row'
                    AND p.oid=to_regprocedure('public.steps_sys_history_guard_hr_payslip()')""")
    row = cr.fetchone()
    if not row:
        return
    source, enabled = row
    if SETTLEMENT in source and source.count(SETTLEMENT) == 1:
        if enabled != "O" or hashlib.sha256(source.replace(SETTLEMENT, "").encode()).hexdigest() != ORIGINAL:
            raise ValueError("The remainder of the original payslip protection differs")
        return
    if enabled != "O" or source.count(MARKER) != 1 or hashlib.sha256(source.encode()).hexdigest() != ORIGINAL:
        raise ValueError("Unrecognized historical SyS payslip protection")
    if not owner:
        raise ValueError("The owner must stage the verified .6.3 protection before the Odoo upgrade")
    cr.execute("""CREATE OR REPLACE FUNCTION public.steps_sys_history_guard_hr_payslip() RETURNS trigger
                  LANGUAGE plpgsql SET search_path=pg_catalog AS %s""", (source.replace(MARKER, SETTLEMENT + MARKER),))


def migrate(cr, version):
    migrate_guard(cr)
