"""Explicit original-FK projection after master adoption, never a compute hook.

The pre-ORM SQL preparer remains authoritative for its native-copy stage. This
API operates on real, already adopted Community masters with explicit expected
pairs. It neither adopts their identity nor changes OCA's generic M2M policy.
"""
from psycopg2 import errors, sql

from odoo import _, models
from odoo.exceptions import UserError


STRUCTURE_FIELDS = ['rule_ids', 'parent_id', 'company_id', 'country_id']
RULE_FIELDS = ['struct_id', 'parent_rule_id', 'active', 'sequence', 'code', 'category_id', 'company_id']


def _expected(values, structure_ids):
    if not isinstance(values, (list, tuple)):
        raise UserError(_("Supply the original explicit structure/rule pairs before projection."))
    result, seen_rules = set(), set()
    for row in values:
        if (not isinstance(row, (list, tuple)) or len(row) != 2
                or any(type(ident) is not int or not 0 < ident < 2**31 for ident in row)):
            raise UserError(_("Original rule projection requires existing integer identities."))
        structure, rule = row
        if structure not in structure_ids or tuple(row) in result or rule in seen_rules:
            raise UserError(_("Original rule projection must name exactly one selected primary structure per rule."))
        result.add(tuple(row))
        seen_rules.add(rule)
    return result


