# T139 y T140 — maestros multiempresa

## Alcance

Adjuntos 3443 y 3445 y mensajes humanos 9849/9853 revisados, incluidas sus
cinco imágenes. Desarrollo, Cerro y QA-Cerro. Fundos se enlaza desde Packing /
Maestros. Categoría, clase, calidad y color conservan los maestros actuales.

## Implementación

`step_agriculture_multicompany`: asignación M2M nativa a res.company sobre los
cinco maestros existentes. Empresa original e IDs conservados, sin reasignar
documentos. La instalación siembra únicamente la empresa original. Cada empresa
y sucursal adicional se elige explícitamente. Reglas por empresas seleccionadas
y hook nativo de consistencia; sin abrir documentos a otras empresas.

Se impiden listas vacías, quitar la empresa original, asignar empresas sin
acceso, códigos que se solapan por empresa y categorías no disponibles para
las empresas de una clase. Se impide retirar empresas usadas por documentos.
Las operaciones de recepción, producción, tarjas y estimación verifican que
sus maestros estén asignados a la empresa de la operación.

## Estado

Implementación preparada; pendiente prueba funcional en copias frescas,
publicación y verificación de ambos destinos. No cerrar por este documento.
