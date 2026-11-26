from odoo.exceptions import ValidationError


# The technical names and original XML IDs remain valid for existing views,
# filters, imports and payroll formulas.
FIELDS = (
    ('hr.employee', 'x_studio_categora_empleado', 'hr.employee.category',
     'nuevo_many2one_emplo_49ee7b2e-23c3-4629-97c9-f2e33502ca19'),
    ('hr.employee', 'x_studio_tipo_contrato', 'hr.contract.type',
     'nuevo_many2one_emplo_0991d5ad-fd5a-4075-b010-c8dfcc395bd7'),
    ('hr.contract', 'x_studio_cotizacin_obligatoria_adicional', None,
     'nuevo_decimal_employ_1d52e497-32e5-4e9d-8ab3-3d2fbdf49aa4'),
)


def adopt_fields(env):
    existing = []
    for model, name, relation, alias in FIELDS:
        cr = env.cr
        cr.execute("""
            SELECT f.id, f.state, f.ttype, f.relation, f.store, f.required, f.readonly,
                   f.related, f.compute, f.company_dependent, f.on_delete, f.domain,
                   EXISTS (SELECT FROM ir_model_fields_group_rel g WHERE g.field_id=f.id)
              FROM ir_model_fields f WHERE f.model=%s AND f.name=%s FOR UPDATE
        """, [model, name])
        row = cr.fetchone()
        cr.execute("""SELECT model,res_id FROM ir_model_data
                       WHERE module='studio_customization' AND name=%s""", [alias])
        original = cr.fetchone()
        cr.execute("""SELECT data_type,is_nullable,column_default FROM information_schema.columns
                       WHERE table_schema='public' AND table_name=%s AND column_name=%s""",
                   [model.replace('.', '_'), name])
        physical = cr.fetchone()
        if not row and not original:
            if physical:
                raise ValidationError(f'Falta la definición del campo existente {model}.{name}.')
            continue
        if not row or original != ('ir.model.fields', row[0]):
            raise ValidationError(f'Identidad de origen inesperada para {model}.{name}.')
        expected = ('manual', 'many2one' if relation else 'float', relation, True, False, False,
                    None, None, False, 'set null' if relation else None, '[]', False)
        if row[1:] != expected:
            raise ValidationError(f'La definición original de {model}.{name} cambió. Revise la migración.')
        if physical != ('integer' if relation else 'double precision', 'YES', None):
            raise ValidationError(f'Almacenamiento inesperado para {model}.{name}.')
        existing.append(row[0])
    if existing:
        if len(existing) != len(FIELDS):
            raise ValidationError('El conjunto de campos de origen de SyS está incompleto.')
        cr.execute("UPDATE ir_model_fields SET state='base' WHERE id=ANY(%s)", [existing])
