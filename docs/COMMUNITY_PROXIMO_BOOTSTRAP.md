# Próximo bootstrap: identidad y configuración original

Propuesta técnica del 30-10-2026 desde la canónica `e847d54f`. Conserva la
aceptación de [Contratos originales C](COMMUNITY_CONTRATOS_ORIGINALES.md).
No ejecuta una importación, certifica reglas, concede permisos ni convierte
una base. El candidato T138/puente Community se valida por separado; esta hoja
no anticipa el resultado de ese ensayo.

## Bloque propuesto y orden

Preparar una **base privada nueva sin demo ni semillas salariales** que pueda
adoptar la configuración original, empezando por la clausura de identidad y
referencias externas. No importar sobre la referencia normal ni sobrescribir
la acción que actualmente ocupa 462. El resultado esperado del siguiente
bloque es un plan ejecutable y probado de identidad/referencias, seguido de
adopción atómica únicamente si pasan todas sus puertas.

La [cápsula C](COMMUNITY_PAYROLL_CONFIG_ORIGINAL.md) conserva 120 maestros:
cuatro estructuras, cinco tipos, seis tipos de entrada, 71 reglas y 34
categorías. Sus 91 aliases contienen **88 originales y tres de referencia**;
no contar los tres últimos como identidades productivas anteriores. La M2M
original estructura/tipo de entrada tiene cero pares y se conserva vacía.

1. Inventariar todos los extremos originales que realmente se requieren:
   empresas, usuarios de auditoría, países/monedas, calendarios, diarios y los
   campos/modelos/grupos/acciones referidos. Capturar identidades, valores y
   relaciones en evidencia privada sellada; los hashes sin un enlace de
   identidad probado no autorizan asignar otro registro equivalente por nombre.
2. Cerrar los cuatro tipos canónicos ya compartidos y sus PK de metadata.
   Sus aliases, modelo, `res_id` y `noupdate` coinciden con `hr_contract`; no son
   cuatro maestros ajenos que se puedan reubicar. Faltan valores originales y
   auditoría. Comprobar los IDs de `ir.model.data`, sus posibles ocupantes y
   todas sus referencias antes de proponer una escritura. No renumerar para
   hacer desaparecer una colisión.
3. Resolver el reporte original 462 en el perfil nuevo antes de las semillas
   que crearían el ocupante incompatible. Una reserva temprana es una
   **estrategia por demostrar**, no una instrucción ya autorizada por un plan
   listo. Debe existir el reporte Community real, el routing de su nombre y
   sus bindings antes de adoptar las cuatro FK de estructura.
4. Resolver seguridad y metadata de modelos/campos originales. Después, y
   sólo con el contrato de diferencias explícito aprobado por las pruebas,
   adoptar los 120 maestros, sus identidades y referencias en una transacción.
   Conservar SQL NULL, traducciones, países globales, archivo, fórmulas y
   auditoría. No rellenar propietarios, categorías, nombres, reglas ni inputs.
5. Proyectar los **71 pares originales explícitos** sobre la M2M real de OCA
   con la API ya implementada. Comprobar FK idénticas, cobertura completa,
   ausencia de extras/comparticiones/ciclos, ACL normales e idempotencia. No
   presentar los 71 pares sintéticos aceptados en C como una importación real.

El [planner de identidad](../tools/community/original_identity_adoption_plan.py)
es readonly. Conserva bloqueos para relaciones sin binding físico demostrado,
Many2many, referencias polimórficas y rutas serializadas/dinámicas. No basta
buscar el entero 462 o los enteros 1–4 en cualquier tabla: hay que demostrar
modelo, tabla, columna y registro propietario. El plan de reserva/importación
debe abortar con cualquier referencia sin clasificar, diferencia concurrente
o colisión no resuelta.

## Diferencias de configuración que no deben ocultarse

El preflight C2 conserva **siete diferencias de campos y cinco físicas**:

| Contrato | Frontera pendiente |
| --- | --- |
| `structure.rule_ids` | One2many nativo frente a Many2many OCA. La proyección funcional no cambia esa metadata. |
| `structure.type_id` | Obligatorio nativo, opcional OCA; también difiere la nulabilidad física. |
| `type.salary_benefits_ids` | Falta el contrato real de beneficios. |
| `rule.category_id`, `rule.code`, `rule.struct_id` | Obligatorios nativos, opcionales OCA; también difiere la nulabilidad física. |
| `category.code` | Obligatorio nativo, opcional OCA; también difiere la nulabilidad física. |

OCA usa legítimamente estructuras sin tipo y reglas sin propietario en su
referencia genérica. No imponer NOT NULL globales ni convertir M2M a O2M para
reducir estos contadores. La admisión
[`_step_check_original_required_contract`](../step_payroll_oca_api/models/original_nullable.py)
comprueba los valores requeridos y el alcance de registros concretos; no
convierte metadata ni autoriza por sí sola una importación. Su uso junto con
la proyección debe quedar en el contrato versionado de adopción, sin marcador
RPC que declare originales a registros sin procedencia.

