"""Preserve two original payroll role identities through Odoo 18 group aliases.

Odoo's SetDefinitions admits one external name per group. This bounded adapter
normalizes only the two verified payroll pairs to an already existing core
reference; all expressions/leaves/implications and actual group IDs stay core.
"""
from odoo import api, models
from odoo.exceptions import AccessError


ROLE_PAIRS = (
    ('hr_payroll.group_hr_payroll_user', 'payroll.group_payroll_user'),
    ('hr_payroll.group_hr_payroll_manager', 'payroll.group_payroll_manager'),
)


class PayrollGroupDefinitions:
    """Public-API delegate; never edits SetDefinitions or introduces leaves."""
    __slots__ = ('_core', '_normalizations', '_blocked')

    def __init__(self, core, normalizations, blocked):
        self._core = core
        self._normalizations = normalizations
        self._blocked = frozenset(blocked)

    def _reference(self, ref):
        if ref in self._blocked:
            raise AccessError('Original payroll role alias identity requires review; no permission was inferred.')
        return self._normalizations.get(ref, ref)

    def get_id(self, ref):
        return self._core.get_id(self._reference(ref))

    def parse(self, refs, raise_if_not_found=True):
        tokens = []
        for token in refs.split(','):
            negative = token.startswith('!')
            ref = token[1:] if negative else token
            tokens.append(('!' if negative else '') + self._reference(ref))
        return self._core.parse(','.join(tokens), raise_if_not_found=raise_if_not_found)

    def __getattr__(self, name):
        return getattr(self._core, name)


def verified_role_definitions(core, rows):
    """Rows: (XML ID, model, res_id, actual group id), four fixed metadata keys."""
    aliases = {row[0]: row[1:] for row in rows}
    normalizations, blocked = {}, set()
    for original, alias in ROLE_PAIRS:
        source, target = aliases.get(original), aliases.get(alias)
        if source is None:
            # Official Community has only the upstream payroll names. Preserve
            # its original definition/API without inventing a native namespace.
            continue
        if source[0] != 'res.groups' or source[1] != source[2] or source[2] is None:
            blocked.update((original, alias))
            continue
        ident = source[2]
        if target is None or target != ('res.groups', ident, ident):
            # An invalid/new alias cannot revoke the original native role or
            # become a route to another group, even after warming core caches.
            blocked.add(alias)
            continue
        recognized = [(ref, core.get_id(ref)) for ref in (original, alias)]
        if any(value not in (None, ident) for ref, value in recognized):
            blocked.update((original, alias))
            continue
        canonical = next((ref for ref, value in recognized if value == ident), None)
        if canonical is None:
            blocked.update((original, alias))
            continue
        normalizations.update({original: canonical, alias: canonical})
    return PayrollGroupDefinitions(core, normalizations, blocked) if normalizations or blocked else core


def _queue_original_rule_group_constraint(groups):
    """Keep the original owner-side FK when only res.groups is initialized.

    Official Odoo 18 Many2many.update_db_foreign_keys proposes CASCADE for its
    owning column with force=False. The inverse res.groups.rule_groups is not
    the owner of the deletion policy on group_id: ir.rule.groups supplies the
    explicit RESTRICT. Extending res.groups alone must therefore also delegate
    the real rule field's updater, after the inverse field's queued updater.
    No schema SQL, field replacement, record or permission change is involved.
    """
    rules = groups.env['ir.rule']
    field = rules._fields['groups']
    actual = (field.type, field.comodel_name, field.relation,
        field.column1, field.column2, field.ondelete)
    expected = ('many2many', 'res.groups', 'rule_group_rel',
        'rule_group_id', 'group_id', 'restrict')
    if actual != expected:
        raise RuntimeError('Original ir.rule.groups foreign-key contract changed; initialization requires review.')
    groups.pool.post_init(field.update_db_foreign_keys, rules)


class Groups(models.Model):
    _inherit = 'res.groups'

    def init(self):
        result = super().init()
        _queue_original_rule_group_constraint(self)
        return result

    @api.model
    def _get_group_definitions(self):
        core = super()._get_group_definitions()
        # No ORM ACL lookup/recursive has_group, sudo business read, mutation or
        # cached alias map. Existing core definitions keep their standard cache;
        # these four metadata bindings are rechecked for every public boundary.
        self.env.cr.execute("SELECT d.module||'.'||d.name,d.model,d.res_id,g.id "
            "FROM ir_model_data d LEFT JOIN res_groups g ON d.model='res.groups' AND g.id=d.res_id "
            "WHERE (d.module='hr_payroll' AND d.name=ANY(%s)) "
            "OR (d.module='payroll' AND d.name=ANY(%s)) ORDER BY d.id",
            (['group_hr_payroll_user', 'group_hr_payroll_manager'], ['group_payroll_user', 'group_payroll_manager']))
        return verified_role_definitions(core, self.env.cr.fetchall())
