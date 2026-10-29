# T131: creación de sucursales, diagnóstico inicial

Se leyeron descripción, comentario 9788 y adjunto 3430. El documento solo muestra
la pestaña Sucursales, sin el mensaje de error. Solicita Desarrollo, Cerro y QA-Cerro.

La relación estándar es `res.company.child_ids` / `parent_id`. Odoo abre un
formulario de empresa para la sucursal; eso por sí solo no demuestra un fallo.
No crear un maestro paralelo ni modificar datos, permisos o vínculos sin reproducirlo.

## Reproducción privada

`tools/ops/probe_company_branch.py` se ejecutó sobre la copia privada existente
`MANAGEMENT_QA_CERRO_t130c5`, con el usuario operativo existente, sin sudo de ORM.
Se abrió el formulario de la empresa padre, se agregó una línea de `child_ids`,
se ingresó un nombre de prueba y se guardó. Se creó una sucursal con padre correcto
y moneda coincidente. La transacción se revirtió; no se creó ninguna sucursal
real ni se publicó código en un ambiente activo.

El proceso de prueba habilita test_enable únicamente en su proceso privado para
no disparar instalación automática de localizaciones al crear la empresa. No se
modificaron credenciales ni configuración de los servicios. Este caso básico
pasó; todavía no se ha reproducido el error informado y no certifica todo el flujo
visual del navegador o los valores concretos ingresados por el cliente.

## Consulta autorizada

El usuario indicó expresamente preguntar al cliente en el ticket. Se publicó y
verificó el comentario público 9789, solicitando mensaje completo o captura del
error y el paso exacto: Agregar una línea, completar un campo o guardar.
No se repite la consulta por este chat ni se cierra el ticket por este análisis.

T131 queda abierto, pendiente de esa información. No hay un paquete correctivo
ni publicación. Antes de entregar una solución: reproducir la respuesta en copia,
probar funcionalmente el mismo paquete en copias frescas de los tres destinos,
publicar con respaldo y bloqueo y verificar menú, formulario, versión y flujo real.

Artefactos privados: `~/.codex/local-artifacts/t131-20261028/` y
`/opt/steps-validation/t131-branch-repro.log`. No guardar los adjuntos en Git.
