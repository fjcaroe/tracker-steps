# Tesorería y cierre de Studio — evidencia (29-08-2026)

Release: `step_account_treasury 18.0.1.0.0`, `step_account_treasury_batch 18.0.1.0.0`,
`step_account_treasury_agro 18.0.1.0.0`, `step_agricultural_access 18.0.2.3.0`.

Confirmación explícita: **no se ejecutaron pagos, transferencias, archivos
bancarios, correos ni integraciones externas, y no se hizo `git push`.**

## 1. Concurrencia y auditoría inicial

Preflight sin colisiones: ningún `odoo-bin -u/-i`, `pg_dump`, `pg_restore`,
`rsync` ni `scp` en curso; los tres servicios activos y sólo conexiones `idle`
en las tres bases. El worktree sucio se conservó: sólo se agregaron módulos
nuevos y se tocaron los archivos de este encargo.

### Mapa de motores

| Motor | Desarrollo | Demo | Demo-SyS |
|---|---|---|---|
| `account`, `account_accountant`, `account_reports` | ✓ | ✓ | ✓ |
| `sale`, `sale_management`, `purchase`, `stock` | ✓ | ✓ | ✓ |
| `l10n_cl`, `l10n_latam_invoice_document` | ✓ | ✓ | ✓ |
| `step_accounting_multicurrency` | ✓ | ✓ | ✓ |
| **`account_batch_payment`** | ✓ | ✓ | **ausente** |
| **`step_hr`** (aporta `step.fundo`) | ✓ | ✓ | **ausente** |

Consecuencia de diseño: el núcleo **no** depende de `account_batch_payment` ni
de `step_hr`. Los accesos a pagos por lotes y el campo Fundo viven en dos
puentes con `auto_install`, que sólo se instalan donde existe el motor.

No existe ningún modelo de proforma de proveedor en ninguna de las tres bases,
así que el módulo aporta uno mínimo (§9.6 del encargo).

## 2. Decisiones funcionales

| Punto | Decisión | Por qué |
|---|---|---|
| Tipo de concepto | Se deriva del código Studio: `01` saldo inicial, `1x` ingreso, `2x` egreso | Es la regla que ya usaba el prototipo; evita hardcodear IDs |
| Conversión | `rate_policy = odoo` usa `res.currency._convert` con empresa y fecha; `manual` interpreta el tipo de cambio como *unidades de la moneda del flujo por unidad de la auxiliar* | Reproduce el 900 CLP/USD del documento sin quedar atado a CLP/USD |
| Columna auxiliar | `res.company.operational_currency_id` de `step_accounting_multicurrency` | Integración por servicio público, sin duplicar lógica |
| Pedidos de venta/compra | Se proyecta `precio_total x (cantidad − cantidad facturada) / cantidad` | No depende de la política de control de facturación, cubre "confirmada" y "factura en espera" y nunca vuelve a contar lo facturado |
| Facturas | Se leen por **apunte contable** abierto, no por documento | Cubre cuotas, pagos parciales y notas de crédito con el residual real |
| Corte del saldo inicial | Asientos publicados con `date < inicio` (estrictamente) | No cuenta dos veces lo que el flujo proyecta el primer día |
| Sin vencimiento | Política visible en el flujo: `Otros` (por omisión) o `W1` | El encargo pide política explícita, no un supuesto |
| Archivo bancario | **No implementado** | Sin especificación aprobada; se documenta como pendiente en vez de inventar un TXT |

## 3. Modelo de datos

```
step.treasury.concept   código único por empresa, tipo, secuencia, activo,
                        account_ids (M2M, multi-cuenta), hoja sugerida, notas,
                        legacy_studio_id
step.cashflow           nombre secuenciado, fecha/hora, empresa, inicio,
                        fin calculado (+34 días), responsable, aprobador,
                        moneda del flujo, moneda auxiliar, política y fecha de
                        tasa, tasa manual con motivo/usuario/fecha, tasa
                        aplicada congelada, política de indefinidos, diarios,
                        estado draft/in_progress/approved/cancelled,
                        saldo inicial, KPI, legacy_studio_id
step.cashflow.line      DATASET CANÓNICO: hoja, signo, concepto, source_model /
                        source_id / source_line_id, manual, partner + RUT,
                        tipo y número de documento, fecha y vencimiento,
                        moneda origen + saldo origen, importe en moneda del
                        flujo y auxiliar, cubeta, excluida, comentario,
                        motivo de ajuste, empresa
step.vendor.proforma(+line)  draft/approved/invoiced/cancelled, moneda,
                        vencimiento, líneas con impuestos, vínculo a factura
sale.order / purchase.order  treasury_due_date (campo propio, no x_studio_*)
```

