# Referencia real SyS e identidad de conceptos históricos — 28-10-2026

Continuación desde 61b6ca1. El usuario indicó que SyS tiene liquidaciones y
procesos reales: se incorpora como referencia autorizada. No volver a pedirle
la base de referencia ni tratarla como inexistente. Esto no autoriza escrituras,
recalcular pagadas/finalizadas ni trasladar maestros entre empresas.

## Hallazgo y referencia privada

Auditoría SQL de solo lectura: SyS tiene 623 liquidaciones done, de marzo a octubre
2026. Las 623 tienen NET de la regla 32; una conserva además NET de la regla 8.
Hay 622 referencias completas BASIC/GROSS/NET sin ambigüedad de identidad y una
con dos reglas NET distintas. No se descarta la fila cero ni se elige primero,
último o mayor ID. No se desactivan ni corrigen reglas, líneas ni liquidaciones.
Los IDs 8 y 32 siguen activos, secuencia 200 y condición none. La frecuencia
histórica no acredita por sí sola cómo los motores actuales resuelven colisiones.

Se selecciona un caso completo sin ambigüedad de septiembre (mes previo cerrado).
La cápsula privada contiene los IDs originales de caso/líneas/reglas/contrato,
importes almacenados, entradas y días reales. No contiene nombres, RUT ni IDs de
empleados ni cuerpos de fórmulas. Contiene datos financieros privados: nunca
publicarla en Git. Las fórmulas actuales se representan por hash y sus fechas;
no se declaran versiones históricas acreditadas. El sueldo del contrato actual
está rotulado como actual, no se usa para reconstruir un sueldo histórico.

La auditoría no carga el ORM ni ejecuta compute_sheet: lee columnas SQL existentes
con default_transaction_read_only=on. La fuente privada Simple Digital se verifica
por su licencia; no se copian fuentes OEEL. La selección es referencia para
reproducción futura, no certificación financiera ni conversión de identidad.

Cerro mantiene sus 71 reglas/cuatro estructuras/seis entradas y sus tres IDs
esenciales 25/26/32. SyS conserva BASIC 25, GROSS 2 y NET 8/32. BASIC de SyS usa
días reales y sueldo contractual; GROSS referencia categorías diferentes de
Cerro. No se copian fórmulas a Cerro ni se relajan los guards estructurales para
ocultar esa diferencia. No está certificada la configuración completa por leerla.

## Cambio implementado

step_payroll_contracts 18.0.1.6.0 lee salary_rule_id junto con los snapshots SQL y
exige acceso al campo y a todas las líneas originales. Los conceptos esenciales
BASIC/GROSS/NET no pueden sumar silenciosamente dos identidades de regla distintas.
El lector compartido bloquea esa exportación con UserError; los datos originales
siguen intactos. No modifica configuración ni decide qué regla es correcta.
Las rutas del proveedor que no usen ese lector no quedan certificadas por esto.

Las filas repetidas de una misma regla siguen sumándose, incluidos ceros;
los conceptos no esenciales conservan su contrato aditivo entre reglas distintas.
La API admite filtrar códigos: pedir un concepto ajeno no reinterpreta un NET
ambiguo, manteniendo el control de visibilidad completa. Cambiar el sueldo actual
no modifica los snapshots leídos. No se cambian modelos, campos, FK, XML IDs ni ACL. Los lectores afectados son
stored_payslip_code_totals y stored_payslip_totals; no todos los consumidores del
proveedor pasan por ellos.

Tres contratos nuevos se ejecutan sobre registros/motores reales en ambas ramas:
rechazo de NET con dos reglas aun con una línea cero, conservación de filas de
la misma regla y del histórico tras cambiar sueldo, y adición de otros conceptos.
Se comprueban IDs, importes y write_date antes/después de leer y rechazar.
El oracle son los valores SQL emitidos por cada motor, no una supuesta igualdad
del cálculo NET. El fixture toma la FK real emitida, no asume que un código
coincidente implica la regla preparada por el test.
Los fixtures se crean abiertos, se cierran y hacen rollback; no son pagadas reales
certificadas ni un modelo hr.payslip simulado.

