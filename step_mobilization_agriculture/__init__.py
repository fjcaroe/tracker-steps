from . import models


def post_init_hook(env):
    """Repara la inconsistencia detectada en la auditoría: las tarifas de
    movilización usaban product.pricelist.partner_id (campo genérico
    'Contratista', compartido con cosecha) para filtrar el transportista,
    mientras que el campo pensado para eso (transporte_id) quedaba oculto en
    la vista. step_mobilization ahora usa transporte_id como campo operativo;
    esto copia el valor ya cargado en partner_id la primera vez, sin tocar
    partner_id (que sigue siendo de step_hr y puede seguir usándose por otros
    dominios)."""
    pricelists = env['product.pricelist'].search([
        ('moviliza', '=', True), ('transporte_id', '=', False), ('partner_id', '!=', False),
    ])
    for pricelist in pricelists:
        pricelist.transporte_id = pricelist.partner_id.id
