# Componentes de líneas y replay BASIC — 29-10-2026 UTC

Continuación de 19b19e90. Se conserva la referencia humana SyS, su cápsula
positiva y documento preservado. El bloque anterior comparó total BASIC; este
bloque exige también amount, quantity y rate originales. Ninguna producción se
escribe ni se recalcula una liquidación original done/paid.

## Contrato implementado

step_payroll_contracts 18.0.1.10.0 incorpora stored_payslip_line_components.
Lee filas SQL guardadas y devuelve ID de línea/liquidación/regla, código,
amount, quantity, rate y total. Respeta permisos del encabezado, modelo/campos
y visibilidad completa de todas las líneas, incluso si se filtra otro código.
Rechaza componentes nulos o no finitos; no reconstruye ni redondea importes.

No suma factores entre líneas: sumar cantidades o tasas no define un resultado
financiero. El total almacenado puede diferir del producto de sus factores por
redondeos; sigue siendo el total original. Tampoco usa sueldo/configuración
actual para reinterpretar líneas cerradas. No cambia campos, tablas, vistas,
ACL, dependencias o almacenamiento ni añade escrituras al leer.

Las líneas con dos identidades NET se pueden inspeccionar por separado, con
sus IDs, sin escoger ni sumar una. El lector agregado anterior sigue rechazando
esa ambigüedad. Esta API de diagnóstico no es una exportación financiera que
resuelva NET 8/32 ni certifica los consumidores que no la utilicen.

Cuatro contratos se ejecutan sobre modelos/motores reales: total redondeado
distinto del producto de factores, estabilidad tras cambiar sueldo actual,
campo restringido/línea oculta, preservación de identidades ambiguas y rechazo
de datos nulos/NaN sin reparar la fila. Los casos inválidos son fixtures privados,
con rollback, no modificaciones de datos de negocio ni un hr.payslip simulado.
El campo restringido se prueba temporalmente en metadatos del test; la regla
oculta usa un ir.rule real. No se eleva al usuario para obtener componentes.

## Referencia real y alcance

audit_sys_monthly_basis.py consulta componentes BASIC directamente por SQL
forzado a lectura. Requiere una línea original inequívoca, estado cerrado,
misma identidad, total y write_date que la cápsula preservada; bloquea una
referencia que haya cambiado. La expresión debe conservar su hash y pasar el
reconocedor estático. No lee propiedades ORM de nóminas históricas.

El replay TransactionCase conserva sueldo documental y días/horas de referencia.
Lee el resultado con el nuevo lector autorizado y compara cada componente por
separado, además del total; comprueba que la FK de regla es la regla del fixture
que recibió la expresión auditada. No basta que el total coincida por casualidad.
Los IDs de registros nuevos de fixture no se presentan como adopción de IDs
originales; no se convierte el motor ni se recalcula el original de SyS.

Alcance sigue siendo BASIC aislado: no es replay de todas las condiciones,
categorías/estructura/entradas del empleado, GROSS/NET, YTD, contabilización,
Previred/libro ni certificación de las 71 reglas. GROSS imponible distinto de
total haberes y la anomalía NET 8/32 siguen explícitos. financial_certified,
master_timeline_certified, full_payroll_replay e identity_conversion son false.

## Aceptación

Paquete D exportado de c4e8d0b: 135 pruebas Community oficial/OCA y 72 en copia
fresca aislada de Cerro, cero fallos/errores y cero ERROR de runtime. BASIC
coincide por separado en amount, quantity, rate y total en ambos motores, con
la FK de la regla aplicada comprobada. Rollback verificado por SQL: cero
empresas/usuarios de fixture restantes; ningún original fue recalculado.

Mismos 96 archivos; SHA-256 del paquete de addons:
630002fef7b0055a9dca873880766c36c1cf55a90c842447015913f6fa4d5142.
Community 68 módulos/cero EE; referencia 383/140. Núcleo 18.0.1.10.0 en ambos,
API Community 18.0.1.5.0 únicamente en CE. Pins Community
4b4efe68291d6def5bb7d2e1f2b829e0cda577d4 y OCA
4c71cd42e46a09a7512d92f5c63c0a9f7c26ad3e. Perfil simpledigital: se conserva
la aceptación anterior de Libro/Previred/HTTP/PDF sin cambios de esas rutas.

