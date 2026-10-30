# Grupos de pagos Community: borrador y publicación contable

**Candidato 18.0.1.1.0, pendiente de aceptación del paquete exacto.** El cierre H
conserva sus pruebas y evidencia de 1.0.0; no se reemplazan ni se reinterpretan.

Implementación propia LGPL-3, escrita desde el contrato de metadata observado
y las APIs públicas de `account` Community. No importa ni copia código OEEL.

`account.batch.payment` usa `account_batch_payment`; los pagos existentes usan
su FK `account.payment.batch_payment_id`, con `ON DELETE SET NULL`. No crea
órdenes, lotes ni pagos en tablas paralelas. La interfaz guarda una referencia
explícita, fecha y pagos existentes. Crear, seleccionar o eliminar un grupo no
publica, duplica, envía ni elimina pagos. Los cambios de pertenencia requieren
acceso a todos sus pagos, empresa, diario bancario, moneda, dirección y método
compatibles. Los pagos de otro grupo, enviados o conciliados se rechazan.

ACL: lector contable de sólo lectura; facturación con CRUD, como el contrato
nativo. La regla global conserva el dominio original por diario/empresa.
También se protege la escritura directa de la FK desde `account.payment`.
No se confía en una One2many filtrada para comprobar el grupo completo.

Los importes de borrador parten de pagos y líneas contables reales. `amount`
usa `account.payment.amount_signed`; los residuales leen las líneas de la
cuenta pendiente, en sus monedas almacenadas. No se convierte con la tasa
actual ni se modifica el importe de un pago al leer el grupo. La observación
privada `community-batch-grouping-reference-20261029C` confirmó en el proveedor
nativo intacto dos pagos de borrador (importe firmado, residual cero) y dos
pagos publicados (importe y residuales negativos pendientes), en moneda de
compañía. No certifica divisas, conciliaciones parciales ni estados enviados/
conciliados; la metadata por sí sola tampoco acredita esos flujos.

`action_post_draft_payments` publica pagos nuevos mediante el servicio compartido
`post_groups_draft_payments`: verifica el grupo completo, permisos y configuración;
separa temporalmente la FK, llama a `account.payment.action_post` real y restituye
la misma pertenencia dentro de un único savepoint. No crea pagos ni debilita la
guarda de escritura directa de su FK. Rechaza cualquier pago con asiento o estado
previo, métodos distintos de manual, transacciones/token de proveedor y efectivo
inmediato. Sólo admite una compañía por operación y vuelve a comprobar los
asientos publicados, importes y referencias. Un error tardío restaura pagos,
asientos, relaciones y notas de todos los grupos seleccionados.

El grupo sigue en `draft`: publicar contablemente no equivale a validarlo para
el banco. La validación, envío, rechazo, congelación y conciliación bancaria del lote
siguen pendientes. `validate_batch_button` rechaza la operación explícitamente.
El formulario ofrece comprobar el grupo y publicar sus pagos nuevos en contabilidad. Los
formatos bancarios sobre pagos existentes siguen en `step_bank_export_core`.

La preinstalación ensayada rechaza proveedores nativos instalados o pendientes
en el mismo grafo, y una tabla previa sin propietario Community certificado.
Ese control prueba instalación limpia y rechazo de almacenamiento frío; no
certifica cambios posteriores de proveedor ni adopción histórica. Cualquier
transición futura exige admisión completa de modelos, identidad, relaciones,
permisos y flujos antes de convertir. La aceptación oficial CE usa únicamente
fuentes Community; la referencia nativa excluye este núcleo.
No se cambian dependencias de Tesorería, no se
crean sustitutos vacíos de los wizards de error/rechazo ni de `bank.rec.widget`.
Quedan por adoptar originales de modelos, campos, XML IDs, ACL, M2M, chatter,
archivos, secuencias y estados enviados/conciliados en la conversión integral.

## Prueba del mismo servicio contra ambos proveedores

`step_batch_payment_grouping` es un servicio abstracto `account`-only. En la
referencia nativa se instala únicamente ese servicio: el proveedor original
conserva su clase y almacenamiento. En Community se instala además este núcleo.
Los mismos casos de agrupación operan contra ambos proveedores reales.

El candidato añade 12 casos de publicación compartida y un caso de formulario.
Tags: `/step_batch_payment_grouping` (32 casos, una observación nativa omitida
en CE) y `/step_batch_payment_core` (15 casos, sólo CE). Los fixtures usan
compañías y secuencias privadas `no_gap`; no consumen ni reinician correlativos
de negocio. La observación `BATCH_NATIVE_REFERENCE` captura importes y estados
reales de dos pagos en borrador y dos publicados, sin asumir su fórmula.
`COMMUNITY_BATCH_REFERENCE_OUTPUT` puede apuntar a un JSON nuevo dentro de
`/opt/steps-validation/` para conservar esa referencia privada.

La aceptación funcional y la conversión fría son puertas distintas. Este
alcance no autoriza retirar Enterprise, cambiar producción ni declarar
resuelto el vencimiento del 31 de octubre.
