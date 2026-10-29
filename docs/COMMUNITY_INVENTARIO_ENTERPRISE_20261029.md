# Matriz de retiro Enterprise — Cerro, 2026-10-29

Generada con `tools/community/build_enterprise_backlog.py` desde auditoría de solo lectura.
No contiene datos de negocio, rutas de servidor ni parámetros de licencia.

Producción: 380 módulos instalados, 140 Enterprise y 99 propios.
Código candidato: 53 apps propias instaladas aún alcanzan Enterprise por sus dependencias.
Producción conserva Enterprise. Ninguna fila autoriza desinstalación ni acredita reemplazo integral.
Las columnas cuentan apps propias instaladas cuya clausura declarada alcanza cada módulo;
«código candidato» usa los manifiestos del checkout. Cero dependientes propios no significa cero uso.

| Módulo Enterprise | Familia | Apps en producción | Código candidato | Puerta de retiro |
| --- | --- | ---: | ---: | --- |
| `account_accountant` | Contabilidad / Tesorería | 55 | 41 | Pendiente de ensayo integral |
| `account_accountant_batch_payment` | Contabilidad / Tesorería | 0 | 0 | Pendiente de ensayo integral |
| `account_accountant_fleet` | Contabilidad / Tesorería | 0 | 0 | Pendiente de ensayo integral |
| `account_asset` | Contabilidad / Tesorería | 0 | 0 | Pendiente de ensayo integral |
| `account_asset_fleet` | Contabilidad / Tesorería | 0 | 0 | Pendiente de ensayo integral |
| `account_auto_transfer` | Contabilidad / Tesorería | 0 | 0 | Pendiente de ensayo integral |
| `account_bank_statement_extract` | Contabilidad / Tesorería | 0 | 0 | Pendiente de ensayo integral |
| `account_bank_statement_import` | Contabilidad / Tesorería | 0 | 0 | Pendiente de ensayo integral |
| `account_bank_statement_import_camt` | Contabilidad / Tesorería | 0 | 0 | Pendiente de ensayo integral |
| `account_bank_statement_import_csv` | Contabilidad / Tesorería | 0 | 0 | Pendiente de ensayo integral |
| `account_bank_statement_import_ofx` | Contabilidad / Tesorería | 0 | 0 | Pendiente de ensayo integral |
| `account_base_import` | Contabilidad / Tesorería | 0 | 0 | Pendiente de ensayo integral |
| `account_batch_payment` | Contabilidad / Tesorería | 2 | 2 | Pendiente de ensayo integral |
| `account_disallowed_expenses` | Contabilidad / Tesorería | 0 | 0 | Pendiente de ensayo integral |
| `account_disallowed_expenses_fleet` | Contabilidad / Tesorería | 0 | 0 | Pendiente de ensayo integral |
| `account_extract` | Contabilidad / Tesorería | 0 | 0 | Pendiente de ensayo integral |
| `account_followup` | Contabilidad / Tesorería | 0 | 0 | Pendiente de ensayo integral |
| `account_inter_company_rules` | Contabilidad / Tesorería | 0 | 0 | Pendiente de ensayo integral |
| `account_invoice_extract` | Contabilidad / Tesorería | 0 | 0 | Pendiente de ensayo integral |
| `account_invoice_extract_purchase` | Contabilidad / Tesorería | 0 | 0 | Pendiente de ensayo integral |
| `account_loans` | Contabilidad / Tesorería | 0 | 0 | Pendiente de ensayo integral |
| `account_online_synchronization` | Contabilidad / Tesorería | 0 | 0 | Pendiente de ensayo integral |
| `account_reports` | Contabilidad / Tesorería | 50 | 36 | Pendiente de ensayo integral |
| `accountant` | Contabilidad / Tesorería | 50 | 36 | Pendiente de ensayo integral |
| `analytic_enterprise` | Contabilidad / Tesorería | 0 | 0 | Pendiente de ensayo integral |
| `base_automation_hr_contract` | Personal / Nómina / Planificación | 0 | 0 | Pendiente de ensayo integral |
| `certificate` | DTE / Chile | 44 | 36 | Pendiente de ensayo integral |
| `contacts_enterprise` | Interfaz / Integraciones | 0 | 0 | Pendiente de ensayo integral |
| `currency_rate_live` | Contabilidad / Tesorería | 0 | 0 | Pendiente de ensayo integral |
| `digest_enterprise` | Interfaz / Integraciones | 0 | 0 | Pendiente de ensayo integral |
| `documents` | Documentos / Firma | 0 | 0 | Pendiente de ensayo integral |
| `documents_account` | Documentos / Firma | 0 | 0 | Pendiente de ensayo integral |
| `documents_fleet` | Documentos / Firma | 0 | 0 | Pendiente de ensayo integral |
| `documents_hr` | Documentos / Firma | 0 | 0 | Pendiente de ensayo integral |
| `documents_hr_contract` | Documentos / Firma | 0 | 0 | Pendiente de ensayo integral |
| `documents_hr_expense` | Documentos / Firma | 0 | 0 | Pendiente de ensayo integral |
| `documents_hr_holidays` | Documentos / Firma | 0 | 0 | Pendiente de ensayo integral |
| `documents_hr_payroll` | Documentos / Firma | 0 | 0 | Pendiente de ensayo integral |
| `documents_hr_recruitment` | Documentos / Firma | 0 | 0 | Pendiente de ensayo integral |
| `documents_product` | Documentos / Firma | 0 | 0 | Pendiente de ensayo integral |
| `documents_project` | Documentos / Firma | 0 | 0 | Pendiente de ensayo integral |
| `documents_project_sign` | Documentos / Firma | 0 | 0 | Pendiente de ensayo integral |
| `documents_sign` | Documentos / Firma | 0 | 0 | Pendiente de ensayo integral |
| `documents_spreadsheet` | Documentos / Firma | 0 | 0 | Pendiente de ensayo integral |
| `hr_attendance_gantt` | Personal / Nómina / Planificación | 0 | 0 | Pendiente de ensayo integral |
| `hr_contract_reports` | Personal / Nómina / Planificación | 0 | 0 | Pendiente de ensayo integral |
| `hr_contract_salary` | Personal / Nómina / Planificación | 0 | 0 | Pendiente de ensayo integral |
| `hr_contract_salary_holidays` | Personal / Nómina / Planificación | 0 | 0 | Pendiente de ensayo integral |
| `hr_contract_salary_payroll` | Personal / Nómina / Planificación | 0 | 0 | Pendiente de ensayo integral |
| `hr_contract_sign` | Personal / Nómina / Planificación | 0 | 0 | Pendiente de ensayo integral |
| `hr_expense_extract` | Personal / Nómina / Planificación | 0 | 0 | Pendiente de ensayo integral |
| `hr_expense_predict_product` | Personal / Nómina / Planificación | 0 | 0 | Pendiente de ensayo integral |
| `hr_gantt` | Personal / Nómina / Planificación | 76 | 10 | Pendiente de ensayo integral |
| `hr_holidays_contract_gantt` | Personal / Nómina / Planificación | 0 | 0 | Pendiente de ensayo integral |
| `hr_holidays_gantt` | Personal / Nómina / Planificación | 65 | 0 | Pendiente de ensayo integral |
| `hr_mobile` | Personal / Nómina / Planificación | 0 | 0 | Pendiente de ensayo integral |
| `hr_payroll` | Personal / Nómina / Planificación | 75 | 9 | Pendiente de ensayo integral |
| `hr_payroll_account` | Personal / Nómina / Planificación | 5 | 5 | Pendiente de ensayo integral |
| `hr_payroll_attendance` | Personal / Nómina / Planificación | 0 | 0 | Pendiente de ensayo integral |
| `hr_payroll_expense` | Personal / Nómina / Planificación | 5 | 5 | Pendiente de ensayo integral |
| `hr_payroll_fleet` | Personal / Nómina / Planificación | 0 | 0 | Pendiente de ensayo integral |
| `hr_payroll_holidays` | Personal / Nómina / Planificación | 0 | 0 | Pendiente de ensayo integral |
| `hr_payroll_planning` | Personal / Nómina / Planificación | 0 | 0 | Pendiente de ensayo integral |
| `hr_recruitment_extract` | Personal / Nómina / Planificación | 0 | 0 | Pendiente de ensayo integral |
| `hr_recruitment_reports` | Personal / Nómina / Planificación | 0 | 0 | Pendiente de ensayo integral |
| `hr_recruitment_sign` | Personal / Nómina / Planificación | 0 | 0 | Pendiente de ensayo integral |
| `hr_work_entry_contract_attendance` | Personal / Nómina / Planificación | 0 | 0 | Pendiente de ensayo integral |
| `hr_work_entry_contract_enterprise` | Personal / Nómina / Planificación | 76 | 10 | Pendiente de ensayo integral |
| `hr_work_entry_contract_planning` | Personal / Nómina / Planificación | 0 | 0 | Pendiente de ensayo integral |
| `hr_work_entry_contract_planning_attendance` | Personal / Nómina / Planificación | 0 | 0 | Pendiente de ensayo integral |
| `hr_work_entry_holidays_enterprise` | Personal / Nómina / Planificación | 0 | 0 | Pendiente de ensayo integral |
| `iap_extract` | Interfaz / Integraciones | 0 | 0 | Pendiente de ensayo integral |
| `l10n_cl_edi` | DTE / Chile | 44 | 36 | Pendiente de ensayo integral |
| `l10n_cl_edi_exports` | DTE / Chile | 43 | 35 | Pendiente de ensayo integral |
| `l10n_cl_edi_factoring` | DTE / Chile | 0 | 0 | Pendiente de ensayo integral |
| `l10n_cl_edi_stock` | DTE / Chile | 0 | 0 | Pendiente de ensayo integral |
| `l10n_cl_reports` | DTE / Chile | 0 | 0 | Pendiente de ensayo integral |
| `mail_enterprise` | Interfaz / Integraciones | 55 | 41 | Pendiente de ensayo integral |
| `mail_mobile` | Interfaz / Integraciones | 0 | 0 | Pendiente de ensayo integral |
| `mrp_account_enterprise` | Inventario / Fabricación | 0 | 0 | Pendiente de ensayo integral |
| `mrp_accountant` | Inventario / Fabricación | 0 | 0 | Pendiente de ensayo integral |
| `mrp_workorder` | Inventario / Fabricación | 0 | 0 | Pendiente de ensayo integral |
| `mrp_workorder_hr_account` | Inventario / Fabricación | 0 | 0 | Pendiente de ensayo integral |
| `planning` | Personal / Nómina / Planificación | 0 | 0 | Pendiente de ensayo integral |
| `planning_contract` | Personal / Nómina / Planificación | 0 | 0 | Pendiente de ensayo integral |
| `planning_holidays` | Personal / Nómina / Planificación | 0 | 0 | Pendiente de ensayo integral |
| `planning_hr_skills` | Personal / Nómina / Planificación | 0 | 0 | Pendiente de ensayo integral |
| `product_barcodelookup` | Interfaz / Integraciones | 0 | 0 | Pendiente de ensayo integral |
| `project_account_asset` | Proyectos / Ventas | 0 | 0 | Pendiente de ensayo integral |
| `project_enterprise` | Proyectos / Ventas | 0 | 0 | Pendiente de ensayo integral |
| `project_enterprise_hr` | Proyectos / Ventas | 0 | 0 | Pendiente de ensayo integral |
| `project_enterprise_hr_contract` | Proyectos / Ventas | 0 | 0 | Pendiente de ensayo integral |
| `project_enterprise_hr_skills` | Proyectos / Ventas | 0 | 0 | Pendiente de ensayo integral |
| `project_holidays` | Proyectos / Ventas | 0 | 0 | Pendiente de ensayo integral |
| `project_hr_payroll_account` | Proyectos / Ventas | 0 | 0 | Pendiente de ensayo integral |
| `project_hr_skills` | Proyectos / Ventas | 0 | 0 | Pendiente de ensayo integral |
| `purchase_mrp_workorder_quality` | Calidad | 0 | 0 | Pendiente de ensayo integral |
| `quality` | Calidad | 4 | 4 | Pendiente de ensayo integral |
| `quality_control` | Calidad | 4 | 4 | Pendiente de ensayo integral |
| `quality_control_picking_batch` | Calidad | 0 | 0 | Pendiente de ensayo integral |
| `quality_control_worksheet` | Calidad | 0 | 0 | Pendiente de ensayo integral |
| `quality_mrp` | Calidad | 0 | 0 | Pendiente de ensayo integral |
| `quality_mrp_workorder` | Calidad | 0 | 0 | Pendiente de ensayo integral |
| `quality_mrp_workorder_worksheet` | Calidad | 0 | 0 | Pendiente de ensayo integral |
| `sale_account_accountant` | Proyectos / Ventas | 0 | 0 | Pendiente de ensayo integral |
| `sale_planning` | Proyectos / Ventas | 0 | 0 | Pendiente de ensayo integral |
| `sale_purchase_inter_company_rules` | Proyectos / Ventas | 0 | 0 | Pendiente de ensayo integral |
| `sale_purchase_stock_inter_company_rules` | Proyectos / Ventas | 0 | 0 | Pendiente de ensayo integral |
| `sign` | Documentos / Firma | 0 | 0 | Pendiente de ensayo integral |
| `snailmail_account_followup` | Contabilidad / Tesorería | 0 | 0 | Pendiente de ensayo integral |
| `spreadsheet_dashboard_account_accountant` | Interfaz / Integraciones | 0 | 0 | Pendiente de ensayo integral |
| `spreadsheet_dashboard_documents` | Interfaz / Integraciones | 0 | 0 | Pendiente de ensayo integral |
| `spreadsheet_dashboard_edition` | Interfaz / Integraciones | 0 | 0 | Pendiente de ensayo integral |
| `spreadsheet_dashboard_hr_contract` | Interfaz / Integraciones | 0 | 0 | Pendiente de ensayo integral |
| `spreadsheet_dashboard_hr_payroll` | Interfaz / Integraciones | 0 | 0 | Pendiente de ensayo integral |
| `spreadsheet_dashboard_mrp_account` | Interfaz / Integraciones | 0 | 0 | Pendiente de ensayo integral |
| `spreadsheet_dashboard_purchase_stock` | Interfaz / Integraciones | 0 | 0 | Pendiente de ensayo integral |
| `spreadsheet_dashboard_stock` | Interfaz / Integraciones | 0 | 0 | Pendiente de ensayo integral |
| `spreadsheet_edition` | Interfaz / Integraciones | 4 | 4 | Pendiente de ensayo integral |
| `spreadsheet_sale_management` | Interfaz / Integraciones | 0 | 0 | Pendiente de ensayo integral |
| `stock_accountant` | Inventario / Fabricación | 0 | 0 | Pendiente de ensayo integral |
| `stock_barcode` | Inventario / Fabricación | 0 | 0 | Pendiente de ensayo integral |
| `stock_barcode_mrp` | Inventario / Fabricación | 0 | 0 | Pendiente de ensayo integral |
| `stock_barcode_picking_batch` | Inventario / Fabricación | 0 | 0 | Pendiente de ensayo integral |
| `stock_barcode_quality_control` | Calidad | 0 | 0 | Pendiente de ensayo integral |
| `stock_barcode_quality_control_picking_batch` | Calidad | 0 | 0 | Pendiente de ensayo integral |
| `stock_barcode_quality_mrp` | Calidad | 0 | 0 | Pendiente de ensayo integral |
| `stock_enterprise` | Inventario / Fabricación | 0 | 0 | Pendiente de ensayo integral |
| `stock_fleet_enterprise` | Inventario / Fabricación | 0 | 0 | Pendiente de ensayo integral |
| `web_cohort` | Interfaz / Integraciones | 0 | 0 | Pendiente de ensayo integral |
| `web_enterprise` | Interfaz / Integraciones | 56 | 45 | Pendiente de ensayo integral |
| `web_gantt` | Interfaz / Integraciones | 76 | 29 | Pendiente de ensayo integral |
| `web_grid` | Interfaz / Integraciones | 0 | 0 | Pendiente de ensayo integral |
| `web_map` | Interfaz / Integraciones | 0 | 0 | Pendiente de ensayo integral |
| `web_mobile` | Interfaz / Integraciones | 55 | 41 | Pendiente de ensayo integral |
| `web_studio` | Interfaz / Integraciones | 0 | 0 | Pendiente de ensayo integral |
| `website_documents` | Documentos / Firma | 0 | 0 | Pendiente de ensayo integral |
| `website_enterprise` | Interfaz / Integraciones | 0 | 0 | Pendiente de ensayo integral |
| `website_studio` | Interfaz / Integraciones | 0 | 0 | Pendiente de ensayo integral |
| `worksheet` | Calidad | 0 | 0 | Pendiente de ensayo integral |