Los [beneficios](COMMUNITY_BENEFICIOS_NOMINA.md) son una frontera distinta:
diez modelos, catorce tablas y 58 registros relacionados que conservar, aunque
no haya beneficios/ofertas configurados. `payroll_contract_advantages` es un
motor LGPL real, pero sus dos modelos y su API no son equivalentes al catálogo
original `hr.contract.salary.benefit`. No crear un alias vacío, retargetear
sus registros ni sustituir sus tablas por un catálogo paralelo. Un puente
necesita APIs funcionales, relaciones y permisos demostrados; mientras falten,
la brecha y la puerta de conversión integral permanecen abiertas.

## Reporte y propiedades por compañía

Las cuatro estructuras remiten al reporte 462 y al alias original
`hr_payroll.action_report_payslip`; su nombre de reporte nativo es
`hr_payroll.report_payslip_lang`. El reporte Community existente usa
`payroll.action_report_payslip` y el renderer real
[`report.step_simpledigital_oca_base.report_payslip`](../step_simpledigital_oca_base/report/payslip_report.py).
Sus pruebas actuales conservan esa identidad y la ausencia del alias nativo.
La adopción propuesta necesita un contrato nuevo y explícito de routing e
identidad para el perfil original; no modificar silenciosamente ese contrato
normal ya aceptado ni copiar una plantilla OEEL.

Exigir impresión real con actor normal, PDF inspeccionado, cero/negativos/NULL,
firma y aislamiento entre compañías. La impresión histórica debe usar líneas
almacenadas sin consultar sueldo vigente ni recalcular. Véanse
[Reporte de liquidación](COMMUNITY_PAYSLIP_REPORT.md) y
[Propiedades de nómina](COMMUNITY_PROPIEDADES_NOMINA.md).

Las tres propiedades JSON de diario conservan cuatro claves de compañía cada
una; la cuarta estructura conserva SQL NULL. No aplanar esas doce referencias
ni dejar que un default ORM complete una clave ausente. La ruta contable debe
probar diario/empresa/cuenta y su contexto real. La cápsula no aporta por sí
sola una configuración contable certificada. No reactivar ni utilizar 210233.

## Evidencia SyS necesaria para certificación

La base de referencia ya fue indicada por el usuario: **SyS**. La
[referencia autorizada](COMMUNITY_SYS_REFERENCE.md) conserva 623 liquidaciones
done auditadas; 622 tienen una identidad NET no ambigua y una tiene dos
identidades NET, incluida una fila cero. Esta última permanece bloqueada; no
elegir una regla ni borrar una contribución para construir un oracle.

La cohorte adicional y sus resultados esperados **no están aprobados por esta
propuesta**. Seleccionar casos completos y relevantes por evidencia privada:
meses de distinta longitud, altas/bajas, faltas, licencias, atrasos, entradas
repetidas/cero/NULL, topes y acumulados. Capturar sólo lectura SQL de los
snapshots, días/inputs y procedencia de reglas/contratos. La fórmula actual y
el sueldo vigente no acreditan sus valores históricos.

Reproducir en **borradores nuevos privados** con los datos originales
demostrados y el motor real; nunca ejecutar `compute_sheet` sobre las 623
cerradas. Comparar identidad e importes de las reglas aplicables, BASIC/GROSS/
NET, cotizaciones, redondeos/YTD, asiento, Previred y libro. Las fórmulas de
GROSS de Cerro y SyS difieren: no trasladar la de SyS a Cerro ni desactivar la
guarda de Cerro para aparentar concordancia.

Se puede avanzar autónomamente en captura readonly, clausura de referencias,
implementación libre, importación controlada cuando sus puertas estén
cerradas y regresiones funcionales. Las diferencias de significado salarial
que no resuelva la evidencia requieren validación de Remuneraciones y una
referencia aprobada; no inferir una decisión legal por el nombre de una
categoría. Toda evidencia financiera queda privada, fuera del checkout.

## Puertas de aceptación

El mismo paquete debe aprobar Community oficial y copia fresca de Cerro,
con respaldo y bloqueo compartido, sin upgrades concurrentes. Comparar antes/
después IDs, aliases/`noupdate`, metadata, ACL, relaciones, propiedades, textos,
históricos, saldos y correlativos; probar rollback real e idempotencia. No
restaurar contadores para ocultar un consumo ni confundir una proyección
numéricamente equivalente con preservación literal de su representación.

La adopción de configuración seguirá siendo una referencia parcial. Falta la
conversión restaurable de la base integral con cero Enterprise, certificación
de consumidores y aceptación operativa de [Autonomía](COMMUNITY_AUTONOMIA.md).
Mantener visibles DTE/CAF/folios/firma/respuestas SII, Tesorería, Calidad y
Studio/Documentos/Firma. No retirar Enterprise en producción, refrescar QA-Cerro,
alterar vencimientos, usar `step_expire_database`, emitir al SII real ni enviar
mensajes externos. **El 31 de octubre conserva riesgo alto.**
