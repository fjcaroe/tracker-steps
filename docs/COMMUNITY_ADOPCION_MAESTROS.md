# Maestros originales, permisos y referencia SyS — 30-10-2026

Continúa desde `a983b501`. Se acepta el paquete normal S7 congelado en
`9a42297f`: **671 casos Community y 462 nativos, cero fallos y errores**.
La adopción completa de los 120 maestros/71 reglas conserva puertas pendientes;
esta aceptación no convierte integralmente Cerro ni resuelve el 31 de octubre.

## Código y aceptación normal

- Foundation `step_payroll_contracts` **18.0.1.15.0** conserva la familia nativa
  de beneficios como datos, sin fingir su API. Sus observadores contrastan
  14 tablas/58 filas y relaciones originales en el ensayo anclado. Dos aliases
  OCA reutilizan los grupos originales; no crean grupos ni membresías.
- El adaptador de `res.groups` resuelve esos dos pares mediante las interfaces
  públicas `get_id`/`parse` de las definiciones reales de Odoo. Odoo sólo registra
  un nombre externo por grupo: `env.ref` por sí solo no prueba `has_group` ni
  expresiones de campos/vistas. Se conservan IDs, evaluador, implicaciones y
  restricciones. Un alias en conflicto falla también al negarlo; el nombre
  nativo válido mantiene su comportamiento. Ocho casos nativos enfocados pasaron
  antes de repetir la pareja completa.
- API **18.0.1.16.0** añade formulario, lista, acción y menú Community reales de
  tipos de entrada. Tres casos comprueban actor normal, país oculto, campos y
  caché caliente. Los indicadores sin semántica certificada permanecen de sólo
  lectura en el formulario; no se introducen maestros.
- Paquete exacto: **33 addons propios / 461 archivos propios + 52 del proveedor
  AGPL = 513**. El archivo Git reproducido en el worktree de integración coincide
  byte a byte con los 461 archivos propios probados. Se verificaron 212/168
  métodos críticos y 31/27 versiones por modo, incluidos 26 módulos requeridos.
- Grafos medidos: Community **120 instalados / 0 EE**; copia nativa de Cerro
  **397 / 140 EE**. La segunda conserva Enterprise y es una referencia.
- Preservación normal: **921 tablas/proyecciones + 140 contadores**, 59.079
  aliases originales y sus noupdate, modelos, relaciones, ACL, históricos y
  saldos. El único cambio de representación permitido sigue siendo
  `stock_package_type.base_weight` ID 1 `15.00`→`15`; un testigo nuevo, desde el
  respaldo S7, prueba equivalencia sin Float ni redondeo. R3 permanece separado.

Evidencia privada: `/opt/steps-validation/community-multifront-parallel-20261030S7`
y `~/.codex/local-artifacts/community-adoption-20261030S`. Cápsula normal:
`8efe41690d0f7b5451455b0a9d7b9f0dc610d9674b832fd4759f29de642b9939`.
Reproducción offline con código Git confiable y sello de 1.104 miembros,
11.501.675 bytes: **`ad84c0302d4f46f39411f4f5c5fc49c468cf2cb37a394d5793f4e900c924aae0`**.
Resumen: `d9925da02991a4e55638be96151097ef651feb373b6694547202362737491e2a`.
El sello y su recibo se conservaron también en el servidor con modo 0600;
los bytes se releyeron allí y sus hashes coinciden con los verificados localmente.
El replay independiente desde el worktree de integración y 38 pruebas puras
de aliases, captura, custodia y verificador pasaron. Estas pruebas puras no
sustituyen los 1.133 casos funcionales de la pareja S7.

## Ensayo original anclado: avance y bloqueos

Las herramientas experimentales quedan preservadas en
`origin/codex/community-original-adoption-20261030`; no se presentan como una
conversión aceptada. S1 detuvo antes de ORM por Git; S3 detectó que el motor no
se había cargado. S2/S4 originales sólo se materializaron. S5/S7 cargaron OCA
real en copia fresca: **modelo 600, reporte 462, 144 instalados/0 EE** en S7,
con los demás productos explícitamente fuera de operación.

El perfil privado conserva los 120 registros y omite semillas y políticas
aditivas. Mantiene sus datos, maestros y permisos originales; dos modelos OCA
nuevos vacíos sólo admiten lectura del gerente existente. Usa cuatro columnas
nuevas nulas sin inferir propietario/padre y derivaciones LGPL mínimas para
preservar propiedades JSONB desde el primer arranque. La instalación oficial
por estados evita que `-i` propague init y recargue datos noupdate del proveedor.
La limpieza LGPL se delega completa, reteniendo sólo dos aliases originales
comprobados; 23 guardas SQL preceden ORM y sus tres negativas se ejecutaron.

El observador nativo readonly real confirmó **118 maestros permitidos y dos
tipos denegados** al UID7, sin ser superusuario ni cambiar sus cuatro compañías.
Los tipos 3/4 de Bélgica no son usados por las cuatro estructuras. Las reglas
de país originales deben conservar su denegación; no se concede acceso para
hacer pasar el ensayo. Todas las estructuras y las 71 reglas sí son visibles.
Sourceproof S7B: `6577c8c2d004778ce825e6427e3f4081080ccf15db8391febb18538082b42773`.
La primera comprobación Target S7 con ese Sourceproof pasó la política, actor,
contexto y partición de los 120 maestros. Se detuvo en el primer formulario
por el observador que prohíbe SQL fuera de la proyección. No alcanzó a escribir
las 71 membresías; el intento y su rechazo quedan conservados, sin ampliar
permisos ni aceptar una escritura por inferencia.