## Aceptación y evidencia

Paquete F exportado de 04c8e43, incorporando T130, aceptado: 163 pruebas en
Community oficial/OCA y 103 en copia fresca nativa de Cerro, cero fallos/errores.
El mismo paquete de 196 archivos tiene fingerprint SHA-256
3d854cda1fff74e8b3db8c685be9d8da45606260cdda1fd075ae70d800732773.
Community instala 71 módulos y cero Enterprise; la referencia nativa 383/140.
step_payroll_contracts 18.0.1.6.0 comprobado por SQL en ambos. Simple Digital y
Libro están realmente instalados; no son pruebas de biblioteca solamente.

Se preservan 1.059 contratos de negocio (919 tablas/proyecciones y 140 contadores),
59.048 XML IDs originales, modelos/campos/ACL/reglas/relaciones, 1.614 vínculos
usuario-grupo y 283 implicaciones de grupos. Comparación antes/después de upgrade
y pruebas, snapshots de histórico idénticos y sin cambios de maestros originales.
La comparación de esquema mantiene 934 campos ausentes, un tipo distinto,
12 diferencias de almacenamiento, 17 de required y cinco de selección; cero
diferencias de campos propios del proveedor no equivale a adopción del motor.
La migración de identidad histórica sigue sin aceptarse.

Verificación local reproducible con el checkout publicado:
python tools/community/summarize_payroll_api.py
~/.codex/local-artifacts/community-sys-reference-20261028/evidence-F
--output ~/.codex/local-artifacts/community-sys-reference-20261028/summary-F.json.
El resultado valida paquete exacto, fuentes ejecutadas, procedencia SyS, proveedor
AGPL de 66 archivos idéntico al de Cerro, derivación reproducible de 52 archivos,
versiones, preservación, tablespaces nuevos y ampliación autorizada. Los JSON
con IDs/importes, dumps, logs y fuentes privadas se conservan fuera del checkout.

A se rechazó por selección incompleta de tests (160 Community/100 nativa,
sin los tres contratos nuevos). B seleccionó 163/103, pero falló la preparación
de las tres líneas históricas: code no se copia en el nativo. Se hizo explícito
código/cero y se tomó la FK original de la línea; el probe C final pasó tres
contratos reales en la referencia B descartada. No es aceptación en bases frescas.
D/E fueron preparaciones sin aceptación, detenidas por exclusión/reserva. El
paquete F incorpora la canónica T130 y almacenamiento privado, con las mismas
restricciones y sin reutilizar esas bases descartadas.

El perfil book-history conserva instalación real de Simple Digital y Libro,
Previred y sus puentes, permisos, vistas/acciones y datasets. Excluye los siete
casos HTTP/PDF ya aceptados y sin cambios de esas rutas; no regresa al ensayo de
biblioteca. Las cifras de suites de perfiles distintos no se suman.

Evidencia privada local: ~/.codex/local-artifacts/community-sys-reference-20261028/.
Servidor candidato final F: /opt/steps-validation/community-payroll-sys-reference-20261028F.
No hay publicación en servicios. Community cero Enterprise y referencia nativa
no significan conversión histórica de Cerro o SyS.

Retención con planes revisados bajo bloqueo: pareja book-install B superada,
las dos parejas fallidas de este bloque y HTTP B superada por PDF D. Ocho bases
propias inactivas, 914.938.744 bytes; cero dumps borrados. Cada plan verificó tres
respaldos por decodificación completa y hash (cinco archivos distintos entre
planes). Se mantienen PDF D, histórico dorado y núcleo sin motor. No repetir
planes consumidos ni retirar copias de otros productos.

Una operación concurrente consumió espacio del volumen PostgreSQL y se respetó
su exclusión. No se rebajó el mínimo de 5 GiB ni se borraron copias ajenas. Se
prepararon tablespaces privados en /opt solo para bases nuevas, con propietarios
existentes y sin mover ninguna base. El volumen WAL/datos compartido seguía bajo
reserva; el usuario autorizó explícitamente ampliar el disco de 100 a 150 GiB.

