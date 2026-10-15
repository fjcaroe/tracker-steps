def post_init_hook(env):
    # Classify the existing process master; never create a parallel process.
    env.cr.execute("""UPDATE step_packing_process_type SET changes_commercial_producer=true
        WHERE step_category='correction' AND lower(trim(name)) IN
        ('cambio productor','cambio de productor')""")
