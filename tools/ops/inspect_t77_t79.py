"""T77-T79 schema inventory; never prints customer rows or credentials."""
try:
    models = ('step.export.estimate', 'step.export.estimate.line', 'step.export.estimate.week',
              'step.export.export', 'step.export.grower.discount', 'step.temporada', 'step.especie',
              'account.analytic.account', 'step.management.budget.template', 'step.management.operational.budget')
    for name in models:
        print('MODEL', name, name in env)
        if name in env:
            print('FIELDS', [(n, f.type, getattr(f, 'comodel_name', None)) for n, f in env[name]._fields.items()
                             if not n.startswith('message_')])
    print('MASTERS', env['ir.model'].search(['|','|','|',('model','ilike','fenol'),
          ('model','ilike','phenol'),('model','ilike','market'),('model','ilike','budget.version')]).mapped('model'))
    print('VERSIONS', [(m.name, m.latest_version, m.state) for m in env['ir.module.module'].search([
        ('name','in',['step_export','step_producer_estimate_revision','step_management_costs',
                     'step_management_costs_agriculture','step_management_costs_machinery','step_bpa'])])])
finally:
    env.cr.rollback()
