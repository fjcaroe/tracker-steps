# Colisiones de códigos: evaluación real y control previo — 28-10-2026

Continuación de 8775827. La referencia humana sigue siendo SyS; no volver a
preguntar qué base contiene procesos reales. Este bloque observa reglas
sintéticas sobre los motores reales, sin recalcular originales cerrados ni
copiar fórmulas privadas u OEEL. No cambia dependencias, IDs, ACL ni maestros.

## Evidencia del motor y alcance

probe_payroll_rule_collisions.py ejecuta cuatro casos como gerente normal en
las dos bases privadas F previamente aceptadas, bajo el bloqueo compartido.
Los fixtures se revierten. Usa estructuras/contratos/reglas/liquidaciones reales,
no un hr.payslip simulado; solo sustituye en el fixture el alta de compañía
para vaciar su caché antes de crear cuentas, igual que el ensayo YTD.

Con dos identidades de regla con código PRIVATE_COLLISION, importes sintéticos
10/20 y categorías distintas, ambos motores producen las mismas observaciones:

| Caso | Línea conservada | Primera categoría | Segunda categoría | result_rules |
| --- | --- | ---: | ---: | ---: |
| Misma secuencia, ID segundo posterior | segunda, 20 | 10 | 10 | 20 |
| Segunda regla adelanta su secuencia | primera, 10 | -10 | 20 | 10 |
| Misma categoría y secuencia | segunda, 20 | 20 | 0 | 20 |
| Segunda regla cero en la misma categoría | segunda, 0 | 0 | 0 | 0 |

El resultado se observa sin interceptar ni reemplazar la evaluación del motor.
La línea y result_rules pueden conservar una sola identidad mientras las
categorías retienen efectos de otra. No se interpreta eso como una suma de dos
conceptos autorizada, ni como equivalencia financiera del total de remuneración.
Ordenar por secuencia/ID reproduce estos fixtures; no acredita adoptar nuevos
IDs ni elegir una regla de SyS. Estos casos no explican por sí solos por qué
una liquidación histórica de SyS conserva dos líneas NET (8/32).

## Cambio implementado

step_payroll_contracts 18.0.1.7.0 amplía configuration_report: inventaría todas
las colisiones entre códigos de reglas activas directas de la estructura en
duplicate_code_ids, con sus IDs originales en orden de secuencia/ID. Los
esenciales mantienen BASIC/GROSS/NET_AMBIGUOUS; otros códigos generan
RULE_CODE_AMBIGUOUS:<code>. No se ejecutan condiciones para escoger ganadores.
Una condición actualmente falsa tampoco prueba que las reglas sean excluyentes
para todos los casos futuros. Las reglas archivadas y otras estructuras no
crean falsos positivos. No se desactivan, fusionan ni reescriben maestros.

El control previo ya existente de Nómina Chile rechaza la colisión antes de
alterar líneas de un borrador. Fuera de ese alcance, el método de informe no
se convierte en un bloqueo global de todas las nóminas. No se amplía por nombre
el alcance del proveedor ni se certifican estructuras heredadas implícitas.
Los históricos siguen usando el lector SQL conservador 1.6.0 integrado, sin
reconstruir valores. Rechazar una configuración actual no invalida ni repara
una liquidación pagada original.

Un contrato compartido comprueba las cuatro observaciones en ambos motores;
dos pruebas del proveedor verifican rechazo antes de modificar líneas ya
calculadas, conservación de maestros y exclusión de archivadas/otras estructuras.

## Aceptación

Paquete D exportado de 8ca0d3b: 166 pruebas en Community oficial/OCA y 106
en copia fresca aislada nativa de Cerro, cero fallos/errores. Mismos pins
Community 4b4efe68291d6def5bb7d2e1f2b829e0cda577d4 y OCA
4c71cd42e46a09a7512d92f5c63c0a9f7c26ad3e. Libro y proveedor real instalados
en ambos, Community 71 módulos/cero EE, referencia 383/140. No es conversión
histórica de Cerro ni de SyS. Versión SQL del núcleo 18.0.1.7.0 en ambos.

Paquete exacto de 196 archivos, SHA-256
18ce5b13e5d3d1add4dcd993c0512ca9fdef23bdab0581cc603914918a5d7ad6.
Preservados 919 tablas/proyecciones, 140 contadores, 59.048 XML IDs originales,
modelos/campos/relaciones/ACL, 1.614 vínculos usuario-grupo y 283 implicaciones;
comparación antes/después del upgrade y las pruebas, sin cambios de históricos.
Los tablespaces corresponden únicamente a las bases nuevas, sin relaciones
públicas en un espacio ajeno. No se publican servicios ni se refresca QA-Cerro.

Esquema del motor aún pendiente: 934 campos ausentes, una diferencia de tipo,
12 de almacenamiento, 17 de required y cinco de selección; identidad histórica
sin aceptar. El control estructural no acredita las 71 reglas ni los CSV oficiales.