Se creó instantánea del disco, se verificaron dumps nuevos de SyS y Cerro por
decodificación completa/hash y se amplió ext4 en línea bajo el bloqueo compartido.
No hubo DML de negocio, cambio de credenciales, particionado ni reinicio de
servicios. PostgreSQL quedó listo con 54.364.999.680 bytes libres (medición final
de la ampliación). La instantánea READY y dumps legibles no acreditan por sí solos
la recuperación integral Community pendiente. La ampliación añade costo de
almacenamiento y no autoriza nuevas ampliaciones automáticas.

Evidencia operativa privada: community-payroll-disk-resize-20261028/proof.json y
backups/; community-payroll-storage-20261028/storage-proof.json. La última
aceptación de aplicación sigue separada de esta operación de infraestructura.

## Pendientes y siguiente prompt

Inventario posterior a la entrega concurrente T130: 380 instalados en Cerro,
99 propios/140 Enterprise; 117 manifiestos propios, 22 fuera de Cerro y 54 apps
con caminos genéricos EE. Los nuevos puentes step_company_form_restore_payroll
y step_company_edi_readiness alcanzan Enterprise; no se consideran migrados.
La entrega T130 se integró sin sobrescribirla antes del paquete final.
La referencia humana ya existe: SyS. Falta la reproducción controlada de su caso,
procedencia temporal de maestros/fórmulas, selección efectiva de NET entre motores,
configuración de las 71 reglas, identidad/almacén del motor, días/entradas/YTD y
asientos, Previred/CSV no vacíos. Siguen DTE/CAF/folios/firma/respuestas SII,
Tesorería, Calidad, Studio/Documentos/Firma, otros productos y conversión integral
restaurable cero Enterprise con conciliación/recuperación/aceptación. El 31
permanece en riesgo alto. Ninguna protección o extracción parcial lo resuelve.

Siguiente prompt: continúa desde la canónica actualizada en worktree propio.
Lee AGENTS, ambientes, operación, workflow, plan, continuidad, autonomía, matriz,
COMMUNITY_PAYROLL_CONFIGURATION.md, COMMUNITY_PAYROLL_YTD.md,
COMMUNITY_BOOK_PDF.md y COMMUNITY_SYS_REFERENCE.md. Haz fetch y revisa inventario
completo y fuentes privadas. El usuario aportó SyS como referencia real: usa la
cápsula privada de septiembre, no vuelvas a pedir qué base usar. Conserva la anomalía
NET 8/32, sin modificar sus originales ni seleccionar reglas por frecuencia.
Prioriza observar en los dos motores reales el orden/evaluación de reglas con
código repetido (misma secuencia, distinta identidad/categoría) antes de adaptar
el guard de configuración. No adivines primero/último ni desactives reglas.
Reproduce después el caso en un borrador nuevo aislado con hechos históricos
probados; nunca recalcules el original done/paid ni suplas historia con sueldo o
fórmulas actuales sin procedencia temporal. Conserva IDs/ACL/FK/M2M e históricos.
Mantén la protección del lector SQL y sus filtros, instalación real del Libro,
PDF/HTTP ya aceptados y CSV bloqueado hasta certificarlo. No repitas suites sin
un cambio que lo justifique. Si una base factual falta, conserva el bloqueo y
avanza DTE/CAF/SII u otra frontera real, sin emitir al SII. Mantén pendientes
conversión integral cero EE y restauración/aceptación. No escribas producción,
retires allí EE, alteres vencimientos ni refresques QA-Cerro. Respeta Calendar,
Boolean bancario y 210233. Usa overlays privados, respaldo, reserva y bloqueo.
Prueba paquete exacto en Community oficial y copia fresca aislada de Cerro;
registra evidencia privada, commits y push, integra solo lo validado y verifica
python tools/git/verify_handoff.py --require-pushed.


Continuación posterior: [COMMUNITY_RULE_COLLISIONS.md](COMMUNITY_RULE_COLLISIONS.md)
contiene el último bloque aceptado, límites temporales comprobados y siguiente
prompt. No usar el sueldo actual como histórico ni repetir consultas ya resueltas.
