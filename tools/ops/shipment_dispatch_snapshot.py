"""Compare every existing dispatch type apart from T212's declared adjustments."""

ELIGIBLE = """d.active AND lower(d.name) = 'embarque'
    AND (d.step_recipient_kind IS NULL OR d.step_recipient_kind IN ('customer','shipment'))"""
DEFAULT_TYPE = """SELECT imd.res_id FROM ir_model_data imd
    JOIN step_freight_dispatch_type d ON d.id = imd.res_id
    JOIN ir_model_data main ON main.module = 'base' AND main.name = 'main_company'
    WHERE imd.module = 'step_packing_interplant' AND imd.name = 'default_shipment_dispatch_type'
    AND imd.model = 'step.freight.dispatch.type' AND d.company_id = main.res_id
    AND d.name = 'Embarque' AND d.active AND d.paga_flete = 'no'
    AND d.step_recipient_kind = 'shipment'"""


def snapshot_dispatch_type(table, row):
    if table == 'step_freight_dispatch_type':
        # Existing types keep their identity, settings and initial owner.
        eligible = ELIGIBLE.replace('d.', 't.')
        normalized = f"({row} - ARRAY['step_recipient_kind', 'write_uid', 'write_date'])"
        return f"(CASE WHEN {eligible} THEN {normalized} ELSE {row} END)", (
            f" WHERE t.id NOT IN ({DEFAULT_TYPE})")
    # The migration adds active companies only inside a single existing holding.
    # Out-of-scope, cross-holding and inactive assignments still affect the hash.
    return row, f""" WHERE NOT EXISTS (
        SELECT FROM step_freight_dispatch_type d
        JOIN res_company source ON source.id = d.company_id
        JOIN res_company assigned ON assigned.id = t.company_id
        WHERE d.id = t.dispatch_type_id AND {ELIGIBLE}
        AND assigned.active
        AND split_part(assigned.parent_path, '/', 1) = split_part(source.parent_path, '/', 1)
        AND NOT EXISTS (
            SELECT FROM step_freight_dispatch_type_company_rel existing
            JOIN res_company company ON company.id = existing.company_id
            WHERE existing.dispatch_type_id = d.id
            AND split_part(company.parent_path, '/', 1) <> split_part(source.parent_path, '/', 1)
        )
    )"""