Restricción `unique(cashflow_id, source_model, source_id, source_line_id)`:
un documento no puede entrar dos veces en el mismo flujo.

### Diagrama de fuentes

```
account.move.line (asset_receivable, posted, no conciliado) --> hoja Clientes
account.move.line (liability_payable, posted, no conciliado) -> hoja Proveedores
sale.order (state=sale, pendiente de facturar) --------------> hoja N Venta
purchase.order (state=purchase, pendiente de facturar) ------> hoja O Compra
step.vendor.proforma (approved, sin factura) ----------------> hoja Proformas
entrada manual sobre step.treasury.concept ------------------> Otras Recaudaciones
entrada manual sobre step.treasury.concept ------------------> Otros pagos
account.move.line de diarios banco/efectivo (date < inicio) -> Saldo inicial
```

Todas las hojas, el resumen, los KPI y las exportaciones se calculan desde
`_summary_matrix()` sobre `step.cashflow.line`. No hay segunda tabla de totales.

## 4. Migración del prototipo Studio

Ejecutada en la instalación (`post_init_hook`), idempotente y tolerante a que
el prototipo no exista.

| | Studio antes | Propio después |
|---|---|---|
| Conceptos (`x_concepto_flujo_caja`) | 12 | 12 creados, 7 con cuenta migrada al M2M |
| Flujos (`x_flujo_de_caja`) | 1 | 1 creado |
| Etapas (`x_flujo_de_caja_stage`) | 3 | mapeadas a `draft` / `in_progress` / `approved` |

Flujo migrado: **Flujo septiembre 2026**, 2026-09-01 → 2026-10-05, CLP,
tipo de cambio manual 900 congelado en `applied_rate`, estado `draft`,
`legacy_studio_id = 1`.

Conceptos migrados con su tipo derivado del código: 01 opening; 10, 11, 12, 13,
14 inflow; 21, 22, 23, 24, 25, 26 outflow.

**Objetos Studio conservados intactos**: `x_flujo_de_caja` (1 registro),
`x_concepto_flujo_caja` (12), `x_flujo_de_caja_stage` (3), con sus tablas,
campos, acciones y vistas.

### Menús Studio archivados (no borrados)

| Id | Menú | Estado |
|---|---|---|
| 1345 | Flujo de Caja | archivado |
| 1346 | Configuración personalizada | archivado (contenedor vacío) |
| 1347 | Flujo de Caja Stages | archivado |
| 1348 | Tesorería | archivado |
| 1349 | Concepto flujo caja | archivado |

**Cómo revertir el ocultamiento**: activar los registros
`ir.ui.menu` 1345–1349 (`UPDATE ir_ui_menu SET active = true WHERE id IN
(1345,1346,1347,1348,1349);` o desde Ajustes → Técnico → Interfaz de usuario →
Menús, quitando el filtro de archivados). Los datos nunca se tocaron.

## 5. Brechas de menús del encargo anterior

### 5.1 Gestión y Costos borrador

Inventario comparado: su contenido **no** estaba replicado en
`step_management_costs` (plantilla agrícola, grupo presupuesto, curva de
calibres, categoría y calibre de fruta, más maestros agrícolas). Se absorbió
dentro de "Gestión y Costos" y recién entonces se archivó la raíz Studio.

### 5.2 Fletes

Se compararon acción, modelo, dominio, contexto, vistas, permisos y registros
alcanzables. Resultado:

