T68 Informe semanal de estimaciones de cosecha
============================================

Solicitud y alcance
-------------------

Ticket 68 y sus dos adjuntos idénticos, leídos el 11 de octubre de 2026.
Destino solicitado: Desarrollo y Cerro El Plomo. Productores / Planificación.
Informe Gantt, tabla dinámica y lista; filtros por temporada, especie,
variedad, Delivery Kind y productor; agrupación por temporada, mes y semana.

Implementación
--------------

El módulo step_producer_estimate_report consulta directamente las semanas,
líneas y cabeceras existentes mediante una vista SQL de solo lectura. No crea
una tabla paralela de estimaciones, no copia maestros y no modifica las filas
originales. Conserva los IDs semanales como IDs del informe. La regla global
limita las filas a las empresas permitidas; acceso de lectura para usuarios
internos. El menú vive debajo de Productores / Planificación.

La cantidad exportada procede de cada semana. Kilos a proceso, cajas,
pallets y bins reproducen proporcionalmente las fórmulas del detalle original.
Fruta embalada no suma kilos a proceso ni bins. Las barras cubren siete días.
Vigentes es el filtro inicial; creadas/validadas e historial reemplazado se
pueden consultar explícitamente, evitando contar versiones anteriores junto
con la vigente por defecto.

El documento no identifica el precio de valorización. Se consultó al usuario;
a falta de otra instrucción, la referencia aplicada es la lista existente de
precios de preliquidación por empresa, temporada, especie, variedad y semana,
con prioridad de producto/embalaje/semana y vigencia, igual que resolve_price.
Se convierte la unidad de peso a kg y la moneda a USD a la fecha de la semana.
El valor mostrado es FOB estimado sobre kilos exportables; no es retorno neto
ni un cobro adicional por kilos a proceso. No se inventan precios o tasas.
La lista muestra el precio aplicado, USD/kg y el estado de valorización.
Sin precio, empates, unidades incompatibles o cambio ausente quedan sin valor;
el contador de semanas sin valorizar permite reconocer los totales parciales.

Verificación y publicación
--------------------------

Paquete inmutable bf575278752070e932ebf6f57a15780046d0e06f.
SHA256 cd616570bb90c7dc278414b2a83a290e74bd58a730d1e374e913eac5ced3146b.
Módulo step_producer_estimate_report, versión 18.0.1.0.0.

Copia nueva MANAGEMENT_QA_DEVELOPMENT_t68c: cinco pruebas aprobadas, cero
fallos y cero errores. Preservación exacta de filas de negocio y auditoría.
Se verificaron versiones, origen del código, menú visible, filtros, las cuatro
vistas efectivas, datos reales de get_gantt_data, agrupación semanal, cantidades
100 kg / 125 kg a proceso / 20 cajas / 2 pallets / 2,5 bins / USD 200,
y denegación de acceso desde otra empresa. Las muestras se revirtieron.
Los ensayos iniciales t68a/t68b no se promovieron; detectaron el nombre del CSV
de permisos y una omisión en la fábrica de variedades de prueba.

Copia nueva MANAGEMENT_QA_CERRO_t68c: las mismas cinco pruebas aprobadas,
cero fallos y errores. Preservación exacta y comprobaciones nativas del informe
aprobadas. El inspector del código nativo web_gantt confirmó que las plantillas
gantt-popover aceptan las variables de los campos declarados en la vista.

El mismo paquete se publicó y verificó en Desarrollo y Cerro El Plomo.
Superposiciones privadas:
/opt/steps-managed/releases/development/bf575278752070e932ebf6f57a15780046d0e06f
/opt/steps-managed/releases/cerro/bf575278752070e932ebf6f57a15780046d0e06f

Respaldos de base, configuración y filestore:
/opt/steps_backups/management_development_20261011T185507Z
/opt/steps_backups/management_cerro_20261011T185608Z

Publicación bajo el bloqueo /run/lock/steps-environments.lock; sin downgrade,
sin cambios concurrentes de módulos ni sustitución de raíces compartidas.
Preservación exacta comprobada también durante la instalación pública.
Después de publicar: versión 18.0.1.0.0, código exacto, servicios activos,
HTTPS, menú visible, vistas y filtros efectivos, Gantt nativo, tabla dinámica,
100 kg y USD 200 en muestras sintéticas, y separación por empresa verificados
en ambos destinos. Todas las muestras se revirtieron.

Accesos:
https://desarrollo.stepsapp.cl/odoo/action-2210
https://cerroelplomo.stepsapp.cl/odoo/action-1576

La evidencia privada está en ~/.codex/local-artifacts/t68/live/; solo contiene
pruebas y registros de verificación. No se versionan documentos del cliente,
respaldos ni configuraciones. No se modificaron otras aplicaciones ni ambientes.