La revisión readonly S5 preserva 944/945 proyecciones literales, 59.079 aliases
y 140 contadores, sin columnas originales perdidas. El delta de filas es de
menús nuevos; historia/adjuntos necesitan separación técnica demostrada. Hay
36 diferencias de columnas: 33 caídas NOT NULL, dos aumentos y
`hr_payslip_line.name` VARCHAR→JSONB. Tres FK cambiaron sólo ON DELETE:
calendario SET NULL→RESTRICT, compañía RESTRICT→SET NULL y lote CASCADE→SET NULL.
Antes de restaurar CASCADE hay que cerrar `run.unlink` sobre todos sus hijos y
la protección de historias; no confiar en `unlink` de hijos ante cascada SQL.
Hay otras 32 restricciones nuevas que requieren revisión. **No hay aceptación
de conversión por esta revisión**, ni por cero EE en una cohorte aislada.

## Referencia real SyS

Una única transacción RR/READ ONLY, sin ORM ni recálculo, capturó 622 cerradas
previas al mes actual, 9.710 líneas con componentes, 753 días y dos entradas.
Las 87.880 work entries son candidatas por contrato: no prueban vínculo directo
al recibo ni aprobación del período. La fuente tenía 727 cerradas; 105 actuales
quedaron fuera del corte. D registraba 627 en otro instante; no se atribuye el
cambio de población a este migrador.

La matriz reproducida liga 39 de las 71 reglas por XML ID original; 23 tienen
líneas históricas en esa cohorte. Sólo 14 coinciden en los campos/expresiones
actuales comparados; 25 difieren y 32 carecen de binding probado. SyS tiene
92 reglas: no se copia su configuración sobre Cerro por código coincidente.
La cronología de maestros sigue sin acreditar en las 71.

Se recontrastaron íntegros el positivo D, el cero F, los cuatro componentes
BASIC y la ambigüedad NET 8/32, conservada sin escoger una regla. La captura
liga 52 archivos listados del proveedor; no certifica archivos extra ni clausura
de ejecución. Artefacto privado A: `488437ac9e936279bf891c6a9c6c7ba053360fb098dd95c786f7921e50ccce77`;
replay independiente exacto: `297c761304a1badea7b23101161ff54793f360b6debbbd612e98f94a4ffd9aa8`.

## Siguiente puerta

Completar la paridad de visibilidad Source→Target y ejecutar la proyección real
idempotente de 71 pares bajo el usuario autorizado, conservando las dos
denegaciones. Cerrar después almacenamiento/constraints, menús legados y
referencias opacas, y certificar reglas, Previred/libro con casos equivalentes
probados. DTE/CAF/folios/firma/respuestas SII, demás productos y copia integral
restaurable con cero Enterprise continúan en el camino crítico. Quedan 54 apps
instaladas con caminos EE en código; producción conserva 140 EE.

El 31 sigue en riesgo. No se ha intervenido producción, QA-Cerro, vencimientos
ni saldos. No hubo emisión SII, mensajes externos ni recálculo de pagadas.

## Prompt de continuación

```text
Continúa desde origin/codex/ambientes-canonicos-reparacion actualizada, en un
worktree propio. Lee AGENTS.md, ~/.odoo/environments.json, operación canónica,
workflow, plan, COMMUNITY_CONTINUACION.md, COMMUNITY_ADOPCION_MAESTROS.md,
COMMUNITY_AUTONOMIA.md y sus referencias e inventario completo vigente.

S7 normal acepta 671 CE/462 nativos, 33 propios/513 archivos y preservación de
921 tablas/proyecciones, 140 contadores y 59.079 XML IDs. Conserva R3/Q4/D/H.
Recupera las herramientas experimentales útiles de
origin/codex/community-original-adoption-20261030; no confundas sus ensayos
con la pareja normal aceptada ni integres código experimental sin pruebas.

Prioriza cerrar la adopción original de 120 maestros/71 reglas sobre OCA:
reutiliza el Sourceproof nativo S7B y conserva su partición 118/2 bajo UID7.
Diagnostica el rechazo de SQL en el formulario del intento S7 source-parity-A,
sin relajar el guard por suposición; prueba formularios/menús y materialización
real idempotente de 71 pares. Revisa todos los metadatos, columnas, constraints,
referencias opacas y menús legados antes de aceptar la cohorte. Evita el cambio
VARCHAR→JSONB y restaura la semántica de las tres FK sólo con pruebas y guardas
reales de históricos; CASCADE exige proteger run.unlink incluso ante hijos
ocultos. No adoptes permisos nuevos sobre modelos originales.

Usa la captura SyS A y su replay offline como referencia real, sin sustituir
las reglas de Cerro ni atribuir cronología a sus 71 maestros. Cierra la prueba
equivalente de reglas, días/entradas, redondeos/YTD, asientos, Previred y libro.
Usa los tres agentes disponibles en worktrees separados y coordina SQL/ORM
bajo /run/lock/steps-environments.lock. Conserva fuentes congeladas y reserva.

Preserva IDs, maestros, ACL, relaciones, históricos, saldos y correlativos.
Respeta Calendar, el Boolean bancario y 210233. No toques producción, QA-Cerro,
vencimientos ni recalcules pagadas/validadas; no emitas al SII ni mensajes
externos, no inventes maestros ni copies OEEL. Avanza después DTE/CAF/folios/
firma/respuestas, Calidad y demás productos. Prueba el paquete exacto en CE
oficial y copia fresca de Cerro, integra sólo lo validado, commit/push y
python tools/git/verify_handoff.py --require-pushed. Mantén activa la continuidad
horaria y no declares resuelto el 31 hasta la copia integral restaurable cero EE
y la aceptación; el corte productivo queda fuera.
```