## Dependencias Enterprise directas de nuestras apps

Esta lista usa producción; los puentes ya extraídos se mantienen instalados allí.

| App | Dependencias directas en producción |
| --- | --- |
| `step_account_treasury` | `account_reports` |
| `step_account_treasury_batch` | `account_batch_payment` |
| `step_accounting_multicurrency` | `account_reports` |
| `step_agricultural_branding` | `hr_work_entry_contract_enterprise` |
| `step_company_edi_readiness` | `l10n_cl_edi` |
| `step_cosecha` | `hr_holidays_gantt`, `hr_payroll`, `hr_work_entry_contract_enterprise` |
| `step_expire_database` | `web_enterprise` |
| `step_export` | `l10n_cl_edi_exports` |
| `step_export_catalog_currency` | `l10n_cl_edi_exports` |
| `step_export_client_revision` | `web_gantt` |
| `step_export_traceability` | `quality_control` |
| `step_hr` | `hr_holidays_gantt`, `hr_payroll`, `hr_work_entry_contract_enterprise` |
| `step_hr_contract_lifecycle` | `hr_payroll`, `hr_work_entry_contract_enterprise` |
| `step_hr_previred` | `hr_payroll` |
| `step_hr_remuneration_book` | `hr_payroll` |
| `step_payroll_engine_transition` | `hr_payroll` |
| `step_producer_contract_report` | `web_gantt` |
| `step_producer_estimate_report` | `web_gantt` |
| `step_qa` | `quality_control` |
| `steps_hr_payroll_correction` | `hr_payroll` |

