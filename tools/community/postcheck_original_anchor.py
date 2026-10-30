"""Actual original-cohort admission after an ordinary official Community load.

The coordinator holds the environment lease and network isolation. The native
control is another fresh restore, never a production database. No source plan
is deserialized or manufactured; both are rebuilt from its readonly SQL cursor.
"""
import json
from pathlib import Path
import re

from odoo import sql_db
from odoo.addons.step_payroll_contracts.original_benefit_cohort import (
    admit_source_benefit_cohort, admit_target_benefit_cohort)
from odoo.addons.step_payroll_contracts.original_payroll_roles import (
    OCA_ONLY_MODELS, plan_original_payroll_role_bindings,
    verify_original_payroll_role_bindings, admit_empty_oca_models_readonly_manager)
from probe_original_handover import run as probe, sealed_json


def run(env, stage, *, database, reference, capsule_sha256, identity_sha256):
    stage = Path(stage)
    assert re.fullmatch(r'MANAGEMENT_QA_CERRO_PAYROLL_API_ORIGINAL_HANDOVER_[A-Za-z0-9_]+', database)
    assert reference == database.replace('_HANDOVER_', '_REFERENCE_') and env.cr.dbname == database
    assert not (stage / 'cohort-admission.json').exists()
    capsule = sealed_json(stage / 'capsule.json', capsule_sha256)
    sealed_json(stage / 'identity-before.json', identity_sha256)
    type_ids = [json.loads(row)['id'] for row in capsule['tables']['hr_payroll_structure_type']['rows_json']]
    # This cursor observes the actual fresh native control with its original
    # installed provider. No native ORM, source rules or payslips are evaluated.
    with sql_db.db_connect(reference, readonly=True).cursor() as control:
        benefits = admit_source_benefit_cohort(control, type_ids, expected_database=reference)
        roles = plan_original_payroll_role_bindings(control, expected_database=reference)
    role_proof = verify_original_payroll_role_bindings(env.cr, roles, expected_database=database)
    benefit_proof = admit_target_benefit_cohort(env, benefits,
        expected_database=database, mode='anchored-preserved')
    manager_id = next(row[3] for row in roles.bindings if row[1] == 'group_payroll_manager')
    new_acls = []
    for name in OCA_ONLY_MODELS:
        model = env['ir.model'].search([('model', '=', name)])
        assert len(model) == 1
        assert not env['ir.model.access'].search([('model_id', '=', model.id), ('active', '=', True)])
        # Only absent-in-source, empty actual OCA models get these new
        # technical read ACLs. The source plan proved their original absence.
        env.cr.execute('SELECT count(*) FROM "' + env[name]._table + '"')
        assert env.cr.fetchone() == (0,)
        acl = env['ir.model.access'].create({'name': 'Original cohort read only: ' + name,
            'model_id': model.id, 'group_id': manager_id, 'perm_read': True,
            'perm_write': False, 'perm_create': False, 'perm_unlink': False})
        new_acls.append({'id': acl.id, 'model': name, 'existing_manager_group_id': manager_id})
    empty_models = admit_empty_oca_models_readonly_manager(env, manager_group_id=manager_id)
    actual = probe(env, str(stage / 'capsule.json'), capsule_sha256,
        str(stage / 'identity-before.json'), identity_sha256, str(stage / 'cohort-probe.json'))
    # Creation of new-only read ACLs and projection must not change one byte of
    # any original role, member/implied edge or common-model access policy.
    assert verify_original_payroll_role_bindings(env.cr, roles,
        expected_database=database) == role_proof
    assert admit_target_benefit_cohort(env, benefits,
        expected_database=database, mode='anchored-preserved') == benefit_proof
    result = {'schema': 1, 'database': database, 'native_control_database': reference,
        'source_benefits': benefits.metadata(), 'benefit_data_admission': benefit_proof,
        'original_role_policy': role_proof, 'empty_upstream_models': empty_models,
        'new_empty_model_readonly_acls': new_acls, 'actual_original_cohort_probe': actual,
        'native_control_functional_reference': False, 'all_products_operational': False,
        'financial_certified': False, 'integral_conversion': False, 'deadline_resolved': False,
        'production_changed': False}
    # The enclosing shell commits only after all observations have succeeded.
    # No module-install fixture or fake payroll record participates in this.
    return result
