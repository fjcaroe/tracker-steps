# Frontera de lotes y conciliación — 29-10-2026

Base canónica inspeccionada: `5d827f9e`. El paquete M anterior conserva su
aceptación de 242 pruebas Community y 214 nativas; esta auditoría no añade una
conversión de lotes ni sustituye esas pruebas funcionales.

## Contrato observado y bloqueo

La copia nativa M conserva `account.batch.payment`, su tabla original y la
relación `account.payment.batch_payment_id`. El modelo tiene tres importes
monetarios almacenados: `amount`, `amount_residual` y `amount_residual_currency`.
Sus estados técnicos son `draft`, `sent` y `reconciled`. No se deben reconstruir
sus valores históricos leyendo pagos o usando un tipo de cambio actual.

La frontera no termina en el lote. Cinco modelos mantienen relaciones hacia él:

- `account.payment`: relación persistente al lote.
- `account.batch.error.wizard`: asistente nativo de errores/validación.
- `bank.rec.widget`: selección de lotes, sin almacenamiento de esa relación.
- `bank.rec.widget.line`: referencia al lote en las líneas del conciliador.
- `step.cashflow.line`: trazabilidad operativa de Tesorería.

Los asistentes de error/rechazo incluyen relaciones M2M con pagos. Su propiedad
en `ir_model_relation`, IDs, campos inversos, FK y almacenamiento deben adoptarse
antes de retirar su proveedor. `store=True` en metadata no prueba que un modelo
virtual del conciliador tenga tabla SQL; se requiere comprobar `_auto` en el
registro real. No se crea una clase vacía para conservar un nombre.

La muestra nativa contiene un lote en borrador, sin pagos enlazados y sin
archivo bancario adjunto. Esto no certifica estados enviados/conciliados,
residuales, archivos históricos ni conciliación agrupada. Se conserva el bloqueo
hasta contar con un proveedor real y pruebas positivas de esos flujos.

Los dos proveedores actuales siguen siendo Enterprise: `account_batch_payment`
y `account_accountant_batch_payment`. Los formatos BancoEstado/Security ya
extraídos a `step_bank_export_core` son funcionales en Community; no implementan
este modelo ni el conciliador y no justifican cambiar sus dependencias.

## Fuente Community examinada

