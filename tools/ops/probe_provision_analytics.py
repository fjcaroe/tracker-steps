"""Odoo-shell probe: preserve documents while linking an identified native account."""
import hashlib
import importlib
import json
from pathlib import Path

class RollbackCosting(Exception):
    pass

try:
    module = env['ir.module.module'].search([('name', '=', 'step_export_shipment_provision')])
    assert module.state == 'installed' and module.latest_version == '18.0.1.0.2'
    source = Path(importlib.import_module('odoo.addons.step_export_shipment_provision.models.provision').__file__)
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    assert not PARAMS['source_sha256'] or PARAMS['source_sha256'] == source_sha, 'Source differs from tested copy'
    mapping = {'season': ('step.temporada', 'cost_id', 'season_id'),
               'shipment': ('step.export.export', 'provision_analytic_account_id', 'shipment_id')}
    model, field, relation = mapping[PARAMS['dimension']]
    master = env[model].browse(PARAMS['master_id']).exists()
    account = env['account.analytic.account'].browse(PARAMS['account_id']).exists()
    assert len(master) == len(account) == 1 and account.active
    env.cr.execute('SELECT id FROM ' + master._table + ' WHERE id=%s FOR UPDATE', [master.id])
    master.invalidate_recordset()
    before = master[field].id or False
    assert before in (False, account.id), 'Existing relation changed; do not overwrite'
    records = env['step.export.shipment.provision'].search([(relation, '=', master.id)])
    assert records and all(not account.company_id or account.company_id == r.company_id for r in records)
    records._lock()
    def document_snapshot():
        env.flush_all()
        rows = []
        for table, query in [('step_export_shipment_provision', 'id IN %s'),
                             ('step_export_shipment_provision_line', 'provision_id IN %s')]:
            env.cr.execute('SELECT to_jsonb(t) FROM ' + table + ' t WHERE ' + query + ' ORDER BY id', [tuple(records.ids)])
            rows.append(env.cr.fetchall())
        return rows
    original = document_snapshot()
    master.with_context(tracking_disable=True, mail_notrack=True,
        mail_create_nosubscribe=True, mail_auto_subscribe_no_notify=True).write({field: account.id})
    journal_changes = []
    if PARAMS['journal_id']:
        journal = env['account.journal'].browse(PARAMS['journal_id']).exists()
        assert len(journal) == 1 and journal.type == 'general' and journal.default_account_id
        assert not journal.default_account_id.deprecated
        assert journal.default_account_id.account_type in ('liability_current', 'liability_non_current')
        for record in records:
            assert record.company_id == journal.company_id and record.company_id in journal.default_account_id.company_ids
            if record.journal_id != journal:
                assert record.state == 'validated' and not record.move_id and not record.journal_id.default_account_id
                previous = record.journal_id.id
                editable = record.with_context(tracking_disable=True, mail_notrack=True,
                    mail_create_nosubscribe=True, mail_auto_subscribe_no_notify=True)
                editable.action_previous_state()
                editable.write({'journal_id': journal.id})
                editable.action_validate()
                journal_changes.append({'provision_id': record.id, 'before': previous, 'after': journal.id})
    configured = document_snapshot()
    changed_ids = {change['provision_id'] for change in journal_changes}
    assert all(len(old) == len(new) for old, new in zip(original, configured)), 'Document rows changed'
    for (old,), (new,) in zip(original[1], configured[1]):
        expected, actual = dict(old), dict(new)
        if old['provision_id'] in changed_ids:
            # Native previous-state resets the pending valuation and touches
            # write metadata, while source expense values must remain exact.
            for audit in ('write_date', 'write_uid'):
                expected.pop(audit, None)
                actual.pop(audit, None)
            for snapshot_field in ('amount_company', 'amount_clp', 'amount_usd'):
                if expected.get(snapshot_field) is None and actual.get(snapshot_field) == 0:
                    expected[snapshot_field] = actual[snapshot_field]
        assert expected == actual, 'Expenses changed during configuration: ' + repr({key:(expected.get(key),actual.get(key)) for key in expected.keys()|actual.keys() if expected.get(key)!=actual.get(key)})
    for (old,), (new,) in zip(original[0], configured[0]):
        expected = dict(old)
        actual = dict(new)
        if old['id'] in changed_ids:
            expected['journal_id'] = PARAMS['journal_id']
            for audit in ('write_date', 'write_uid'):
                expected.pop(audit, None)
                actual.pop(audit, None)
        assert expected == actual, 'Unexpected provision change'
    checked = []
    for record in records:
        distribution = record._get_analytics()
        assert len(distribution) == 1 and len(next(iter(distribution)).split(',')) == 3
        if record.state == 'validated' and not record.move_id:
            try:
                with env.cr.savepoint():
                    record.action_cost()
                    assert record.state == 'costed' and all(line.expense_account_id and line.amount_company > 0 for line in record.line_ids)
                    checked.append({'provision_id': record.id, 'clp': record.amount_clp, 'usd': record.amount_usd})
                    raise RollbackCosting()
            except RollbackCosting:
                pass
    assert checked, 'No affected validated provision exercised'
    assert document_snapshot() == configured, 'Document or expense changed during costing check'
    proof = {'tested': True, 'costing_checked': True, 'applied': PARAMS['apply'],
             'source_sha256': source_sha, 'before': before, 'after': master[field].id,
             'checked': checked, 'journal_changes': journal_changes,
             'documents_preserved': True, 'version': module.latest_version}
    if PARAMS['apply']:
        env.cr.commit()
    print('PROVISION_ANALYTICS_OK ' + json.dumps(proof))
finally:
    env.cr.rollback()
