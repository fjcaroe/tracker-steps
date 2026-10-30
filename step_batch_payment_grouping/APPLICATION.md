# Aplicación contable de documentos guardados — candidato 18.0.1.2.0

El servicio usa `account.payment.action_post()` y `account.move.line.reconcile()`
reales de `account`. Publica sólo pagos nuevos draft sin asiento y aplica su
contraparte a una factura/bill posted completamente abierto. No ejecuta banco,
envía pagos, concilia extractos ni sustituye `validate_batch_button`.

API:

- `post_groups_against_linked_invoices(batch_ids)` utiliza los vínculos originales
  persistentes `account.payment.invoice_ids`; exige exactamente uno por pago.
- `post_groups_against_invoices(batch_ids, [[payment_id, invoice_id], ...])`
  exige correspondencia exacta con TODOS esos vínculos guardados. No infiere un
  documento por tercero, nombre o importe ni crea/reescribe relaciones maestras.

El actor real conserva ACL/campos/reglas, incluso con un recordset sudo/cacheado.
La selección física completa M2M y todas las líneas de cada documento se
autorizan antes de leer importes. Bloquea grupos, pagos, documentos y líneas;
revalida sus campos. Todos los documentos deben compartir una compañía y moneda
de compañía, tercero exacto, tipo/dirección y una única contraparte vigente
conciliable. No admite notas de crédito, FX, cuotas múltiples, documentos ya
parcialmente aplicados, régimen de impuesto en base a caja, efectivo ni 210233.
No activa cuentas ni cambia tipos, vencimientos, fechas o importes para admitirlos.

Un único savepoint envuelve todo el conjunto: preflight, publicación real,
aplicación real, pertenencia y notas internas. No permite flags del contexto
cliente que omitan validaciones contables. El pago se separa temporalmente del
grupo para ejecutar las APIs normales y después vuelve al mismo grupo; la guarda
pública de su FK no recibe un bypass. Un error tardío del proveedor o de la nota
revierte publicaciones, aplicaciones, estados, relaciones y notas de toda la
operación. No restaura ni reinicia ninguna secuencia.

La contraparte queda con residual cero y conciliación real. La cuenta pendiente
conserva todo su residual firmado, sin partials ni extracto bancario. El lote
permanece draft y conserva miembros/IDs/importe. El motor Community puede
mostrar invoice/payment `paid` al aplicar la contraparte, mientras accountant
nativo habilita `in_payment`/`in_process`. Se conservan esos cálculos originales;
una etiqueta `paid` no acredita aquí recepción ni conciliación bancaria.

En CE el formulario de pago permite seleccionar el campo ORIGINAL `invoice_ids`
antes de agrupar. El botón contable del grupo utiliza sólo esos vínculos. No hay
wizard, tabla paralela, nuevo maestro ni dependencia Enterprise. La referencia
nativa instala sólo el servicio; no se cambia su formulario ni clase de lote.

Regresiones propuestas: once métodos compartidos de
`BatchInvoiceApplicationCase`, incluido normal actor, dirección entrada/salida,
contrapartes/asientos/partials reales, selección oculta, ACL de campo, tercero/
empresa, historial previamente aplicado, fallos tardíos y rechazo de caja/210233.
El caso CE `BatchCoreCase.test_normal_form_applies_only_saved_complete_document_links`
comprueba formulario, vínculos originales, botón, denegación de documento oculto
y aplicación real. Los fixtures usan sus compañías/cuentas y contadores no_gap
privados, incluido picking.batch. No se recalculan liquidaciones ni se tocan
documentos pagados originales. La auditoría LGPL de `account.full.reconcile`
confirma que su matching usa IDs reales y no consume una secuencia comercial.

Es un candidato hasta la pareja exacta Community oficial/copia fresca Cerro.
No certifica cancelación/reversión histórica, validación/conciliador de lotes,
divisas, concurrencia entre procesos, conversión fría ni el vencimiento del31.
