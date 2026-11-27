{
    'name': 'Cerro El Plomo - Especies y cargas de fruta',
    'version': '18.0.1.0.3',
    'license': 'LGPL-3',
    'depends': [
        'step_cerro_studio_adoption',
        'step_species_tariff',
        'step_agriculture_species_pallet',
        'step_agriculture_catalogs',
        'step_agriculture_core',
    ],
    'pre_init_hook': 'adopt_views',
    'data': ['views/customizations.xml'],
    'installable': True,
}
