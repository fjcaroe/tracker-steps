{
    'name': 'Steps - Almacén CAF Community',
    'version': '18.0.1.0.0', 'license': 'LGPL-3', 'author': 'Steps Consulting',
    'depends': ['step_l10n_cl_caf_custody_core'],
    'data': ['security/caf_security.xml', 'security/ir.model.access.csv', 'views/caf_views.xml'],
    'pre_init_hook': 'check_provider_boundary',
    'post_init_hook': 'preserve_original_aliases',
    'installable': True,
}