## Apps propias con caminos Enterprise pendientes

Se cuentan las apps propias del inventario instalado, no los puentes nuevos opcionales.
«Fuente en repo» solo indica disponibilidad del manifiesto; no acredita aceptación funcional.
Los sustitutos agrícolas y HR probados no equivalen a conversión integral del destino.

| App | Caminos Enterprise | Fuente en repo |
| --- | ---: | --- |
| `step_account_treasury_batch` | 1 | Sí |
| `step_accounting_multicurrency` | 6 | Sí |
| `step_agricultural_access` | 4 | Sí |
| `step_agricultural_branding` | 3 | Sí |
| `step_agro_analytics` | 10 | Sí |
| `step_agro_traceability` | 4 | Sí |
| `step_application_profiles` | 10 | Sí |
| `step_bank_security` | 1 | Sí |
| `step_company_edi_readiness` | 2 | Sí |
| `step_company_form_restore_payroll` | 10 | Sí |
| `step_expire_database` | 1 | Sí |
| `step_export` | 9 | Sí |
| `step_export_catalog_currency` | 10 | Sí |
| `step_export_client_revision` | 10 | Sí |
| `step_export_control` | 10 | Sí |
| `step_export_dashboard` | 9 | Sí |
| `step_export_document_revision` | 10 | Sí |
| `step_export_folio_settings` | 10 | Sí |
| `step_export_shipment_provision` | 9 | Sí |
| `step_export_shipping_design` | 10 | Sí |
| `step_export_supply_comparison` | 10 | Sí |
| `step_export_traceability` | 13 | Sí |
| `step_fruit_category_unification` | 10 | Sí |
| `step_hr_contract_days` | 10 | Sí |
| `step_hr_contract_lifecycle` | 4 | Sí |
| `step_hr_contract_lifecycle_simpledigital` | 10 | Sí |
| `step_hr_payroll_rounding` | 10 | Sí |
| `step_hr_previred_simpledigital` | 10 | Sí |
| `step_hr_remuneration_book` | 4 | Sí |
| `step_inventory_packing` | 9 | Sí |
| `step_packing_analytics` | 9 | Sí |
| `step_packing_batch` | 9 | Sí |
| `step_packing_dispatch` | 10 | Sí |
| `step_packing_dispatch_improvements` | 10 | Sí |
| `step_packing_operations` | 9 | Sí |
| `step_packing_ot_layout` | 9 | Sí |
| `step_packing_packaging_master` | 9 | Sí |
| `step_packing_producer_change` | 9 | Sí |
| `step_packing_reception_revision` | 10 | Sí |
| `step_packing_sag` | 10 | Sí |
| `step_packing_stock_flow` | 9 | Sí |
| `step_packing_tare` | 9 | Sí |
| `step_payroll_engine_transition` | 4 | Sí |
| `step_producer_daily_estimate` | 10 | Sí |
| `step_producer_estimate_cancel` | 10 | Sí |
| `step_producer_estimate_revision` | 10 | Sí |
| `step_producer_fruit_flow` | 9 | Sí |
| `step_producer_fruit_reports` | 10 | Sí |
| `step_producers_integrations` | 9 | Sí |
| `step_qa` | 4 | Sí |
| `step_sale_export_report` | 9 | Sí |
| `step_season_navigation` | 9 | Sí |
| `steps_hr_payroll_correction` | 4 | Sí |

