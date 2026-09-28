# T35 — decisiones de Exportaciones y Productores

## Decisiones resueltas

1. **Módulo vigente.** `step_export` es la app de Exportaciones de Steps. Conserva
   los datos que se portaron desde Studio en T33 y es la única app raíz de
   Exportaciones en las cuatro bases auditadas. La nueva app `step_producers`
   depende de ella. No se desinstalan modelos ni registros históricos de Studio.
2. **Maestros de packing.** Líneas y tipos de proceso, tipos y estados de tarja,
   causas de detención y causas de corrección permanecen en `step_packing`, que
   es su dueño funcional. Exportaciones abre las mismas acciones y registros
   desde **Configuración → Maestros de packing**. Las tarjas operativas siguen
   en sus módulos actuales.
3. **Campos compartidos.** Los datos de Exportación y Packing del contacto, y el
   nombre comercial del productor y sus fundos, están en `res.partner`. El
   producto exportable, costo presupuestado, categoría, producto base, especie
   y concepto de liquidación están en `product.template`. La capacidad en cajas
   por pallet y pallets por contenedor está en `stock.package.type`; los kg por
   caja, en `product.packaging`. El indicador de fruta y las cantidades por
   pallet se guardan en `mrp.bom` y sus líneas. Las vistas y accesos de
   Exportaciones exponen esos campos sin crear un catálogo paralelo.
4. **Productores.** `step_producers` da una portada y accesos a productores,
   fundos, estimaciones, tarifas y liquidaciones. Sus botones en el contacto
   muestran los registros relacionados. Reutiliza contactos y operaciones de
   Exportaciones; no genera asientos por sí mismo. La tarifa se busca y valida
   dentro de la empresa, temporada, especie y productor correspondientes.
5. **Moneda.** `step_export` declara dependencia de
   `step_accounting_multicurrency`, instalada en las cuatro bases. Los
   movimientos contables pasan por la integración multimoneda de Steps y sus
   importes operativos. La divisa contractual y fecha de tipo de cambio deben
   revisarse en cada operación, según la política acordada con el cliente.

La decisión de ubicación de datos sigue los modelos propios de Odoo: variantes
en [Productos](https://www.odoo.com/documentation/18.0/applications/sales/sales/products_prices/products/variants.html),
embalajes en [Product packaging](https://www.odoo.com/documentation/18.0/applications/inventory_and_mrp/inventory/product_management/configure/packaging.html)
y movimientos multimoneda en [Multi-currency system](https://www.odoo.com/documentation/18.0/applications/finance/accounting/get_started/multi_currency.html).

## Decisión contable que necesita el cliente

El módulo ya aplica el flujo inicial documentado en
[T35_EXPORTACIONES_IMPLEMENTACION.md](T35_EXPORTACIONES_IMPLEMENTACION.md):
factura inicial, liquidación de recibidor, ajuste IVV y liquidación del productor
con control de facturas previas. Antes de usarlo como política definitiva, el
responsable contable del cliente debe confirmar o corregir lo siguiente **por
empresa**:

1. ¿En qué hecho y fecha se reconoce la venta inicial (contrato e Incoterm) y
   cuándo se considera validada y contabilizada la liquidación del recibidor?
2. ¿Qué conceptos del recibidor reducen ventas, cuáles son gastos o comisiones,
   y cómo se distribuyen entre embarques, calidades y productores?
3. ¿Quién emite los documentos de ajuste de exportación 111/112: Odoo o su
   proveedor DTE? ¿Qué cuentas, diarios, impuestos y folios se usarán?
4. ¿El productor factura al recibir fruta o solo al cierre? ¿Cómo se descuentan
   anticipos, compras ya facturadas y cargos antes de pagar el saldo?
5. ¿Qué fecha y fuente del tipo de cambio se usarán para la factura, el IVV y
   la liquidación del productor? ¿Se permite corregir manualmente el valor?

Para responder basta un contrato representativo y un caso real anonimizado con
factura inicial, liquidación del recibidor, ajuste IVV y factura o nota del
productor. El cliente puede modificar diarios, cuentas e impuestos en
**Exportaciones → Configuración → Parámetros contables** y tarifas en
**Exportaciones → Configuración → Tarifa Productor**. Cambios de criterio de
devengo, reparto o emisión requieren ajustar y probar el flujo antes de
contabilizar nuevos documentos. No se modifican asientos ya publicados.

## Verificación y despliegue

La actualización de `step_packing 18.0.1.1.0`, `step_export 18.0.2.4.0` y la
instalación de `step_producers 18.0.1.0.0` se probaron primero en copias
aisladas de las cuatro bases. Cada copia terminó con **16 pruebas, 0 fallas y
0 errores**. La app de Productores, su icono y sus recursos JS responden en los
cuatro dominios HTTPS. Después del despliegue, los cuatro servicios quedaron
activos y las páginas de ingreso respondieron HTTP 200.

| Entorno | Base | Respaldo previo en `odoo-new` |
| --- | --- | --- |
| Desarrollo | `LAB_TAREAS` | `/opt/steps_backups/t35_producers_20260928_dev_041926/` |
| Demo | `STEPS_DEMO` | `/opt/steps_backups/t35_producers_20260928_demo_042052/` |
| Cerro El Plomo | `CERRO_EL_PLOMO` | `/opt/steps_backups/t35_producers_20260928_cerro_042201/` |
| Demo-SyS | `STEPS_DEMO_SYS` | `/opt/steps_backups/t35_producers_20260928_demosys_042308/` |

Cada respaldo contiene base PostgreSQL, filestore, código anterior de
`step_export` y `step_packing`, sumas SHA-256 y el log de actualización.
La integración contable actual no se alteró ni se publicaron asientos de
negocio durante el despliegue.