| Entrada heredada | Modelo | Equivalente del módulo | Veredicto |
|---|---|---|---|
| Orden de flete | `x_orden_de_flete` (2) | Órdenes de flete | acción idéntica → retirada |
| Contabilización de fletes | `x_contabilizacion_de_f` | Contabilización | acción idéntica → retirada |
| Tarifa de fletes | `x_tarifa_de_fletes` (1) | Tarifas | acción idéntica → retirada |
| Rastreo camiones | `x_rastreo_camiones` | Rastreo | acción idéntica → retirada |
| Tramo de flete | `x_tramo_de_flete` (3) | Tramos | acción idéntica → retirada |
| **Informe de fletes** | `x_informe_de_fletes` | — | **sólo Studio → conservado** |
| **Servicios de fletes** | `product.template` | — | **sólo Studio → conservado** |
| **Camiones** | `fleet.vehicle` (18) | — | **sólo Studio → conservado** |
| **Modalidad de frío** | `x_modalidad_de_frio` (3) | — | **sólo Studio → conservado** |

La regla nueva sólo archiva una entrada heredada cuando **modelo, dominio,
contexto y vistas coinciden exactamente** y la superviviente pertenece al
módulo. Por eso "Informes BPA" y "Labores agrícolas" quedaron en pie: comparten
modelo pero no configuración de acción.

Se archivaron además 5 entradas equivalentes en BPA y Riego y 2 contenedores
que la propia fusión dejó vacíos.

Apps activas: Desarrollo 49 → 48, Demo 48 → 47. **Cero duplicados**.

### 5.3 `step.tracker.*`

Sigue duplicado entre `step_hr` y `step_tracker_odoo`. Sólo se documenta: no se
mezcló con este encargo y ninguna prueba reveló regresión.

## 6. Seguridad

Cuatro grupos: `group_treasury_reader`, `group_treasury_user`,
`group_treasury_approver`, `group_treasury_manager` (encadenados). ACL por
modelo y `ir.rule` global multiempresa en los cinco modelos. Ningún `.sudo()`
para saltar seguridad en cálculos de usuario. Auditoría de quién genera,
actualiza, aprueba, reabre y exporta cada snapshot vía `mail.thread`.

Perfil inicial asignado al instalar: quien ya administra Contabilidad
(`account.group_account_manager`) recibe el perfil de configuración —
6 usuarios en Desarrollo, 2 en Demo, 2 en Demo-SyS. El reparto fino queda en
manos del cliente.

## 7. Pruebas

Todas en bases desechables creadas desde cero y **eliminadas al terminar**
(`TES_TEST_20260829`, `AGS_TEST_20260829`).

```
step_account_treasury      0 failed, 0 error(s) of 37 tests
step_agricultural_access   0 failed, 0 error(s) of 14 tests
```

Cobertura frente a las 20 pruebas mínimas:

| # | Escenario | Cubierto |
|---|---|---|
| 1 | Concepto con varias cuentas y restricción multiempresa | ✓ (4 pruebas) |
| 2 | Migración Studio dos veces sin duplicar | ✓ idempotencia + regla de tipo; la migración real se verificó sobre LAB_TAREAS con conteos antes/después |
| 3 | Factura cliente abierta, parcial, vencida, cuotas, nota de crédito | ✓ |
| 4 | Factura proveedor equivalente | ✓ |
| 5 | Venta parcialmente facturada sin doble conteo | ✓ |
| 6 | Compra parcialmente recibida/facturada, ambas políticas | ✓ (fórmula independiente de la política) |
| 7 | Proforma aprobada que desaparece al facturarse | ✓ |
| 8 | Líneas manuales que sobreviven a Actualizar datos | ✓ |
| 9 | Límites exactos de vencido y W1–W5 | ✓ (12 fronteras) |
| 10 | Fecha sin vencimiento según política visible | ✓ |
| 11 | Conversión CLP/USD y tercera moneda | ✓ |
| 12 | Tasa congelada en flujo aprobado | ✓ |
| 13 | Saldo inicial con dos bancos y drill-down | ✓ (incluye el corte del día de inicio) |
| 14 | Fórmula acumulada y signos | ✓ reproduce el ejemplo del documento |
| 15 | Idempotencia y fuente duplicada | ✓ |
| 16 | Bloqueo del aprobado y reapertura auditada | ✓ |
| 17 | ACL de consulta, operación, aprobación, configuración | ✓ |
| 18 | Aislamiento multiempresa | ✓ |
| 19 | Exportación que cuadra con la interfaz | ✓ |
| 20 | Instalación limpia y upgrade sin errores | ✓ en las tres bases |