## Alcance de productos fuera del inventario instalado

El repositorio contiene 119 módulos propios con manifiesto; 24 no están instalados en este inventario de Cerro.
Los módulos operativos requieren aceptación Community; separar herramientas de ensayo como step_payroll_enterprise_reference, que solo compara el motor nativo en clones privados. La ausencia de caminos declarados no acredita imports, assets, permisos ni flujos; las fuentes desconocidas quedan pendientes.

| Módulo fuera de Cerro | Caminos Enterprise declarados | Dependencias sin fuente inventariada |
| --- | ---: | ---: |
| `step_account_treasury_reports` | 6 | 0 |
| `step_accounting_multicurrency_core` | 0 | 0 |
| `step_agriculture_core` | 0 | 0 |
| `step_agriculture_format_core` | 0 | 0 |
| `step_bank_export_core` | 0 | 0 |
| `step_bpa_inventory` | 0 | 0 |
| `step_budget_design` | 0 | 0 |
| `step_colaciones` | 0 | 0 |
| `step_helpdesk_whatsapp` | 0 | 1 |
| `step_hr_contract_lifecycle_agriculture` | 4 | 1 |
| `step_hr_payroll_bridge` | 5 | 0 |
| `step_hr_previred_blueminds` | 0 | 1 |
| `step_l10n_cl_edi_core` | 0 | 0 |
| `step_labor_operations_core` | 0 | 0 |
| `step_labor_payroll_wizards` | 4 | 0 |
| `step_labor_reports` | 0 | 0 |
| `step_operations_core` | 0 | 0 |
| `step_payroll_contracts` | 0 | 0 |
| `step_payroll_enterprise_reference` | 9 | 0 |
| `step_payroll_oca_api` | 0 | 1 |
| `step_sawmill` | 0 | 0 |
| `step_simpledigital_oca_base` | 0 | 1 |
| `step_simpledigital_oca_security` | 10 | 0 |
| `step_treasury_community_reports` | 0 | 0 |

