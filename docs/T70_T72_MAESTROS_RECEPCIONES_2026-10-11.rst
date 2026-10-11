T70 T71 T72 Maestros y reportes de recepciones de fruta
====================================================

Solicitud
---------

Tickets 70, 71 y 72, adjuntos y últimos comentarios humanos 9346, 9350 y 9354,
leídos el 11 de octubre de 2026. T70 pide Configuraciones / Fruta en Productores
y los campos Código SAG y Caja Base x pallet en Especie. T71 y T72 piden tablas
dinámicas de recepciones a proceso y embaladas en Productores e Inventario,
con filtros de temporada, mes, semana, productor, fundo, especie, variedad y
lote; dimensiones producto y embalaje, cantidad de embalajes y kilos.
Ambientes de entrega: Desarrollo y Cerro El Plomo.

Implementación
--------------

Módulo step_producer_fruit_reports, versión 18.0.1.0.0. Menú Fruta con las
mismas acciones nativas usadas por Exportaciones y Packing: Especie, Grupo
variedad, Variedad, Grupo de calibre, Calibre de fruta, Categoría de fruta,
Calidades de fruta y Color de fruta. No crea maestros ni copia registros. Inventario recibe consulta de los tres
maestros de calibres/categorías previamente reservados a Gestión; la edición
conserva los permisos originales de Gestión.

step.especie recibe sag_code (texto) y base_boxes_per_pallet (número no negativo).
Ambos aparecen en el formulario compartido. No se infieren valores históricos,
no se reemplazan los kg de caja base ni se altera la configuración existente.

La vista SQL step.fruit.reception.report consulta el detalle original
step.packing.picking.tag.line y su recepción stock.picking. Una fila por línea,
con su mismo ID: cantidad de embalajes toma quantity y kilos toma kilos,
exactamente como el detalle de recepción; box_count queda como dato separado
de cajas registradas. Embalaje usa product.packaging existente. No une las
cantidades con quants, composiciones actuales de tarjas o movimientos de stock,
porque esos enlaces podrían duplicar filas o cambiar la historia al despachar.

Productor procede del fundo original; temporada, especie y variedad del
encabezado de recepción. Lote usa stock_lot_id explícito. Si falta, consulta
los lotes de operaciones de la misma recepción, producto, empresa y paquete;
solo asigna cuando el lote es único. Varios lotes quedan señalados sin inferir
uno; el lote de texto original se conserva como referencia adicional de lectura.

Fecha de recepción usa date_done para hechas y scheduled_date para pendientes;
la agrupación nativa de Odoo por mes y semana respeta la zona horaria del usuario.
El filtro inicial Recepciones hechas evita mezclar cantidades ingresadas con
borradores o cancelaciones; se pueden consultar mediante filtros explícitos.
El dominio de cada acción separa process y packed; la regla global limita por
empresas permitidas y el ACL concede solo lectura a usuarios de Inventario.

Los menús Recepción a proceso y Recepción embalada de Productores abren las
nuevas acciones pivot,list. En Inventario / Reportes se añaden Informe fruta a
proceso e Informe fruta embalada con esas mismas acciones. Las acciones nativas
de operaciones siguen disponibles para registrar entradas en Inventario.

Validación y publicación
------------------------

Paquete final c4b307f607a08b7d14db6ecaf9eaf2f30698e5fa.
SHA256 1b6bcfc51516bce3221d0673d5a0a91e7c73d37cbcaa386f1c422a82fb681340.
Módulo step_producer_fruit_reports versión 18.0.1.0.0.

El ensayo inicial t7072a detectó operaciones de prueba con cantidad cero en
traslados hechos, rechazadas correctamente por Odoo. t7072b aprobó seis pruebas,
pero la comprobación del perfil de Inventario detectó tres menús invisibles por
sus ACL originales de Gestión. El paquete final incorpora lectura de esos
maestros para Inventario y una séptima prueba de los ocho menús y de la ausencia
de permiso de edición adicional.

Copia nueva MANAGEMENT_QA_DEVELOPMENT_t7072c: siete pruebas aprobadas, cero
fallos y errores; conservación exacta de filas de negocio y auditoría. La
comparación inicial excluye únicamente las dos columnas nuevas de Especie;
las actualizaciones futuras las preservan también.

Se verificaron origen y versión del código, ocho maestros compartidos y sus
menús, formulario efectivo de Especie, acciones compartidas entre Productores
e Inventario, tabla dinámica/lista/búsqueda, filtros y agrupación semanal,
flujo real de recepción de ambos tipos, lotes y empresas. Cada recepción
sintética validó 30 embalajes y 150 kg; juntas, cuatro líneas y 300 kg. Todas
las muestras se revirtieron, con correos de registro de usuarios suprimidos.

Copia nueva MANAGEMENT_QA_CERRO_t7072c: las mismas siete pruebas aprobadas,
sin fallos ni errores, y preservación exacta. Se repitieron satisfactoriamente
los menús con perfil de responsable de Inventario, formulario efectivo,
relaciones a maestros, filtros, tabla dinámica, totales y recepciones validadas.

El mismo paquete se publicó y verificó en Desarrollo y Cerro El Plomo bajo
/run/lock/steps-environments.lock, sin downgrade ni cambios concurrentes y con
superposiciones privadas, sin sobrescribir raíces de addons compartidas.

Superposiciones:
/opt/steps-managed/releases/development/c4b307f607a08b7d14db6ecaf9eaf2f30698e5fa
/opt/steps-managed/releases/cerro/c4b307f607a08b7d14db6ecaf9eaf2f30698e5fa

Respaldos completos de base, configuración y filestore:
/opt/steps_backups/management_development_20261011T223114Z
/opt/steps_backups/management_cerro_20261011T223244Z

Después de publicar se repitieron satisfactoriamente versión, código, maestros,
formulario, menús de ambas aplicaciones, filtros, tabla dinámica semanal,
totales, validación real de recepciones y separación por empresa. Conservación
exacta durante instalación pública, servicios activos y acceso HTTPS aprobados.
Las muestras se revirtieron y no se enviaron correos de registro de usuarios.

Accesos de Cerro:
https://cerroelplomo.stepsapp.cl/odoo/action-1578 (fruta a proceso)
https://cerroelplomo.stepsapp.cl/odoo/action-1579 (fruta embalada)

En Desarrollo, las acciones correspondientes son 2212 y 2213.
Evidencia privada en ~/.codex/local-artifacts/t70-t72/live/, fuera del repositorio.
No se versionan adjuntos del cliente, respaldos ni configuraciones privadas.
