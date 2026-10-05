"""Transfer metadata ownership without renaming tables, records or public XML IDs."""
import ast
from pathlib import Path

CORE_MODELS = (
    'step.export.estimate', 'step.export.estimate.line', 'step.export.estimate.week',
    'step.export.estimate.stage', 'step.export.estimate.tag',
    'step.export.grower.rate', 'step.export.grower.rate.tag',
    'step.export.grower.discount', 'step.export.grower.discount.tag',
    'step.export.producer.settlement', 'step.export.producer.settlement.line',
    'step.export.producer.settlement.discount',
)
SHARED_FIELDS = {
    'res.partner': ('step_export_packing', 'step_export_packing_type', 'step_export_fundo_ids'),
    'product.template': ('step_export_species_id',),
    'stock.package.type': ('step_export_boxes_per_pallet',),
    'product.packaging': ('step_export_kg_per_box',),
    'res.company': ('step_export_purchase_journal_id', 'step_export_purchase_account_id', 'step_export_purchase_tax_id'),
}
SEASON_MODELS = ('step.producer.season.statement', 'step.producer.season.statement.wizard')
SEASON_XMLIDS = ('sequence_season_statement', 'view_season_statement_list', 'view_season_statement_form',
    'action_season_statement', 'view_season_statement_wizard', 'action_season_statement_generate',
    'action_report_season_statement', 'report_season_statement', 'rule_season_statement_company',
    'access_season_statement_user', 'access_season_statement_account', 'access_season_statement_wizard',
    'menu_season_statement', 'menu_season_generate')


def _core_xmlids():
    tree = ast.parse((Path(__file__).parent / 'legacy_ids.py').read_text(encoding='utf-8'))
    return ast.literal_eval(next(node.value for node in tree.body if isinstance(node, ast.Assign)))


def _owned_ids(cr, module, models, xmlids, shared=False):
    cr.execute('''SELECT d.id, d.name, d.model, d.res_id, d.noupdate
          FROM ir_model_data d
         WHERE d.module=%s AND (
             d.name=ANY(%s)
             OR (d.model='ir.model' AND d.res_id IN (SELECT id FROM ir_model WHERE model=ANY(%s)))
             OR (d.model='ir.model.fields' AND d.res_id IN (
                 SELECT id FROM ir_model_fields WHERE model=ANY(%s) AND name <> 'receiver_settlement_id'))
             OR (d.model='ir.model.constraint' AND d.res_id IN (
                 SELECT c.id FROM ir_model_constraint c JOIN ir_model m ON c.model=m.id
                  WHERE m.model=ANY(%s) AND c.type='u' AND c.name NOT LIKE '%%producer_receiver_unique')))
         ORDER BY d.id''', [module, list(xmlids), list(models), list(models), list(models)])
    rows = {row[0]: row for row in cr.fetchall()}
    if shared:
        for model, names in SHARED_FIELDS.items():
            cr.execute('''SELECT d.id, d.name, d.model, d.res_id, d.noupdate
                  FROM ir_model_data d JOIN ir_model_fields f ON d.res_id=f.id
                 WHERE d.module=%s AND d.model='ir.model.fields' AND f.model=%s AND f.name=ANY(%s)''',
                       [module, model, list(names)])
            rows.update((row[0], row) for row in cr.fetchall())
    return list(rows.values())


def _transfer(cr, origin, target, rows):
    for xml_id, name, model, res_id, noupdate in rows:
        cr.execute('SELECT id, model, res_id FROM ir_model_data WHERE module=%s AND name=%s', [target, name])
        existing = cr.fetchone()
        if existing:
            if existing[1:] != (model, res_id):
                raise RuntimeError('Conflicting XML ID during producer migration: %s.%s' % (target, name))
            cr.execute('UPDATE ir_model_data SET noupdate=true WHERE id=%s', [xml_id])
        else:
            if model == 'ir.model.constraint':
                cr.execute('UPDATE ir_model_constraint SET module=(SELECT id FROM ir_module_module WHERE name=%s) WHERE id=%s', [target, res_id])
            cr.execute('UPDATE ir_model_data SET module=%s WHERE id=%s', [target, xml_id])
            cr.execute('INSERT INTO ir_model_data(module,name,model,res_id,noupdate) VALUES(%s,%s,%s,%s,true)',
                       [origin, name, model, res_id])


def transfer_ownership(cr):
    _transfer(cr, 'step_export', 'step_producers', _owned_ids(cr, 'step_export', CORE_MODELS, _core_xmlids(), True))
    _transfer(cr, 'step_producers', 'step_export', _owned_ids(cr, 'step_producers', SEASON_MODELS, SEASON_XMLIDS))
    # Preserve historical dates/scopes before these become standalone core columns.
    cr.execute("SELECT to_regclass('step_export_producer_settlement')")
    if cr.fetchone()[0]:
        for name, sql_type in (('date', 'date'), ('season_id', 'integer'), ('species_id', 'integer')):
            cr.execute('ALTER TABLE step_export_producer_settlement ADD COLUMN IF NOT EXISTS %s %s' % (name, sql_type))
        cr.execute("SELECT to_regclass('step_export_receiver_settlement')")
        if not cr.fetchone()[0]:
            return
        cr.execute('''UPDATE step_export_producer_settlement p
                         SET date=r.date, season_id=r.season_id, species_id=r.species_id
                        FROM step_export_receiver_settlement r
                       WHERE p.receiver_settlement_id=r.id
                         AND (p.date IS NULL OR p.season_id IS NULL OR p.species_id IS NULL)''')


def _alias(cr, origin, target, rows):
    for _xml_id, name, model, res_id, _noupdate in rows:
        cr.execute('SELECT model,res_id FROM ir_model_data WHERE module=%s AND name=%s', [target, name])
        existing = cr.fetchone()
        if existing and existing != (model, res_id):
            raise RuntimeError('Conflicting legacy producer alias: %s.%s' % (target, name))
        if not existing:
            cr.execute('INSERT INTO ir_model_data(module,name,model,res_id,noupdate) VALUES(%s,%s,%s,%s,true)',
                       [target, name, model, res_id])


def register_legacy_aliases(cr):
    _alias(cr, 'step_producers', 'step_export', _owned_ids(cr, 'step_producers', CORE_MODELS, _core_xmlids(), True))


def register_season_aliases(cr):
    _alias(cr, 'step_export', 'step_producers', _owned_ids(cr, 'step_export', SEASON_MODELS, SEASON_XMLIDS))