Verificación privada reproducible con el commit publicado:
python tools/community/summarize_payroll_api.py
~/.codex/local-artifacts/community-rule-collisions-20261028/evidence-D
--output ~/.codex/local-artifacts/community-rule-collisions-20261028/summary-D.json.
Verifica paquete, preservación, fuentes exactas del probe/auditores, cuatro
observaciones iguales entre motores, hash de la cápsula y límites temporales.
El auditor temporal se conserva en f0319f5; no cambia bytes del paquete probado.

Evidencia privada local: ~/.codex/local-artifacts/community-rule-collisions-20261028/.
Servidor: /opt/steps-validation/community-payroll-rule-collisions-20261028D.
El probe B sobre F es diagnóstico previo; las bases nuevas D acreditan el
paquete final. A falló por permisos de lectura del script, sin resultados de
motor; no se utiliza como aceptación. C seleccionó los 166/106 contratos
previstos pero se rechazó: el nuevo test esperaba draft tras un cálculo que
deja verify. El test D compara el estado abierto previo real, sin alterar el
comportamiento del motor ni debilitar la comparación SQL de líneas/maestros.
No se repiten HTTP/PDF sin cambios.

Inventario releído en producción con PostgreSQL forzado a lectura: 380 módulos,
99 propios/140 Enterprise, 71 reglas/cuatro estructuras/seis entradas y cero
contratos/liquidaciones en Cerro. Matriz regenerada idéntica: 117 manifiestos
propios, 22 fuera de Cerro y 54 apps instaladas con caminos EE. Fuentes privadas
y pins se conservan conforme a la aceptación anterior; el validador vuelve a
comprobar los hashes activos del proveedor antes de restaurar/instalar.

## Pendientes y siguiente prompt

Falta reproducir el caso privado real de SyS de septiembre con hechos temporales
probados: reglas/fórmulas/contrato/entradas/días vigentes entonces. El sueldo
actual o una regla modificada después del cierre no son base histórica.
La cápsula ya acredita que el contrato actual del caso fue modificado después
del período elegido: no se acepta su sueldo como prueba temporal por defecto.
audit_sys_payroll_temporal_basis.py revalida identidad/período del caso mediante
SQL de solo lectura y liga el resultado al hash de la cápsula. No exporta sueldos,
identificadores de empleados ni fórmulas. Encuentra cero eventos de seguimiento
de wage/hourly_wage/wage_type/schedule_pay para ese contrato. La ausencia de
eventos no prueba ausencia de cambios. hr.contract.history es una vista con
dependencia comprobada sobre hr_contract.wage actual, no un respaldo salarial
inmutable. Hay que recuperar historia de remuneración o una referencia
documental aprobada. historical_wage_proven permanece false.
Auditar la procedencia antes de ejecutar un borrador nuevo; jamás recalcular el original
done/paid ni adaptar maestros de Cerro para forzar ese resultado. La anomalía
histórica NET 8/32 sigue explícita y sin resolver.

Siguen identidad/almacén del motor, configuración y certificación de las 71
reglas, días/entradas/redondeos/YTD, contabilización, Previred/libro no vacíos,
DTE/CAF/folios/firma/respuestas SII, Tesorería, Calidad, Studio/Documentos/Firma,
otros productos y conversión integral restaurable cero Enterprise con aceptación.
Los 140 Enterprise continúan en producción y 54 apps tienen caminos pendientes.
El 31 sigue en riesgo alto; ninguna extracción parcial lo resuelve.

Siguiente prompt: continúa desde la canónica actualizada en worktree propio.
Lee AGENTS, ambientes, operación, workflow, plan, continuidad, autonomía, matriz,
COMMUNITY_SYS_REFERENCE.md, COMMUNITY_RULE_COLLISIONS.md y sus referencias.
Haz fetch y revisa inventario completo/fuentes privadas. SyS es la referencia
real indicada por el usuario: no repetir esa pregunta. Usa cápsula de septiembre
y dumps/snapshot privados autorizados, sin escribir en producción. Prioriza
recuperar evidencia temporal del sueldo del caso (adjuntos aprobados o respaldo
anterior al cierre) antes de reproducirlo en borrador aislado. La auditoría ya
probó cero tracking salarial y vista dependiente del sueldo actual: no repitas
esas consultas esperando que acrediten la historia. No suplas historia con
sueldo o fórmulas actuales. Conserva anomalía NET 8/32,
IDs, permisos, relaciones y snapshots. No elijas reglas por frecuencia/ID ni
relajes la validación de colisiones para instalar. Si faltan hechos históricos,
documenta exactamente cuáles y avanza una frontera real DTE/CAF/SII sin emitir
al SII. Conserva Calendar, Boolean bancario y 210233; no recalcules pagadas,
retires EE en producción, alteres vencimientos ni refresques QA-Cerro. Mantén
5/2 GiB de reserva, overlays y bloqueo compartido. Prueba paquete exacto en
Community oficial y copia fresca de Cerro, distingue referencia de conversión,
guarda evidencia privada, commits/push, integra solo lo validado y ejecuta
python tools/git/verify_handoff.py --require-pushed.
