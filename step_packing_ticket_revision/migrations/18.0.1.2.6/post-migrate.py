def migrate(cr, version):
    if version:
        cr.execute('DROP INDEX IF EXISTS step_external_active_reception_folio')
