# SyS · Aprobación de ausencias y días de nómina

El 27 de noviembre de 2026 se comparó el respaldo nativo de SyS con una nueva restauración íntegra de su entrega Community de 193 módulos. Ambas bases se abrieron en memoria en la estación. Coincidieron las identidades, estados, períodos y relaciones de todas las solicitudes y asignaciones, las entradas de trabajo y los días de liquidación. El respaldo nativo es `669f58d3eb1f5240bcd248b2f2a905d52b76752274dfc5396d14b5ad118c17f0`. [Entrega integrada](COMMUNITY_SYS_ENTREGA_193.md)

| Registros originales | Resultado |
| --- | --- |
| Solicitudes de ausencia | 140 aprobadas y 8 rechazadas |
| Asignaciones de tiempo libre | 189 aprobadas y una pendiente |
| Entradas de trabajo | 99.134, incluidas 2.623 con un vínculo directo a 134 ausencias aprobadas de 65 empleados en ocho empresas |
| Tipos de día guardados en nómina | 132 ausencias coinciden en tipo, empleado y período con 99 líneas de 96 liquidaciones cerradas |
| Muestra de las 133 liquidaciones más recientes | 36 ausencias aprobadas coinciden en período y trabajador con 18 liquidaciones de seis empresas |

Los mismos seis identificadores de ausencia aprobada ya carecían de entrada directamente enlazada en la base nativa. En cinco casos se conservan contrato coincidente y tipo de entrada. Uno carece de esos dos datos. En los seis existían entradas de trabajo y una liquidación cerrada del trabajador en el período. Los registros permiten comprobar la situación histórica. No documentan por qué se generó así. El recibo de la comparación es `6b8561a75fdaf5c8999a3c5ad1304dd2862da8ef3f37c9c4212642f263dfa16e`. [Verificador de origen](../tools/community/inspect_sys_absence_chain.py)

## Flujo del aprobador

Los dos gestores originales abrieron el menú 382, la acción 619 y el formulario 1781 en cada una de las ocho empresas. Consultaron las solicitudes de su empresa y los controles Aprobar, Validar y Rechazar. Las definiciones del menú, la acción y la ficha coincidieron con la referencia nativa. Los campos de primer y segundo aprobador están vacíos en las 148 solicitudes históricas, por lo que el ensayo no atribuye esas aprobaciones a personas concretas.

Se crearon dos solicitudes de prueba para empleados y contratos reales en días de diciembre todavía sin nómina cerrada. Se usaron los tipos de ausencia empleados anteriormente por esos trabajadores. Una pasó de pendiente a aprobada con el gestor de RRHH. La otra pasó primero a segunda aprobación y fue validada por el segundo gestor. En cada caso el motor creó dos entradas del tipo original, con ocho horas en total. En un nuevo borrador el calculador chileno reconoció las mismas horas, el tipo y el código de día. El recibo es `6010b84875711da5571db023c11266c4f76d013d643b9efdcb96778df1079078`. [Prueba funcional](../tools/community/probe_sys_absence_approvers.py)

Las transacciones se revirtieron. Después coincidieron las 609.137 filas de las 1.141 tablas y el catálogo completo de la entrega. Se registraron los avances de secuencia propios de los ensayos. El recibo de preservación es `3dd36eff3edc96e8b105e9c8b91eb4f8507a3fb9343e52fc56a60dc36bdd1951`.

## Alta ordinaria de liquidaciones en la entrega 193

La prueba local separó el cálculo correcto de los días de la creación desde el menú. El formulario histórico 5018 falla en la carga inicial porque solicita campos sin proveedor. Se identificaron 23 campos y nueve métodos de botón ausentes en la vista combinada. El formulario libre 5302 encuentra un segundo problema durante el cambio de empleado: intenta leer `hr.rule.input`. Esta tabla está vacía en Community y no existía en el origen. La ruta genérica de días devuelve cero líneas con el tipo de ausencia en los dos casos ensayados. Resolver estos puntos requiere conservar las funciones y relaciones que sí utilizaban los operadores.

En el origen, los dos operadores internos crearon las 765 liquidaciones, 233 y 532 respectivamente. Las rutas originales son Todos los recibos de nómina (951/1420), Por pagar (952/1418) y Lotes (953/1426). La captura conserva 702 asientos enlazados, 765 totales de horas, 90 advertencias y tres indicaciones de neto negativo. Hay seis tipos de entradas adicionales y dos líneas históricas que utilizan uno de ellos. No existen planificaciones, adjuntos salariales ni gastos enlazados a estas liquidaciones.
