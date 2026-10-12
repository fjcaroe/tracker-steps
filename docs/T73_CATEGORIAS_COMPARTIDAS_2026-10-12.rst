T73 Categorías y clases de fruta compartidas
===========================================

Respuesta incorporada
---------------------

Se releyó el ticket 73 y el comentario humano 9378 del 12 de octubre de 2026:
el cliente modificó la recepción de prueba, quitó A proceso y pidió actualizar
el maestro. Se comprobó por SSH que stock.picking.fruit_class_id no conserva
relaciones a la clase antigua en Cerro. No se crea una categoría ni se supone
una equivalencia con Materia Prima. Se retomó el ticket en In Progress.

Implementación
--------------

step_fruit_category_unification extiende los modelos y registros existentes.
Las categorías de stock.picking, detalle de tarja y productos de contratos
consultan step.management.fruit.category. El campo antiguo fruit_class_id de
la recepción conserva su nombre técnico e identidad, pero consulta el maestro
general con la etiqueta Categoría de origen. El maestro de Clase de fruta de
Gestión conserva su identidad y sus clases, y se agrega a las configuraciones
de fruta de Packing, Exportaciones y Productores.

Los menús y accesos antiguos de Packing resuelven el maestro general. Se añaden
formularios compartidos para categorías y clases; los permisos de edición de
Gestión se conservan y Inventario recibe solo consulta de clases. Las reglas
por empresa permanecen activas. Se comprueban explícitamente las relaciones
de categoría de las recepciones al crear o editar.

Las categorías de inventario y contratos son ahora el mismo registro. El
accesor usado por la valorización de Packing devuelve esa misma categoría,
sin exigir un segundo maestro ni un puente de configuración. La columna
original del puente se conserva como historia de migración y se retira de
la vista de edición. No se crean tablas de negocio ni se borran maestros
antiguos; sus registros permanecen como archivo fuera de los flujos activos.

Migración y preservación
------------------------

La migración usa únicamente equivalencias explícitas ya configuradas entre
la categoría antigua y la general, dentro de la misma empresa. Exige una
equivalencia única para cada ID referenciado; rechaza equivalencias ausentes,
duplicadas y relaciones que crucen empresas. Si vuelve a aparecer una clase
de origen antigua referenciada, se detiene antes de cambiar datos.

Los cambios de IDs relacionados se aplican con CASE para evitar colisiones.
Se reemplazan las claves foráneas por relaciones al maestro general. Todas
las demás columnas originales, incluidos importes, kilos, estados, fechas de
auditoría y marcas nulas, se preservan mediante tablas temporales de la conexión
de instalación que se eliminan al terminar. No quedan tablas paralelas.

El comparador normaliza antes de instalar únicamente los IDs relacionados a
su equivalencia explícita. Después exige las mismas filas y el mismo contenido
semántico en todas las tablas de negocio, sin excluir columnas de auditoría.

Estado de pruebas
-----------------

t73a aprobó cinco pruebas y detectó que la recepción aceptaba una categoría de
otra empresa a pesar de la propiedad check_company del campo. Se añadió una
restricción explícita sobre las dos categorías y la empresa de la recepción,
y una comprobación previa de empresa en la migración. Ese paquete no se publica.

El paquete final aprobó seis pruebas en MANAGEMENT_QA_DEVELOPMENT_t73b y
MANAGEMENT_QA_CERRO_t73b, con cero fallos y errores. La comparación semántica
preservó todas las filas y columnas originales, incluidos auditoría e importes,
normalizando únicamente las relaciones de categoría según su equivalencia.
Una comprobación del formulario esperaba el campo Empresa para un perfil que
lo oculta; se corrigió el verificador y se certificó la misma copia aprobada,
sin repetir la instalación ni cambiar el paquete. Se verificaron los menús,
formularios efectivos, recepción real validada, selección de precio de contrato,
permisos y aislamiento de empresas. Las muestras se revirtieron.

Publicación verificada
----------------------

Paquete 3ca1ca93dfba5e394bb46f12b460e15e6baee276.
SHA256 f5b4311ff9073cb3a0da35fa065213598dba9e7c443c4535d65cf3433b5959ff.
Módulo step_fruit_category_unification versión 18.0.1.0.0.

El mismo paquete se publicó en Desarrollo y Cerro El Plomo. Se repitieron
versión instalada, origen del código, formularios, menús, validación real de
recepción, selección de precio contractual, relaciones por empresa y retirada
de referencias activas a maestros antiguos. Ambas instalaciones preservaron
exactamente los datos según la equivalencia comprobada. Servicios activos y
acceso HTTPS verificados. Las muestras se revirtieron y no se enviaron correos.

Respaldos completos de base, configuración y filestore:

* /opt/steps_backups/management_development_20261012T213703Z
* /opt/steps_backups/management_cerro_20261012T213839Z

Superposiciones privadas:

* /opt/steps-managed/releases/development/3ca1ca93dfba5e394bb46f12b460e15e6baee276
* /opt/steps-managed/releases/cerro/3ca1ca93dfba5e394bb46f12b460e15e6baee276

Se respetaron el bloqueo /run/lock/steps-environments.lock, la ausencia de
cambios concurrentes y downgrade y las raíces de addons compartidas.
Categorías/Clases: acciones 1928/1929 en Desarrollo y 1095/1096 en Cerro.
Evidencia privada fuera del checkout en ~/.codex/local-artifacts/t73/live/.

El registrador de cierre exige la evidencia del mismo paquete en ambos destinos,
relee respuestas posteriores al comentario 9378, contrasta el ticket con el
estado guardado al retomar y verifica el HTML, la etapa Solved y la ausencia de
notificaciones. El acta y el código se guardan y suben a la rama de trabajo y
a codex/ambientes-canonicos-reparacion, con verify_handoff aprobado.

T73 quedó en Solved, con nota interna 9379. Se releyeron la etapa y el mensaje
guardado: HTML correcto, subtipo Note y cero notificaciones. No hubo otra
respuesta humana posterior a 9378 antes del cierre.
