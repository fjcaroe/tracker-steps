T69 Informe de calendario de pagos de contratos
==============================================

Solicitud
---------

Ticket 69, comentario 9340 y documento adjunto, leídos el 11 de octubre de 2026.
Publicar en Desarrollo y Cerro El Plomo, Productores / Planificación.
Gantt y tabla dinámica del calendario de pagos por vencimiento, filtros por
temporada, especie, variedad, productor y folio del contrato; medidas kilos y
neto a pago en USD; agrupación por temporada, mes y semana.

Implementación
--------------

step_producer_contract_report define una vista SQL de solo lectura sobre las
cuotas, productos y contratos originales. No copia documentos ni maestros.
Una fila por cuota, con el mismo ID; barra de un día en su vencimiento.
Regla global por empresas permitidas y ACL solo de lectura para usuarios internos.

Temporada relaciona el contrato con step.temporada existente, respetando sus
empresas habilitadas. La columna nueva se instala vacía en los históricos:
no se infiere por fecha, nombre o productor. Se permite clasificar un confirmado
sin temporada una vez; cambiar una temporada ya asignada exige revisión.
Las revisiones conservan la temporada y permiten cambiarla en borrador.
El formulario efectivo incorpora el selector en Vigencia y versiones.

El filtro inicial Cuotas vigentes consulta active=True. Las revisiones nativas
conservan cuotas contabilizadas anteriores y desactivan las pendientes que
copian al nuevo contrato. El informe respeta esos indicadores, incluyendo
borradores para planificación y conservando el historial sustituido como
consulta explícita. No descarta todos los contratos anteriores, porque ello
perdería cuotas contabilizadas que siguen activas.

Kilos convierte la cantidad de cada cuota desde su UdM de peso al kg nativo.
Las unidades sin equivalencia a peso se señalan; no se supone que una caja o
unidad pesa un kilo. Neto a pago utiliza el amount original y convierte su
moneda a USD a la fecha del vencimiento. Una moneda sin tasa aplicable queda
sin convertir y se señala mediante un contador, evitando interpretar como
completo un total parcial. El importe original y la UdM siguen disponibles
en el detalle; el importe en moneda original no se agrega entre monedas.
La cantidad original tampoco se agrega entre distintas unidades.
La fecha de vencimiento es el eje temporal, no una medida sumable.

Validación y publicación
------------------------

Paquete final afeec6713e4fc544bd8d40042e52b8165aa781ff.
SHA256 e4c054090168b65fcdd733b31ab7eddd1b5dbe59417b6dd9bd27c5fe4127a356.
Módulo step_producer_contract_report versión 18.0.1.0.0.

Copia nueva MANAGEMENT_QA_DEVELOPMENT_t69c: seis pruebas aprobadas, cero
fallos y cero errores. El ensayo inicial t69a detectó una expectativa incorrecta
del tipo de excepción del control de empresa; la restricción nativa funcionaba.
El ensayo t69b pasó seis pruebas. El paquete final añade la protección de
agregación de cantidades originales de distintas unidades.

Las copias MANAGEMENT_QA_DEVELOPMENT_t69c y MANAGEMENT_QA_CERRO_t69c
aprobaron las mismas seis pruebas, sin fallos ni errores, y preservación exacta
de todas las filas de negocio y su auditoría. Solo se excluye de la comparación
inicial la columna nueva season_id, que se instala sin asignación histórica;
las actualizaciones posteriores la preservan también.

Verificaciones nativas: versión y origen del código, menú visible con usuario
interno, formulario efectivo con temporada y calendario, las cuatro vistas y
sus filtros, datos de get_gantt_data y agrupación semanal, cantidades 100 kg y
neto USD 200. La revisión conserva la temporada y mantiene dos cuotas activas
por USD 200, sin duplicar las pendientes sustituidas. Se probó la separación
por empresa y se revirtieron todas las muestras.

El mismo paquete se publicó en los dos destinos bajo bloqueo compartido
/run/lock/steps-environments.lock, comprobando ausencia de downgrade y cambios
concurrentes. Se instalaron superposiciones privadas, preservando raíces
compartidas y los demás módulos.

Superposiciones:
/opt/steps-managed/releases/development/afeec6713e4fc544bd8d40042e52b8165aa781ff
/opt/steps-managed/releases/cerro/afeec6713e4fc544bd8d40042e52b8165aa781ff

Respaldos completos de base, configuración y filestore:
/opt/steps_backups/management_development_20261011T190930Z
/opt/steps_backups/management_cerro_20261011T191037Z

Después de publicar se repitieron satisfactoriamente las verificaciones de
versión, código, menú, formulario, filtros, Gantt, tabla dinámica semanal,
kilos, USD, revisión sin duplicados y separación por empresa. Conservación
exacta durante instalación pública, servicios activos y HTTPS comprobados.
Las muestras se revirtieron y no se enviaron correos de prueba.

Accesos:
https://desarrollo.stepsapp.cl/odoo/action-2211
https://cerroelplomo.stepsapp.cl/odoo/action-1577

Evidencia privada en ~/.codex/local-artifacts/t69/live/, fuera del repositorio.
No se versionan adjuntos, respaldos ni configuraciones privadas.

Cierre del ticket
-----------------

Se consultaron nuevamente los comentarios humanos posteriores al 9340; no
había respuestas nuevas. Ticket 69 en Solved, nota interna 9342, subtipo
mail.mt_note, sin destinatarios ni notificaciones. El registrador comprobó
antes la evidencia del mismo paquete publicado en ambos ambientes.
Cambios guardados y subidos a codex/t69-contratos y a la rama canónica;
verify_handoff.py --require-pushed aprobado.