La prueba 14 replica el resumen del documento: saldo inicial 10.000.000 y
saldos de caja 10.225.207 / 10.945.207 / 8.545.207 / 8.545.207 / 8.545.207 /
4.545.207 / 4.545.207.

## 8. Conciliación de un flujo de ejemplo

Sobre **Flujo septiembre 2026** en LAB_TAREAS, con datos reales:

```
LINEAS: 18   SALDO INICIAL: -11.900.000,00 (diarios BNK1, CSH1)

HOJA                     DETALLE       RESUMEN        EXPORT   OK
Clientes                41.788,00     41.788,00     41.788,00  OK
Órdenes de compra    1.307.360,00  1.307.360,00  1.307.360,00  OK
Proveedores          2.124.150,00  2.124.150,00  2.124.150,00  OK

Sub total recaudaciones     41.788,00  (total_inflow  = 41.788,00)
Sub total pagos          3.431.510,00  (total_outflow = 3.431.510,00)
Saldo Caja final       -15.289.722,00  (closing_balance = -15.289.722,00)

CONCILIACION HOJAS: OK   FORMULA ACUMULADA: OK   TOTALES == RESUMEN: OK
```

Detalle = resumen = exportación, y la fórmula acumulada cuadra cubeta a cubeta.

## 9. Despliegue y huellas

Secuencia: Desarrollo → validación → Demo → validación → Demo-SyS. Sólo se
actualizaron los módulos dirigidos y se reinició únicamente el servicio del
ambiente correspondiente.

| Módulo | Versión | SHA-256 | Dev | Demo | Demo-SyS |
|---|---|---|---|---|---|
| `step_account_treasury` | 18.0.1.0.0 | `819d364c48e0332368cdd5576b785dad4338619416a66230c3d3d0257a3e4e3c` | ✓ | ✓ | ✓ |
| `step_account_treasury_batch` | 18.0.1.0.0 | `71515a7757450df9eefba5e9869d3c7c9b36e6e6ae865351bb0d3af9de589778` | ✓ | ✓ | n/a |
| `step_account_treasury_agro` | 18.0.1.0.0 | `8c9282885bd599965bfb8d4fc35142cef69d4fdc25355af7447089dcdcda0510` | ✓ | ✓ | n/a |
| `step_agricultural_access` | 18.0.2.3.0 | `b17eb564515340ac8243fac63b7cdc605765fba82b8042f319be08a0ba2a3d29` | ✓ | ✓ | n/a |

El núcleo es **byte a byte el mismo** en los tres ambientes. Los puentes están
ausentes en Demo-SyS por diseño (no existen sus motores) y `step_agricultural_access`
no está instalado allí.

Servicios activos y HTTP 200 en `https://desarrollo.stepsapp.cl`,
`https://demo.stepsapp.cl` y `https://demo-sys.stepsapp.cl`. Sin nuevos
tracebacks en los journals de los tres servicios.

## 10. Respaldos

`/opt/backups/tesoreria_20260829/`

| Archivo | Tamaño | `pg_restore --list` | SHA-256 |
|---|---|---|---|
| `LAB_TAREAS_tesoreria.dump` | 19M | 29 900 entradas | `20fa8557d5ed6be4159cd6a3790d8077a68edcdd4c4318477eacf7838359875d` |
| `STEPS_DEMO_tesoreria.dump` | 22M | 29 370 entradas | `5cc7595e678cc04b2f8be448da3c30840a456c1ed4478e1e492cf1c89dbb7769` |
| `STEPS_DEMO_SYS_tesoreria.dump` | 24M | 25 313 entradas | `91a670b17e467877350e3af812415ed1af4b5a1511716c8a45d6e151f003800e` |

También siguen disponibles `/opt/backups/menus_20260829/` y
`/opt/backups/maquinaria_20260828*/` de los encargos anteriores.

## 11. Validación en navegador

Con la sesión real del usuario en `https://desarrollo.stepsapp.cl`, contra los
mismos endpoints que usa el cliente web:

