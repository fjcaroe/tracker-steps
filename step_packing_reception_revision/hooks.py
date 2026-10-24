def post_init_hook(env):
    # Category and class are different masters. Keep the old category FK intact;
    # infer a class only where the same-company category has one possible class.
    env.cr.execute("""
        WITH candidates AS (
            SELECT p.id, min(c.id) AS class_id
              FROM stock_picking p JOIN step_management_fruit_class c
                ON c.category_id=p.fruit_class_id
               AND (c.company_id IS NULL OR c.company_id=p.company_id)
             WHERE p.step_fruit_reception_kind='process'
               AND p.step_fruit_origin_class_id IS NULL
             GROUP BY p.id HAVING count(*)=1
        ) UPDATE stock_picking p SET step_fruit_origin_class_id=c.class_id
            FROM candidates c WHERE p.id=c.id
    """)

    # Explicit labels/keys only: preserve every original string, including
    # unrecognized spellings, rather than guessing a historical classification.
    env.cr.execute("""
        UPDATE stock_picking SET step_fruit_type = CASE
            WHEN translate(lower(btrim(fruit_type)), 'áéíóú', 'aeiou')
                 IN ('convencional', 'conventional') THEN 'conventional'
            WHEN translate(lower(btrim(fruit_type)), 'áéíóú', 'aeiou')
                 IN ('organica', 'organico', 'organic') THEN 'organic'
            ELSE NULL END
         WHERE step_fruit_reception_kind='process' AND step_fruit_type IS NULL
    """)