Preservados 919 tablas/proyecciones, 140 contadores, 59.048 XML IDs originales,
modelos/campos/ACL/relaciones, 1.614 vínculos usuario-grupo y 283 implicaciones.
Comparación antes/después del upgrade y las pruebas, históricos idénticos.
Tablespaces privados solo para las bases nuevas, sin relaciones públicas en
un espacio ajeno. Matriz completa regenerada idéntica.

Verificación reproducible con el checkout publicado:
python tools/community/summarize_payroll_api.py
~/.codex/local-artifacts/community-payroll-components-20261029/evidence-D
--output ~/.codex/local-artifacts/community-payroll-components-20261029/summary-D.json.
Valida código exacto, identidades/componentes originales y write_date,
fuentes de auditores/probe, cápsula/documento, cuatro comparaciones, versiones,
rollback y preservación, manteniendo certificación/conversión completas en false.

A contiene inventario; B fue preparación sin ejecución. C añade las pruebas de
componentes nulos/no finitos antes de ejecutar aceptación: 135 Community verdes,
referencia 72 con una aserción fallida que comparaba IDs NET filtrados contra
todas las líneas (la nativa conserva otras líneas). D corrige el alcance de esa
aserción, conserva comparación del histórico completo y repite en bases nuevas.
Se mantienen rollback
transaccional y comprobación posterior de cero empresas/usuarios de fixture.
Sin repetir Libro/Previred/HTTP/PDF sin cambios ni sumar pruebas entre perfiles.

Artefactos privados locales:
~/.codex/local-artifacts/community-payroll-components-20261029/.
Servidor: /opt/steps-validation/community-payroll-components-20261029D.
basis-input.json contiene expresión, importes y componentes originales; nunca
Git. Conservar cápsula/documento y pruebas de origen, fuentes ejecutadas,
paquete, JSON/logs, summary-D.json y verification-D.log fuera del checkout.

## Pendientes y siguiente prompt

Inventario completo releído: Cerro 380 instalados/99 propios/140 Enterprise,
117 manifiestos propios, 22 fuera de Cerro y 54 apps con caminos EE. No se
retiran dependencias por este bloque. Sigue pendiente identidad/almacén del
motor, en particular code de días nativo related frente a OCA almacenado
obligatorio. Cerro sin nóminas no prueba adopción histórica: hace falta verificar
históricos reales en copia privada, con snapshots visibles originales, IDs,
relaciones y permisos preservados antes de cambiar la propiedad/almacenamiento.

Continúan 71 reglas/estructuras/entradas/días reales, GROSS/NET, cantidades/
redondeos/YTD generales, asientos, Previred/libro no vacíos, DTE/CAF/folios/firma/
respuestas SII, Tesorería, Calidad, Studio/Documentos/Firma y otros productos.
Falta conversión integral restaurable cero EE, recuperación y aceptación. El 31
sigue en riesgo alto. Producción conserva Enterprise; QA-Cerro no se refresca.

Siguiente prompt: continúa desde canónica actualizada en worktree propio. Lee
AGENTS, ambientes, operación, workflow, plan, continuidad, autonomía, matriz,
COMMUNITY_PAYROLL_COMPONENTS.md, COMMUNITY_PAYROLL_REAL_BASIS.md y referencias.
Haz fetch y revisa inventario completo/fuentes privadas. Conserva referencia
humana SyS, caso positivo documental y caso cero; no repetir preguntas resueltas.
No repitas BASIC/componentes ya verdes sin cambios. Prioriza cerrar almacenamiento
e identidad histórica de días/códigos en copia privada con datos reales de SyS,
sin usar Demo-SYS como QA, antes de retirar dependencias. Captura valores visibles
originales con IDs/ACL/relaciones y prueba upgrade sin recalcular importes.
Amplía después el replay a contexto real de estructura/condiciones/categorías/
entradas y GROSS imponible/NET, sin seleccionar/desactivar reglas para instalar.
No confundas filas separadas del lector diagnóstico con permiso de sumar NET 8/32.
Mantén las 71 reglas, YTD/asientos, Previred/libro y conversión integral cero EE
pendientes hasta certificarlas. Si falta un hecho temporal, conserva el límite
y avanza DTE/CAF/SII sin emisión real. No escribir producción, retirar allí EE,
alterar vencimientos o refrescar QA-Cerro; respeta Calendar, Boolean bancario y
210233. Usa overlays, respaldo, reserva 5/2 GiB y bloqueo compartido; prueba
paquete exacto Community/copia fresca Cerro, evidencia privada, commits/push,
integración solo validada y python tools/git/verify_handoff.py --require-pushed.