- `/web/webclient/load_menus`: **46 aplicaciones, cero duplicadas**, sin
  "Gestión y Costos borrador".
- `Contabilidad` contiene ahora `Tesorería` con sus seis secciones y los
  quince accesos (pagos, pagos por lotes, transferencias, bancos y efectivo,
  conciliación bancaria, cuentas corrientes, estado de flujo de efectivo,
  cuentas por cobrar/pagar vencidas, Flujos de Caja, Proyección por semana,
  Concepto flujo caja, Proformas).
- `call_kw / get_views` del formulario del flujo: las **ocho pestañas**
  `Clientes, N Venta, Otras Recaudaciones, Proveedores, O Compra, Proformas,
  Otros pagos, Resumen` y el resumen HTML presente.
- `call_kw / web_search_read`: los 12 conceptos migrados con su tipo y sus
  cuentas, el flujo migrado con sus KPI y las líneas con su cubeta e importe.

## 12. Pendientes reales

1. **Archivo bancario de pagos por lotes: no implementado.** No hay
   especificación aprobada por banco; el encargo pide no inventar un TXT. Falta
   definir la interfaz versionada de adaptadores y qué formatos aprueba el
   cliente.
2. **Pantalla inicial de Tesorería (dashboard OWL): no construida.** Hoy los
   indicadores viven en el formulario del flujo (saldo inicial, ingresos,
   egresos, saldo mínimo, alerta de caja negativa), en la lista de flujos con
   esas columnas y en la vista gráfica "Proyección por semana". Falta la
   pantalla con tarjetas por cubeta y gráfico de saldo acumulado.
3. **Exportación PDF: no implementada.** La XLSX sí, con hoja Resumen y hoja
   Detalle derivadas del mismo dataset.
4. **Medición de rendimiento con volumen representativo: no ejecutada.** Se
   añadieron índices por empresa, estado, hoja, cubeta, vencimiento y fuente, y
   la recolección hace una búsqueda por hoja en vez de N+1, pero no se midió
   contra un volumen grande ni se verificó el comportamiento del pool bajo
   carga.
5. **Validación visual con capturas: no disponible.** La pestaña automatizada
   vive en una ventana de Chrome en segundo plano donde el cliente OWL no monta;
   la validación se hizo contra los endpoints reales de esa misma sesión
   autenticada. Demo y Demo-SyS se validaron por consulta y por HTTP, no
   visualmente.
6. **Usuario restringido: no probado en navegador.** Los cuatro perfiles se
   prueban en la batería automatizada, no en sesión real.
7. **Duplicación de `step.tracker.*`** entre `step_hr` y `step_tracker_odoo`
   sigue pendiente, como deuda técnica ya conocida.
8. Quedan bases `CODEX_TEST_*` de otra sesión en el servidor; no son de este
   encargo y no se tocaron.
9. **El árbol local divergió del release desplegado mientras se redactaba este
   informe.** A las 08:10 otra sesión reescribió `__manifest__.py` (versión
   `18.0.1.0.1`), `hooks.py`, `models/cashflow.py`, `models/cashflow_line.py`,
   `models/cashflow_summary.py`, `models/vendor_proforma.py` y
   `tests/test_treasury.py`, y agregó `migrations/18.0.1.0.1/post-migrate.py`.
   Esos cambios **no** se probaron ni se desplegaron aquí. Lo instalado en los
   tres ambientes es el release verificado `18.0.1.0.0`
   (`819d364c48e0332368cdd5576b785dad4338619416a66230c3d3d0257a3e4e3c`), con
   37/37 pruebas verdes. Antes de subir `18.0.1.0.1` hay que revisarlo y volver
   a pasar la batería: no se debe desplegar sin eso.

## 13. Rollback

- Módulos: desinstalar `step_account_treasury*` deja intactos los modelos y
  datos Studio; el menú Studio se reactiva con los ids 1345–1349.
- Menús: `step_agricultural_access` volver a 18.0.2.2.1 no revierte por sí solo
  el archivado; se restaura desde `/opt/backups/menus_20260829/` o reactivando
  los `ir.ui.menu` afectados, que están listados en el log de la migración.
- Bases completas: los dumps de `/opt/backups/tesoreria_20260829/` restauran el
  estado previo a este release.