Se inspeccionó sin importarlo ni instalarlo `account_payment_batch_oca`
18.0.3.4.0, AGPL-3, fijado al commit
`287767cd30d2d73f19b3709d4cac7437ec21c0b2` de
[OCA/bank-payment-alternative](https://github.com/OCA/bank-payment-alternative/tree/287767cd30d2d73f19b3709d4cac7437ec21c0b2).
Su [manifiesto](https://github.com/OCA/bank-payment-alternative/blob/287767cd30d2d73f19b3709d4cac7437ec21c0b2/account_payment_batch_oca/__manifest__.py)
declara `account_payment_base_oca` y `base_iban` y excluye `account_payment_order`.

Es un motor real, con un contrato distinto: declara `account.payment.order`
y `account.payment.lot`, con enlaces `payment_order_id`/`payment_lot_id`.
La orden usa `draft/open/generated/uploaded/cancel`; su confirmación genera
pagos desde líneas y rechaza una orden ya vinculada a pagos. Tesorería agrupa
pagos existentes creados por el registro nativo. Renombrar una dependencia o
copiar los IDs a otra tabla perdería esa identidad y no adapta los flujos.
Referencias de API:
[orden](https://github.com/OCA/bank-payment-alternative/blob/287767cd30d2d73f19b3709d4cac7437ec21c0b2/account_payment_batch_oca/models/account_payment_order.py),
[lote](https://github.com/OCA/bank-payment-alternative/blob/287767cd30d2d73f19b3709d4cac7437ec21c0b2/account_payment_batch_oca/models/account_payment_lot.py).

La [documentación funcional oficial 18.0](https://www.odoo.com/documentation/18.0/applications/finance/accounting/payments/batch.html)
describe agrupación de pagos registrados del mismo método, validación que impide
añadir pagos posteriores y conciliación del importe bancario con los pagos del
grupo. Esos contratos requieren casos positivos; no se infieren de un borrador
vacío ni se copian cuerpos de implementación OEEL.

## Preflight reproducible

`tools/community/batch_adoption_preflight.py` opera mediante autenticación peer
local en una transacción `READ ONLY / REPEATABLE READ`. Rechaza nombres de
producción, no arranca Odoo, no cambia el esquema y no ejecuta cálculos, pagos,
cron, firmas ni envíos. Exporta metadata privada y hashes de filas almacenadas;
no exporta XML de vistas, código de acciones, cuerpos OEEL ni archivos bancarios.

El contrato recoge modelos/campos/selecciones, XML IDs y sus filas originales,
ACL/reglas/grupos, columnas/FK, propietarios M2M, referencias de vistas y sus API,
acciones, secuencias y contadores. También registra hashes de pagos/lotes,
relaciones, adjuntos y chatter del lote. El comparador rechaza cambios o pérdidas
de originales; únicamente admite protección `noupdate=False→True` en namespaces
explícitos de la frontera. No permite cambios de importes ni de correlativos.

Ejemplo sobre una copia existente y aislada, conservando cada salida:

```bash
sudo /usr/bin/python3.10 tools/community/batch_adoption_preflight.py \
  --database MANAGEMENT_QA_CERRO_PAYROLL_API_ACCELERATED_20261029M \
  --output /opt/steps-validation/community-batch-adoption-20261029/baseline.json
sudo /usr/bin/python3.10 tools/community/batch_adoption_preflight.py \
  --database MANAGEMENT_QA_CERRO_PAYROLL_API_ACCELERATED_20261029M \
  --compare-with /opt/steps-validation/community-batch-adoption-20261029/baseline.json \
  --output /opt/steps-validation/community-batch-adoption-20261029/recheck.json
```

`--community-candidate` admite un snapshot con manifiesto AGPL/LGPL/GPL explícito.
Obtiene declaraciones y hashes con AST, sin importar ni ejecutar el candidato;
rechaza OEEL antes de leer sus modelos. No añade fuentes externas al checkout.

La metadata SQL no contiene todos los atributos del registro: moneda de cada
importe, almacenamiento `attachment` de binarios, `_auto`, dependencias de
cálculo y firmas de métodos. `batch_registry_contract.inspect_registry(env)`
es un payload para que el operador inspeccione un registro privado ya cargado,
en una transacción obligatoriamente de solo lectura. Sólo inspecciona atributos
y firmas; no lee registros de negocio ni ejecuta los métodos. Este payload
se ejecutó posteriormente por el coordinador en la pareja B, con READ ONLY y
comparación exacta de todas las tablas/correlativos; ver
[COMMUNITY_PAYROLL_ADOPCION.md](COMMUNITY_PAYROLL_ADOPCION.md). Se obtuvieron esos
atributos y firmas reales sin registros, computes ni cuerpos. Eso cierra la
captura de metadata del registro, no la equivalencia de comportamiento.

## Evidencia y siguiente bloque

Evidencia privada en `/opt/steps-validation/community-batch-adoption-20261029/`:
`native-M-final.json`, `native-M-final-repeat.json`, `community-M-final.json` y
el snapshot OCA con pin/hashes en `oca-reference/source-reference.json`.
La primera ejecución nativa y su repetición conservan contrato exacto sin
modificaciones; Community confirma ausencia del proveedor, almacenamiento y
relación de lote. `conversion_ready=false` y `dependencies_may_change=false`
son obligatorios: la herramienta no certifica el motor por metadata o licencia.

El siguiente bloque debe usar el registro efectivo obtenido y escoger una adaptación
que mantenga `account.batch.payment`/tabla/IDs/ACL, originales de error/rechazo,
M2M y archivos. Debe agrupar pagos existentes sin duplicarlos ni volver a publicar
pagos históricos; probar validación, congelación del grupo, eliminación segura,
residuales y conciliación agrupada por moneda/empresa/rol, más errores y pagos
ocultos. Sólo después procede cambiar las dependencias y ensayar una conversión
fría del proveedor en una copia fresca. El reemplazo del conciliador Enterprise
y la conversión integral de Cerro siguen abiertos; el 31 no queda resuelto.
