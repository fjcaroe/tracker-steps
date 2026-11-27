from . import ir_model_data
from odoo.addons.step_cerro_studio_adoption.ownership import adopt
from odoo.exceptions import ValidationError


LEGACY = {'process_types': 'odoo_studio_step_pac_97e5ba32-1ff6-4533-b129-64c9d7c2d13c'}


def adopt_views(env):
    adopt(env, 'step_cerro_studio_process_types', __file__, LEGACY)


def preserve_alias(env):
    view = env.ref('step_cerro_studio_process_types.process_types')
    xml_id = 'step_cerro_studio_packing.process_types'
    old = env.ref(xml_id, raise_if_not_found=False)
    if old and old != view:
        raise ValidationError('La vista de tipos de proceso del paquete anterior cambió.')
    if not old:
        env['ir.model.data']._update_xmlids([{'xml_id': xml_id, 'record': view, 'noupdate': True}])
