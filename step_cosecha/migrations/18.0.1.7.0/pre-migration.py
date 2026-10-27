def migrate(cr, version):
    cr.execute("UPDATE ir_model_data SET noupdate=true WHERE module='step_cosecha' AND model='ir.sequence' AND name IN ('seq_step_cosecha_propio','seq_step_cosecha_contra')")
