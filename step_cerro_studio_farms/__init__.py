from . import ir_model_data
from odoo.addons.step_cerro_studio_adoption.ownership import adopt
from odoo.exceptions import ValidationError


LEGACY = {'farms': 'odoo_studio_step_fun_05371f67-0dae-476d-8fe8-d7eb8da9926f'}


def adopt_views(env):
    adopt(env, 'step_cerro_studio_farms', __file__, LEGACY)


def preserve_alias(env):
    view = env.ref('step_cerro_studio_farms.farms')
    xml_id = 'step_cerro_studio_agriculture.farms'
    old = env.ref(xml_id, raise_if_not_found=False)
    if old and old != view:
        raise ValidationError('La vista de fundos del paquete anterior cambió.')
    data = env['ir.model.data']
    if not old:
        data._update_xmlids([{'xml_id': xml_id, 'record': view, 'noupdate': True}])
