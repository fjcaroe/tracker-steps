"""T27 QA: marcar como transportistas de fletes a los contactos que ya se usan como tales."""


def migrate(cr, version):
    cr.execute(
        """
        UPDATE res_partner SET is_freight_carrier = TRUE
         WHERE id IN (SELECT x_studio_transportista FROM x_tarifa_de_fletes WHERE x_studio_transportista IS NOT NULL
                      UNION SELECT x_studio_transportista FROM x_orden_de_flete WHERE x_studio_transportista IS NOT NULL
                      UNION SELECT transpor_id FROM res_partner WHERE transpor_id IS NOT NULL)
        """
    )
