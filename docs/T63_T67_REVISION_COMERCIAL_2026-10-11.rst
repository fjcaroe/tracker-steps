T63 a T67 - Revisión comercial de Exportaciones y Packing
========================================================

Alcance confirmado
------------------

Se revisaron las descripciones y los cinco documentos adjuntos a los comentarios
humanos recientes, antes de implementar. Los tickets anteriores que el cliente
ya cerró se respetan, incluido T62. No se copiaron documentos privados al repo.

T63 reutiliza step.management.fruit.quality y su acción actual de Gestión y
Costos desde Configuraciones / Fruta en Exportaciones y Packing. Color de fruta
es un maestro nuevo único, compartido por las dos acciones de menú, con código,
nombre, secuencia, activo y empresa. Conserva permisos por perfil y empresa;
no crea otro maestro de calidades ni valores de color supuestos.

T64 incorpora Tipo de embarque debajo de Empresa en el programa de ventas,
con la selección nativa marítimo/aéreo/terrestre. Los nuevos programas reciben
el valor inicial marítimo; los históricos solo se completan desde embarques
relacionados cuando todos indican el mismo tipo. El tipo se conserva al crear
otra versión; una versión vigente o reemplazada permanece protegida.

T65 agrega Planificación / Informe programa de ventas, con Gantt nativo,
tabla dinámica y detalle. Usa las semanas reales del programa, sin tabla de
hechos duplicada. Filtra especie, tipo de embarque, programa y temporada;
agrupa por temporada, mes o semana. Las medidas son contenedores, pallets,
cajas, kilos y ventas USD calculadas con el tipo de cambio de esa versión.
Inicialmente muestra Vigentes; se puede quitar ese filtro y elegir
Creados / validados o Historial reemplazado. No suma por defecto las versiones
reemplazadas. El Gantt es de consulta: no reprograma documentos al arrastrar.

T66 agrega los roles de naviera/aerolínea, consignatario, notify, agencia de
carga y agente de aduana en la hoja Exportación de los contactos. Los cinco
selectores del instructivo filtran por el rol correspondiente. Un contacto
puede tener varios roles. La migración marca los roles ya demostrados por
relaciones existentes, sin buscar ni inventar coincidencias por nombre.
Conserva contactos y documentos anteriores.

La prueba con Cerro El Plomo SpA detectó que las secuencias de embarque se
habían configurado solo para la empresa original: un segundo instructivo
intentaba repetir Nuevo. Se completan las secuencias nativas que falten por
empresa y tipo, y la creación usa la empresa del documento. Se parte después
del mayor sufijo existente, sin cambiar números históricos ni secuencias
ya configuradas. La prueba nueva verifica dos embarques por cada tipo y la
conservación de un número histórico.

T67 mueve el Incoterm nativo desde Otra información al encabezado y agrega
Modalidad de venta relacionada con step.export.sale.mode. No duplica el
maestro ni mantiene otro Incoterm de texto. El título impreso de Nota de venta
pasa a Sales Order y el de Proforma a Invoice, según el documento del cliente.
Se mantienen los totales, numeración, contenido y configuración de T62.

Control de históricos
---------------------

Los ensayos iniciales pasaron las pruebas funcionales, pero la comparación
detectó cambios en write_uid/write_date de semanas existentes al inicializar
campos relacionados. No se promovieron. Cantidades/importes y las otras
columnas originales estaban intactos. El diagnóstico identifica las columnas
sin imprimir valores privados.

Un pre-init guarda exclusivamente los IDs y datos de auditoría en una tabla
temporal de la misma transacción, eliminada al commit. El post-init completa
las nuevas relaciones y restituye los datos originales de auditoría. No hay
un segundo maestro ni una tabla permanente de documentos. El comparador sigue
exigiendo igualdad de todas las columnas originales, incluidos write_uid y
write_date; no se relajó para aceptar el cambio detectado.

Paquete publicado
------------------

Commit 83f22b3fd1d1388eaa0fae529795ad1703b184f8.
SHA256 2c090ec7a9f8b969d49a576f0a6ec874f85590f849b89bd80d50760f3a9f29e6.
step_sale_export_report 18.0.1.0.1 y step_export_client_revision 18.0.1.0.1.
Las herramientas de inspección y verificación están versionadas en tools/ops.
Las pruebas cubren selección por rol, permisos de colores, versionado del
transporte, conservación de auditoría, cantidades/ventas USD, arquitectura
efectiva de Gantt/dinámica, encabezado comercial y ambos títulos impresos.

El publicador exige copias frescas de Desarrollo y del destino Cerro,
conservación de registros, verificación funcional, paquete idéntico,
ausencia de downgrade/cambios concurrentes y respaldo/overlay privado.

Desarrollo y Cerro superaron trece pruebas en las copias frescas
MANAGEMENT_QA_DEVELOPMENT_t6367d y MANAGEMENT_QA_CERRO_t6367d, y comparación
exacta de todas las columnas originales. El verificador de perfil comercial
ejecutó alta/consulta de color, uso del maestro de calidad, versionado del
programa, API nativa get_gantt_data, agrupación con venta de 10.000 USD,
exclusión de versiones reemplazadas, creación de instructivo con los roles
seleccionados, formulario de Nota de venta y generación de ambos PDF.

Se inspeccionaron visualmente los PDF de Desarrollo y los de Cerro El Plomo
SpA con su logo. El perfil de prueba es ventas/inventario multiempresa;
los nuevos menús se comprueban con la API de visibilidad del mismo perfil.
Las muestras se revierten al terminar. Las configuraciones nuevas de
numeración son registros nativos de ir.sequence, sin renumerar documentos.

Publicado el paquete exacto 83f22b3 en Desarrollo y Cerro, usando el bloqueo
/run/lock/steps-environments.lock, guardas de concurrencia/downgrade,
respaldo completo y overlays privados. Ambos servicios están activos y sus
HTTPS pasaron la verificación; los flujos se repitieron en las bases publicadas.

- Desarrollo: respaldo /opt/steps_backups/management_development_20261011T033439Z.
- Cerro: respaldo /opt/steps_backups/management_cerro_20261011T034022Z.
- Overlays: /opt/steps-managed/releases/{development,cerro}/83f22b3fd1d1388eaa0fae529795ad1703b184f8.
- Informe en Cerro: https://cerroelplomo.stepsapp.cl/odoo/action-1575.

Código y herramientas integrados en codex/ambientes-canonicos-reparacion y
conservados en codex/t63-t67-cerro. Los certificados, logs y muestras privadas
quedan en ~/.codex/local-artifacts/t63-t67, fuera del checkout.

T45 continúa pendiente de la prueba con una balanza física; T48 depende de
la activación de Cloud API de Meta; T46 conserva sus pruebas móviles y
tiendas pendientes. No tienen comentarios humanos nuevos que permitan
dar por completadas esas condiciones. No se cierran por esta entrega.
