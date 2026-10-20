"""Retain already-canonical fruit FKs while Odoo loads an older base definition.

The installed unification addon overrides the base fields later in the graph.
During an inventory upgrade Odoo otherwise briefly requests legacy targets.
This adapter changes only those pending requests for existing validated FKs;
it never drops constraints, remaps IDs, copies masters or weakens validation.
It is installed only in the short-lived Cerro upgrade/verification process.
"""
CANONICAL = 'step_management_fruit_category'
LEGACY = {
    ('stock_picking','fruit_category_id'):'step_packing_fruit_category',
    ('stock_picking','fruit_class_id'):'step_packing_fruit_class',
    ('step_packing_picking_tag_line','category_id'):'step_packing_fruit_category',
    ('step_producer_purchase_contract_product','category_id'):'step_packing_fruit_category',
}


def retained_spec(key, specification, existing):
    if specification[0] != LEGACY.get(key):
        return specification
    if any(target==CANONICAL for target,valid in existing):
        assert existing==[(CANONICAL,True)], 'Canonical fruit FK must be unique and validated'
        return (CANONICAL,*specification[1:])
    return specification


def install():
    import logging
    from odoo.modules.registry import Registry
    original=Registry.check_foreign_keys
    if getattr(original,'_steps_preserve_fruit_fks',False):
        return
    logger=logging.getLogger(__name__)

    def check_foreign_keys(registry,cr):
        candidates=[key for key,value in registry._foreign_keys.items()
                    if key in LEGACY and value[0]==LEGACY[key]]
        if candidates:
            cr.execute("SELECT 1 FROM ir_module_module WHERE name='step_fruit_category_unification' AND state='installed'")
            if cr.fetchone():
                for key in candidates:
                    cr.execute('SELECT target.relname,c.convalidated FROM pg_constraint c '
                        'JOIN pg_class source ON source.oid=c.conrelid '
                        'JOIN pg_class target ON target.oid=c.confrelid '
                        'JOIN pg_attribute a ON a.attrelid=source.oid AND a.attnum=ANY(c.conkey) '
                        "WHERE c.contype='f' AND source.relname=%s AND a.attname=%s",key)
                    before=registry._foreign_keys[key]
                    after=retained_spec(key,before,cr.fetchall())
                    if after!=before:
                        registry._foreign_keys[key]=after
                        logger.info('Retaining validated canonical fruit relationship %s.%s',*key)
        return original(registry,cr)

    check_foreign_keys._steps_preserve_fruit_fks=True
    Registry.check_foreign_keys=check_foreign_keys
