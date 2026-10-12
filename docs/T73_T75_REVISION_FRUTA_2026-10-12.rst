T73 T74 T75 Revisión de maestros y estimaciones de fruta
======================================================

Alcance confirmado
------------------

Se leyeron los tickets 73, 74 y 75, sus comentarios humanos 9365, 9369 y
9374 y los tres documentos Word adjuntos el 12 de octubre de 2026.
Todos solicitan Desarrollo y Cerro El Plomo.

T73 solicita reemplazar el maestro de Packing por Categoría de fruta de
Gestión, adaptar sus relaciones y agregar Clase de fruta de Gestión en las
configuraciones de Exportaciones, Packing y Productores.

Existe una decisión pendiente de migración: una recepción de Cerro usa la
clase antigua «A proceso» de una empresa cuya categoría homónima existente
pertenece a otra empresa. No se debe asignar esa relación entre empresas ni
suponer que equivale a Materia Prima. Se consultó si corresponde migrar a una
categoría A proceso en la misma empresa o a Materia Prima. T73 permanece abierto.
No se modificaron sus relaciones, registros ni menús.

Implementación T74 y T75
-----------------------

step_producer_estimate_revision extiende modelos existentes sin tablas nuevas.
stock.package.type conserva su identidad y recibe Grupo paquete (Bins, Pallet,
A piso) y Pallet por avión. El campo existente Cajas por pallet cambia de
etiqueta a Cajas por pallet/bins. Packing / Maestros / Tipos de pallets y
Productores / Maestros / Tipos de pallet abren la misma acción de Exportaciones.
Se extienden tanto su formulario como el formulario estándar de Inventario
usado al abrir el envase desde una estimación. Las capacidades negativas se
rechazan al editar; cero y ausencia de grupo no producen divisiones inválidas.
No se asignan grupos ni capacidades históricas por el nombre de un envase.

Las fórmulas pedidas en T75 se aplican literalmente:

* Bins = Kilos a proceso / Cajas por pallet/bins del envase, solo grupo Bins.
* Pallets proceso = Kilos a proceso / Cajas por pallet/bins, solo grupo Pallet.
* Cajas exportación = Kilos exportación / Kg Caja Base de Especie.
* Pallets exportación = Kilos exportación / Caja Base x pallet de Especie.

Los resultados son cero si falta un divisor positivo o el grupo no corresponde.
No se añade una multiplicación implícita por los kg de una caja. Cajas cosecha
conserva Kilos a proceso / Kg por caja de la línea. Las cantidades se recalculan
también al cambiar la capacidad/grupo del envase o los valores de Especie.
Pallets proceso pasa a ser calculado y de solo lectura.

El informe semanal usa las mismas fórmulas y conserva filas, IDs, valores FOB,
precios, semanas, filtros, reglas y origen de cantidades. Añade Pallets proceso
como columna y medida. La instalación recalcula las cantidades derivadas
existentes; no cambia los kilos originales, las semanas ni sus documentos.
El ensayo compara el resto de las filas de negocio exactamente y valida las
cuatro cantidades derivadas de todas las líneas después de instalar.

Estado de verificación
----------------------

Primer ensayo t7475a: cinco pruebas aprobadas y dos fallos por redondeo de
Pallets proceso a tres decimales frente al informe SQL. Se retiró esa precisión
forzada para conservar la misma precisión que las otras cantidades calculadas.
t7475d aprob� ocho pruebas, pero el comparador detect� cambios de auditor�a
y conversi�n de marcas de entrega nulas a falso durante la inicializaci�n.
La migraci�n conserva esos valores antes de inicializar y los restaura
exactamente despu�s del rec�lculo, mediante una tabla temporal de la conexi�n
que se elimina al terminar. Solo cambian las cantidades derivadas solicitadas.

Los ensayos siguientes parten de copias nuevas; no se publicó el primer paquete.

La entrega solo podrá anunciarse cuando el mismo paquete apruebe Desarrollo,
la copia de Cerro y los flujos posteriores a ambas publicaciones. Se conservarán
la configuración y el filestore con dump recuperable, overlays privados y
exclusión compartida /run/lock/steps-environments.lock.
