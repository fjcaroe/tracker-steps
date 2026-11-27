from odoo.exceptions import ValidationError


NAME = 'x_studio_compaia'
ALIAS = 'nuevo_many2one_bill__c2736a42-70d8-4a94-81a7-4c67b9b55714'


def adopt_company_field(env):
    cr = env.cr
    cr.execute("""SELECT id,state,ttype,relation,store,required,readonly,copied,company_dependent,
                         on_delete,domain,related,compute,index,field_description->>'en_US'
                  FROM ir_model_fields WHERE model='mrp.bom' AND name=%s FOR UPDATE""", [NAME])
    original = cr.fetchone()
    cr.execute("SELECT model,res_id FROM ir_model_data WHERE module='studio_customization' AND name=%s", [ALIAS])
    alias = cr.fetchone()
    cr.execute("""SELECT format_type(atttypid,atttypmod),attnotnull,atthasdef,attnum FROM pg_attribute
                  WHERE attrelid='public.mrp_bom'::regclass AND attname=%s AND NOT attisdropped""", [NAME])
    column = cr.fetchone()
    if not original and not alias and not column:
        return
    expected = ('many2one', 'res.company', True, False, False, True, False,
                'set null', '[]', None, None, False, 'Compa\u00f1ia')
    if (not original or original[1] not in ('manual', 'base') or original[2:] != expected
            or alias != ('ir.model.fields', original[0])):
        raise ValidationError('La identidad o la configuraci\u00f3n del campo de empresa de Cerro cambi\u00f3.')
    if not column or column[:3] != ('integer', False, False):
        raise ValidationError('No coincide la columna original de la lista de materiales.')
    cr.execute("""SELECT pg_get_constraintdef(oid),convalidated FROM pg_constraint
                  WHERE conrelid='public.mrp_bom'::regclass AND contype='f'
                  AND %s=ANY(conkey)""", [column[3]])
    if cr.fetchall() != [('FOREIGN KEY (x_studio_compaia) REFERENCES res_company(id) ON DELETE SET NULL', True)]:
        raise ValidationError('No coincide la referencia original a la empresa.')
    cr.execute("SELECT 1 FROM ir_model_fields_group_rel WHERE field_id=%s LIMIT 1", [original[0]])
    if cr.fetchone():
        raise ValidationError('El campo original de empresa tiene permisos adicionales.')
    if original[1] == 'base':
        cr.execute("""SELECT model,res_id FROM ir_model_data WHERE module='step_cerro_bom_company'
                      AND name='field_mrp_bom__x_studio_compaia'""")
        if cr.fetchone() != alias:
            raise ValidationError('La relación declarada en código no tiene su identidad de adopción.')
        return
    cr.execute("UPDATE ir_model_fields SET state='base' WHERE id=%s AND state='manual'", [original[0]])
