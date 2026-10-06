"""Versioned names for the existing freight tables, not parallel masters."""
MODELS = {
    'x_tramo_de_flete': 'step.freight.route',
    'x_modalidad_de_frio': 'step.freight.cold.mode',
    'x_tarifa_de_fletes': 'step.freight.tariff',
    'x_tarifa_de_fletes_line_57b07': 'step.freight.tariff.line',
    'x_orden_de_flete': 'step.freight.order',
    'x_orden_de_flete_line_709f3': 'step.freight.order.line',
    'x_orden_de_flete_line_72953': 'step.freight.order.cost',
    'x_contabilizacion_de_f': 'step.freight.accounting',
    'x_rastreo_camiones': 'step.freight.tracking',
    'x_tipo_despacho': 'step.freight.dispatch.type',
    'x_planificacion_de_flete': 'step.freight.plan',
    'x_planificacion_de_flete_linea': 'step.freight.plan.line',
}
FIELDS = {
    'x_name': 'name', 'x_active': 'active', 'x_studio_sequence': 'sequence',
    'x_studio_cdigo': 'code', 'x_studio_km_desde': 'km_from', 'x_studio_km_hasta': 'km_to',
    'x_studio_fundo': 'fundo_id', 'x_studio_empresa': 'legacy_company_id',
    'x_studio_lugar_desde': 'legacy_origin', 'x_studio_lugar_hasta': 'legacy_destination',
    'x_studio_fecha': 'date', 'x_studio_transportista': 'freight_carrier_id',
    'x_studio_responsable': 'responsible_id', 'x_studio_autoriza': 'approver_id',
    'x_studio_vigencia_desde': 'effective_from', 'x_studio_vigencia_hasta': 'effective_to',
    'x_studio_selection_field_8tm_1jhk3i2t3': 'tariff_state',
    'x_studio_selection_field_4ag_1jhk4c7s5': 'freight_state',
    'x_studio_one2many_field_61q_1jhk3j03r': 'tariff_line_ids',
    'x_tarifa_de_fletes_id': 'tariff_id', 'x_studio_tramo_de_flete': 'route_id',
    'x_studio_modalidad_de_fro': 'cold_mode_id', 'x_studio_modalidad_de_tarifa': 'tariff_basis',
    'x_studio_moneda': 'currency_id', 'x_studio_tarifa_flete': 'freight_rate',
    'x_studio_orden_de_flete': 'description', 'x_studio_instrucciones_del_flete': 'instructions',
    'x_studio_html_field_938_1jhk4i40k': 'legacy_instructions',
    'x_studio_orden_de_compra': 'purchase_order_id', 'x_studio_pedido_de_venta': 'sale_order_id',
    'x_studio_lista_de_tarifa_flete': 'price_list_id',
    'x_studio_one2many_field_9na_1jhk4lspn': 'detail_ids',
    'x_studio_one2many_field_8gj_1jhk6aj15': 'cost_ids',
    'x_orden_de_flete_id': 'order_id', 'x_studio_camin': 'vehicle_id',
    'x_studio_chofer': 'driver_id', 'x_studio_tramo': 'route_id',
    'x_studio_detalle_carga': 'cargo_description', 'x_studio_gua_referencia': 'delivery_reference',
    'x_studio_unidad': 'uom_id', 'x_studio_cantidad': 'quantity',
    'x_studio_tarifa': 'unit_rate', 'x_studio_valor_del_flete': 'freight_value',
    'x_studio_servicio_flete': 'service_product_id', 'x_studio_costo_flete': 'freight_cost',
    'x_studio_cuenta': 'expense_account_id',
    'x_studio_distribucin_analtica': 'legacy_distribution_model_id',
    'x_studio_modelo_distr_analtica': 'distribution_model_id',
}


def replace_tokens(text, mapping):
    import re
    pattern = r'(?<![\w])(' + '|'.join(re.escape(key) for key in sorted(mapping, key=len, reverse=True)) + r')(?![\w])'
    return re.sub(pattern, lambda match: mapping[match.group()], text)
