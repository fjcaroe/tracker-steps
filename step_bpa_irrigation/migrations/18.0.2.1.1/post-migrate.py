"""Promote the legacy Studio application status to a native BPA field."""


def migrate(cr, version):
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'x_aplicacion_foliar'
           AND column_name = 'x_studio_selection_field_55o_1jhkpbieg'
        """
    )
    if cr.fetchone():
        cr.execute(
            """
            UPDATE x_aplicacion_foliar
               SET state = x_studio_selection_field_55o_1jhkpbieg
             WHERE x_studio_selection_field_55o_1jhkpbieg
                   IN ('status1', 'status2', 'status3', 'Contabilizado')
            """
        )