class Structure(models.Model):
    _inherit = 'hr.payroll.structure'

    def _step_original_rule_projection_plan(self, expected_pairs):
        normal = self.sudo(False).with_context(active_test=False)
        if not normal or any(type(ident) is not int or ident <= 0 for ident in normal.ids):
            raise UserError(_("Select saved original payroll structures before projection."))
        normal.check_access('read')
        normal.check_field_access_rights('read', STRUCTURE_FIELDS)
        expected = _expected(expected_pairs, set(normal.ids))
        # Reuse the complete physical primary/M2M authorization already used
        # by the genuine ownership mutators. Archived members remain included.
        direct, primary = normal._step_rule_membership_access()
        rule_ids = {rule for structure, rule in expected | direct} | {rule for rule, structure in primary}
        rules = normal.env['hr.salary.rule'].with_context(active_test=False).browse(sorted(rule_ids))
        rules.check_access('read')
        rules.check_field_access_rights('read', RULE_FIELDS)
        if set(rules.exists().ids) != rule_ids:
            raise UserError(_("Original salary rule identities are incomplete."))
        rules.flush_recordset(RULE_FIELDS)
        normal.env.cr.execute('SELECT id,struct_id FROM hr_salary_rule WHERE id=ANY(%s)', (rules.ids,))
        owner_rows = normal.env.cr.fetchall()
        owners = normal.browse(sorted({owner for ident, owner in owner_rows if owner}))
        owners.check_access('read')
        owners.check_field_access_rights('read', STRUCTURE_FIELDS)
        normal.env.cr.execute('SELECT struct_id,rule_id FROM hr_structure_salary_rule_rel WHERE rule_id=ANY(%s)', (rules.ids,))
        actual = set(normal.env.cr.fetchall()) | direct
        other_structures = normal.browse(sorted({structure for structure, rule in actual}))
        other_structures.check_access('read')
        other_structures.check_field_access_rights('read', STRUCTURE_FIELDS)
        observed = {(owner, rule) for rule, owner in owner_rows}
        if observed != expected or any(owner is None for rule, owner in owner_rows):
            raise UserError(_("Original primary rule ownership differs from the explicit source pairs; no owner is inferred."))
        if actual - expected:
            raise UserError(_("Extra or shared rule memberships diverge from the original primary projection."))
        # This is the actual existing hierarchy/cycle/ACL validator, not a
        # second hierarchy implementation. Missing direct links can be planned;
        # their exact original direct selection is checked after materializing.
        for structure in normal:
            structure._step_check_payroll_scope(normal.env.company)
            structure._step_effective_rule_scope()
        return {'structures': normal, 'rules': rules, 'expected': expected, 'actual': actual,
            'missing': expected - actual}

    def _step_check_original_rule_projection(self, expected_pairs):
        """Read-only exact admission, including archived source configuration."""
        plan = self._step_original_rule_projection_plan(expected_pairs)
        normal, rules = plan['structures'], plan['rules']
        if plan['missing']:
            raise UserError(_("Original primary rules are missing their exact Community membership."))
        # Reuse the native-required values, archived-rule/category cycles and
        # company/country contract. No financial rule is evaluated by it.
        normal._step_check_original_required_contract()
        for structure in normal:
            direct_active = rules.filtered(lambda rule: rule.active and rule.struct_id == structure)
            effective = structure._step_effective_rule_scope()['rules']
            if set(effective.ids) != set(direct_active.ids):
                raise UserError(_("Inherited rule selection diverges from the original direct primary projection."))
        return {'structure_ids': sorted(normal.ids), 'rule_ids': sorted(rules.ids),
            'pairs': [list(pair) for pair in sorted(plan['expected'])], 'memberships': len(plan['expected']),
            'projection_equivalent': True, 'source_identity_certified': False,
            'original_metadata_ttype_converted': False, 'financial_certified': False}

    def _step_materialize_original_rule_projection(self, expected_pairs):
        """Insert only explicitly missing real pairs; preserve master timestamps.

        This private adoption operation is deliberately not attached to create,
        write, copy, compute_sheet or an RPC context flag. Generic OCA optional
        owners/sharing/copy remain unchanged and are rejected only at admission.
        """
        normal = self.sudo(False).with_context(active_test=False)
        normal.check_access('write')
        normal.check_field_access_rights('write', ['rule_ids'])
        changed = False
        try:
            # Targeted master flushes below avoid a global payroll flush, and
            # explicit cache invalidation below handles savepoint rollback.
            with normal.env.cr.savepoint(flush=False):
                plan = normal._step_original_rule_projection_plan(expected_pairs)
                normal.env.cr.execute('LOCK TABLE hr_structure_salary_rule_rel IN SHARE ROW EXCLUSIVE MODE NOWAIT')
                for records in (normal, plan['rules']):
                    normal.env.cr.execute(sql.SQL('SELECT id FROM {} WHERE id=ANY(%s) ORDER BY id FOR UPDATE NOWAIT').format(
                        sql.Identifier(records._table)), (sorted(records.ids),))
                    if {row[0] for row in normal.env.cr.fetchall()} != set(records.ids):
                        raise UserError(_("Original rule projection references changed while locking."))
                normal.invalidate_recordset(STRUCTURE_FIELDS)
                plan['rules'].invalidate_recordset(RULE_FIELDS)
                plan = normal._step_original_rule_projection_plan(expected_pairs)
                missing = sorted(plan['missing'])
                if missing:
                    normal.modified(['rule_ids'], before=True)
                    normal.env.cr.execute('''INSERT INTO hr_structure_salary_rule_rel (struct_id,rule_id)
                        SELECT * FROM unnest(%s::integer[],%s::integer[]) ON CONFLICT DO NOTHING''',
                        ([structure for structure, rule in missing], [rule for structure, rule in missing]))
                    changed = True
                    normal.invalidate_recordset(['rule_ids'])
                    normal.modified(['rule_ids'])
                normal._check_primary_rule_membership()
                result = normal._step_check_original_rule_projection(expected_pairs)
                result.update(created_memberships=len(missing), master_rows_written=False,
                    payroll_read_or_recomputed=False)
                return result
        except errors.LockNotAvailable:
            raise UserError(_("Original payroll configuration is being edited. Retry the projection after that transaction finishes.")) from None
        finally:
            if changed:
                # Also discard uncommitted membership caches when a later real
                # required/ACL/constraint error rolled the savepoint back.
                normal.invalidate_recordset(['rule_ids'])