## Orden de desbloqueo y aceptación

1. Maestros agrícolas y centros de costo: núcleo Community con modelos/IDs originales; luego consumidores de Packing, Productores, Costos y Exportación.
2. Nómina y contratos: motor Community compatible, reglas chilenas, liquidaciones, Previred y libro de remuneraciones; conservar contratos y liquidaciones históricas.
3. Tesorería: lotes nativos existentes, conciliación operativa y clasificación del efectivo. Las cinco consultas alternativas ya no requieren account_reports.
4. DTE y exportación: CAF, folios, firmas, libros, guías, respuestas SII e históricos. No declarar equivalencia por instalar una localización genérica.
5. Calidad, calendarios y demás interfaz: reemplazar operaciones reales y vistas, inventariar Studio, adjuntos, documentos, firmas y configuraciones antes de retirar.
6. Arranque de una copia integral con fuentes Community exclusivamente; comparar IDs, tablas, permisos, saldos y flujos por empresa y perfil; ensayar recuperación.

No editar controles de vencimiento ni usar stubs Enterprise. El addon legado `step_expire_database` forma parte del inventario, no de los reemplazos autorizados.
El corte final requiere paquete integral probado y respaldo fresco; esta matriz no demuestra que el riesgo del 31 de octubre esté resuelto.
