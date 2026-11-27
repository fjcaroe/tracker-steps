from odoo.exceptions import ValidationError

OWNER = 'step_cerro_contact_followup'
SOURCE = 'account_followup'
FIELDS = {
    'res.partner': ('followup_next_action_date','followup_responsible_id','followup_reminder_type',
                    'followup_line_id','followup_status','total_due','total_overdue'),
    'account.move.line': ('followup_line_id',),
    'account_followup.followup.line': ('name','delay','company_id','activity_default_responsible_type','id','display_name','create_uid',
                                      'create_date','write_uid','write_date'),
}


def adopt_history(env):
    source=env['ir.module.module'].search([('name','=',SOURCE)])
    if not source or source.state!='uninstalled':
        raise ValidationError('El perfil de consulta requiere el archivo original de seguimiento de cobros.')
    data=env['ir.model.data']
    refs=[]
    def add(name,model):
        row=env.ref(SOURCE+'.'+name)
        previous=env.ref(OWNER+'.'+name,raise_if_not_found=False)
        if row._name!=model or (previous and previous!=row):
            raise ValidationError('Cambió la referencia original de cobros '+name)
        refs.append(dict(xml_id=OWNER+'.'+name,record=row,noupdate=True))
        return row
    add('model_account_followup_followup_line','ir.model')
    for model,fields in FIELDS.items():
        prefix=model.replace('.','_')
        for name in fields:
            row=add('field_'+prefix+'__'+name,'ir.model.fields')
            if row.ttype=='selection':
                for option in env['ir.model.fields.selection'].search([('field_id','=',row.id)]):
                    add('selection__'+prefix+'__'+name+'__'+option.value,'ir.model.fields.selection')
    data._update_xmlids(refs)
