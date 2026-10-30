# Publicación contable de pagos nuevos agrupados

API candidata 18.0.1.1.0: `post_group_draft_payments(batch_id)` y
`post_groups_draft_payments(batch_ids)`. Devuelven IDs autorizados de grupos,
pagos existentes y asientos creados. El coordinador debe probar el mismo paquete
en Community oficial y copia fresca nativa antes de integrar o declarar aceptación.

El servicio conserva el proveedor, tabla, IDs y pertenencia existentes. Usa ACL y
reglas del actor real, incluso si recibe sudo; comprueba campos y la selección
física completa antes de bloquear. Bloquea grupos y pagos en orden, invalida caché
y prevalida TODO el conjunto antes de modificar. Una operación sólo admite una
compañía; el contexto contable se toma de ella, no de la compañía inicial del
cliente. No se inventa un propietario: son grupos colaborativos según las ACL
originales. Un grupo oculto, de otra compañía o sin permiso se deniega.

Sólo admite pagos draft sin asiento, envío ni conciliación, con importe positivo
finito, método manual y cuenta pendiente vigente distinta de efectivo. Rechaza
token/transacción de proveedor y transferencia interna. No importa defaults ni
maestros del contexto. El mismo savepoint separa la FK, ejecuta el método real de
`account.payment.action_post`, comprueba sus entradas publicadas y restituye la
pertenencia. La guarda pública de la FK no recibe un bypass. Error del proveedor,
restitución o nota revierte todo; las pruebas inyectan únicamente fallos tardíos,
después de crear asientos reales, sin simular el motor.

La operación produce pagos `in_process` y asientos `posted`, conservando importe,
fecha, tercero, banco, moneda y método. El lote permanece `draft`. Deja una nota
interna; no entrega archivo, marca `is_sent`, ejecuta banco ni concilia extractos.
No es la validación nativa: el contrato documental de validación congela el grupo,
y sus wizards/estados/archivos todavía requieren observación y adopción reales.

`validate_batch_button` de CE permanece bloqueado. Disolver un grupo draft sigue
siendo la operación existente; no cancela pagos ni se inventa un estado `cancel`
para el lote. Cancelar/revertir asientos publicados queda fuera: no se toca historia
pagada para aparentar esa operación. FX, concurrencia entre procesos separados y
la adopción fría integral siguen pendientes. Un fallo nativo después de consumir
una secuencia standard puede dejar un hueco normal del proveedor; no se restaura
ningún correlativo. Los fixtures usan cuentas/compañías y secuencias `no_gap`
propias, incluidos `account.payment`, entrada/salida de lote y `picking.batch`.

Regresión candidata: 12 casos nuevos del servicio en ambos proveedores reales y
uno de formulario CE. El proveedor nativo conserva su clase/métodos originales;
sus observaciones se refieren exclusivamente a publicación contable de pagos.
No se deduce validación bancaria, equivalencia de estados enviados, recepción del
banco ni conciliación desde ese resultado. No se cambian las dependencias de
Tesorería Enterprise ni se acredita conversión o solución del vencimiento.
