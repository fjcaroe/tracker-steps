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

La entrega requiere aprobar una copia nueva de Desarrollo y una copia privada
de Cerro, publicar el mismo paquete con respaldos y exclusión compartida,
y repetir versión, formularios, menús y flujos reales en ambos destinos.
