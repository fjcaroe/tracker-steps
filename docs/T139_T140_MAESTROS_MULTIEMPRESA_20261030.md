# T139 y T140 — maestros multiempresa

## Entrega

Ambos tickets resueltos el 30-10-2026. Adjuntos 3443 y 3445 y mensajes humanos
9849/9853 revisados, incluidas sus cinco imágenes. Notas internas 9854 (T139)
y 9855 (T140), etapa Solved, con ausencia de notificaciones y correos verificada.

Se entregó el mismo paquete en Desarrollo, Cerro y QA-Cerro:

- Módulo: `step_agriculture_multicompany` **18.0.1.0.1**.
- Commit del paquete: `15cddd2b3d1ff8cc90e50998c81720cadd00214c`.
- Archivo certificado: `masters-v8.tar.gz`.
- SHA-256: `a204114c29e1a4274528391cfe263f09f9144412b66028a5c4421e2a2221acd1`.
- Árbol de código efectivo de Cerro y QA-Cerro, idéntico:
  `67e7c0683fd07980ee1ae8e9d3668c8aa561f2643de80ac85ef10665b520a22c`.

La comparación acredita únicamente el módulo de esta entrega, no todos los
addons o prototipos de los ambientes. No reutilizar los paquetes preliminares.

## Comportamiento

Asignación M2M nativa a res.company sobre los cinco maestros existentes:
Fundos de productores, categoría, clase, calidad y color de fruta. Empresa
original, IDs, campos y relaciones conservados. La instalación siembra
únicamente la empresa original; las demás empresas y sucursales se eligen
explícitamente. No se fusionan maestros ni se comparten con todas las empresas.

Fundos se enlaza desde Packing / Maestros con la misma acción de Productores,
incluido su filtro de productores. Se conservan permisos y reglas documentales.
El hook nativo de consistencia usa las empresas elegidas. También se adaptan
la búsqueda de Fundo del encabezado de OT y el control de calidad del embarque,
que antes comparaban solamente la empresa de origen.

El selector Empresas y sucursales se muestra a administradores de accesos
(base.group_erp_manager). Los operadores conservan el uso del maestro en sus
empresas, sin intentar leer etiquetas de compañías fuera de su acceso. Hay
formularios propios de calidad y color para evitar formularios genéricos que
expongan ese selector. No se asignaron grupos a usuarios reales.

Se impiden listas vacías, quitar la empresa original, asignar empresas sin
acceso, códigos que se solapan por empresa y categorías no disponibles para
las empresas de una clase. Se impide retirar empresas usadas por documentos.
Los códigos históricos repetidos entre empresas no se fusionan: una ampliación
que produzca un solapamiento requiere resolver su configuración, conservando
los históricos. Las operaciones de recepción, OT, tarjas y estimación verifican
la disponibilidad del maestro para la empresa de la operación.

## Validación y publicación

**42 pruebas aprobadas: 14 por copia fresca**, mismo paquete. Incluyen selección
en sucursal, rechazo de empresa ajena, asignación autorizada, lectura web del
administrador y del operador, formulario de Fundo, recepción nativa, propuesta
y guardado de la OT y control de calidad del embarque. Pruebas y registros de
ensayo solo en copias; no se crearon ni validaron documentos reales al publicar.

Después de cada publicación se comprobaron versión instalada, ruta efectiva,
reglas, menús, formularios nativos y acceso con el usuario existente (Desarrollo
2; Cerro y QA-Cerro 6). Todos los servicios activos. Respaldo, bloqueo compartido,
rechazo de concurrencia/downgrade y overlays privados durante cada publicación.

| Ambiente | Prueba | Respaldo en /opt/steps_backups/ |
|---|---|---|
| Desarrollo | t139d8, 14 pruebas | management_development_20261030T134041Z |
| Cerro | t139c8, 14 pruebas | management_cerro_20261030T134558Z |
| QA-Cerro | t139q8, 14 pruebas | management_qa-cerro_20261030T134759Z |

Huella exacta de los datos previos comprobada durante migración y publicación.
Fundos conservados: Desarrollo 6, Cerro 19, QA-Cerro 21. Categorías 5/6/6;
clases 6/11/11; calidades 5/4/4; colores 0/5/5. No se refrescó QA-Cerro.
Su aislamiento, bloqueo de salida y rechazo de acceso a la base de producción
se volvieron a verificar bajo exclusión compartida.

Evidencia privada: `/opt/steps-validation/t139-t140-20261030/evidence/` y
`~/.codex/local-artifacts/t139-t140-20261030/evidence/`. Incluye certificados,
logs de pruebas, formularios, publicaciones, paridad e aislamiento. El colector
captura también las salidas de procesos hijos del verificador de aislamiento,
sin anidar ni eludir el bloqueo. La entrega no depende de una captura parcial.
