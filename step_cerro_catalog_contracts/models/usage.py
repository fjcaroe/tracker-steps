from odoo import models, _
from odoo.exceptions import ValidationError
from odoo.tools import SQL


FRUIT = {
    'step.management.fruit.category', 'step.management.fruit.class',
    'step.management.caliber.group', 'step.management.fruit.caliber',
}


class FruitMasterUsage(models.AbstractModel):
    _inherit = 'step.shared.agriculture.master'

    def _check_document_memberships(self, old):
        super()._check_document_memberships(old)
        if self._name not in FRUIT:
            return
        removed = [(record.id, tuple(old[record.id] - set(record.company_ids.ids))) for record in self]
        removed = [(master, companies) for master, companies in removed if companies]
        if not removed:
            return
        # Include stored Many2ones of the original document providers that are
        # still absent from this registry. Require the actual PostgreSQL FK,
        # original model/field identities and stored document company together.
        self.env.cr.execute('''SELECT DISTINCT t.relname, col.attname
            FROM pg_constraint k JOIN pg_class t ON t.oid=k.conrelid
            JOIN pg_attribute col ON col.attrelid=t.oid AND col.attnum=k.conkey[1]
            JOIN pg_attribute co ON co.attrelid=t.oid AND co.attname='company_id' AND NOT co.attisdropped
            JOIN ir_model m ON replace(m.model,'.','_')=t.relname AND NOT m.transient
            JOIN ir_model_fields f ON f.model_id=m.id AND f.name=col.attname AND f.ttype='many2one'
                 AND f.store AND f.relation=%s
            JOIN ir_model_fields fc ON fc.model_id=m.id AND fc.name='company_id' AND fc.store
                 AND fc.ttype='many2one' AND fc.relation='res.company'
            WHERE k.contype='f' AND cardinality(k.conkey)=1 AND k.confrelid=to_regclass(%s)
              AND t.relnamespace='public'::regnamespace''', (self._name, 'public.' + self._table))
        for table, column in self.env.cr.fetchall():
            for master, companies in removed:
                self.env.cr.execute(SQL('SELECT 1 FROM %s WHERE %s=%s AND company_id IN %s LIMIT 1',
                                        SQL.identifier(table), SQL.identifier(column), master, companies))
                if self.env.cr.fetchone():
                    raise ValidationError(_('Una empresa utiliza este maestro en documentos existentes. Conserve su asignación.'))
