"""Exercise original CAF attachment claims in genuine concurrent Odoo transactions."""

import base64
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
import re
from time import monotonic, sleep
from types import SimpleNamespace

from cryptography.hazmat.primitives.asymmetric import rsa
from odoo import api, Command
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import new_test_user
from psycopg2.errors import SerializationFailure

from odoo.addons.step_l10n_cl_edi_core.tests.caf_cases import CAFCaseMixin
from odoo.addons.step_l10n_cl_edi_core.tests.ted_cases import synthetic_ted


MODEL = 'l10n_cl.dte.caf'
CAF_METADATA = ('id,filename,company_id,l10n_latam_document_type_id,start_nb,final_nb,issued_date,status,'
                'create_uid,write_uid,create_date,write_date')


def synthetic_documents(first):
    keys = SimpleNamespace(signer=rsa.generate_private_key(public_exponent=65537, key_size=2048),
                           issuer_key=rsa.generate_private_key(public_exponent=65537, key_size=1024))
    raw = CAFCaseMixin.fixture(keys, first=first, last=first + 49)
    # The CAF payload contains public material only. The issuer key never leaves memory.
    return raw, base64.b64encode(synthetic_ted(raw, keys.issuer_key, folio=first)[0])


def attach(env, record_id, raw):
    return env['ir.attachment'].create({
        'name': 'SYNTHETIC_CAF_RACE.xml', 'type': 'binary', 'res_model': MODEL, 'res_id': record_id,
        'res_field': 'caf_file', 'company_id': env.company.id, 'datas': base64.b64encode(raw),
        'mimetype': 'application/xml'})


def competing_write(registry, uid, context, ident, raw, pid_queue):
    with registry.cursor() as cr:
        cr.execute("SET LOCAL lock_timeout TO '20s'")
        cr.execute('SELECT pg_backend_pid()')
        pid_queue.put(cr.fetchone()[0])
        try:
            attach(api.Environment(cr, uid, context), ident, raw)
            cr.commit()
            return 'committed'
        except SerializationFailure:
            cr.rollback()
            return 'serialization_failure'


def race(registry, uid, company_id, ident, first, winner_commits):
    one, one_ted = synthetic_documents(first)
    two, two_ted = synthetic_documents(first)
    context = {'allowed_company_ids': [company_id], 'lang': 'en_US'}
    queue = Queue()
    with ThreadPoolExecutor(max_workers=1) as executor, registry.cursor() as cr:
        cr.execute('SELECT pg_backend_pid()')
        winner_pid = cr.fetchone()[0]
        attach(api.Environment(cr, uid, context), ident, one)
        future = executor.submit(competing_write, registry, uid, context, ident, two, queue)
        try:
            contender_pid = queue.get(timeout=10)
            deadline = monotonic() + 12
            with registry.cursor() as observer:
                while True:
                    observer.execute('SELECT %s=ANY(pg_blocking_pids(%s))', (winner_pid, contender_pid))
                    if observer.fetchone()[0]:
                        break
                    if monotonic() > deadline:
                        raise AssertionError('Both independent attachment writers must contend on the same CAF')
                    sleep(0.05)
            if winner_commits:
                cr.commit()
            else:
                cr.rollback()
            outcome = future.result(timeout=12)
        finally:
            cr.rollback()
    with registry.cursor() as cr:
        env = api.Environment(cr, uid, context)
        caf = env[MODEL].browse(ident)
        rows = env['ir.attachment'].search([('res_model', '=', MODEL), ('res_id', '=', ident), ('res_field', '=', 'caf_file')])
        assert len(rows) == 1 and not rows.public and not rows.access_token
        assert caf._step_custody_original_bytes() == (one if winner_commits else two)
        ted, rejected = (one_ted, two_ted) if winner_commits else (two_ted, one_ted)
        assert caf.step_custody_check_ted_for_folio(ted)['caf_id'] == ident
        try:
            caf.step_custody_check_ted_for_folio(rejected)
        except UserError:
            pass
        else:
            raise AssertionError('A competing original must not authorize a TED')
        if winner_commits:
            assert outcome == 'serialization_failure'
            try:
                attach(env, ident, two)
            except AccessError:
                pass
            else:
                raise AssertionError('A fresh retry must reject an existing original')
        else:
            assert outcome == 'committed'
        cr.rollback()
    return outcome


def run(env):
    if not re.fullmatch(r'(?:COMMUNITY|MANAGEMENT_QA_CERRO)_CAF_RACE_[A-Z0-9]+', env.cr.dbname):
        raise ValueError('A dedicated restored CAF concurrency database is required')
    env.cr.execute("SELECT id FROM l10n_cl_dte_caf WHERE id IN (-945001,-945002)")
    assert not env.cr.fetchall(), 'Use a fresh private derivative for each rehearsal'
    env.cr.execute("SELECT last_value,is_called FROM l10n_cl_dte_caf_id_seq")
    sequence = env.cr.fetchone()
    original_query = f"SELECT {CAF_METADATA} FROM l10n_cl_dte_caf WHERE id NOT IN (-945001,-945002) ORDER BY id"
    env.cr.execute(original_query)
    original = env.cr.fetchall()
    company = env['res.company'].create({'name': 'SYNTHETIC CAF race', 'vat': '76086428-5', 'country_id': env.ref('base.cl').id})
    actor = new_test_user(env(context=dict(env.context, no_reset_password=True)), login='synthetic_caf_race_account',
                          groups='account.group_account_manager', company_id=company.id, company_ids=[Command.set(company.ids)])
    document = env['l10n_latam.document.type'].search([('country_id.code', '=', 'CL'), ('code', '=', '33')])
    document.ensure_one()
    for ident, first in ((-945001, 50), (-945002, 150)):
        env.cr.execute("""INSERT INTO l10n_cl_dte_caf
            (id,filename,company_id,l10n_latam_document_type_id,start_nb,final_nb,issued_date,status)
            VALUES (%s,%s,%s,%s,%s,%s,'2026-10-01','spent')""",
            (ident, f'SYNTHETIC_CAF_RACE_{first}.xml', company.id, document.id, first, first + 49))
    fixture_query = f"SELECT {CAF_METADATA} FROM l10n_cl_dte_caf WHERE id IN (-945001,-945002) ORDER BY id"
    env.cr.execute(fixture_query)
    baseline = env.cr.fetchall()
    env.cr.commit()
    committed = race(env.registry, actor.id, company.id, -945001, 50, True)
    rolled_back = race(env.registry, actor.id, company.id, -945002, 150, False)
    env.cr.execute(fixture_query)
    assert baseline == env.cr.fetchall()
    env.cr.execute(original_query)
    assert original == env.cr.fetchall()
    env.cr.execute("SELECT last_value,is_called FROM l10n_cl_dte_caf_id_seq")
    assert sequence == env.cr.fetchone()
    return {'both_writers_blocked_on_actual_caf': True, 'after_first_commit': committed,
            'after_first_rollback': rolled_back, 'rejected_fresh_duplicate': True, 'matching_teds_only': True,
            'original_cafs_and_sequence_preserved': True}
