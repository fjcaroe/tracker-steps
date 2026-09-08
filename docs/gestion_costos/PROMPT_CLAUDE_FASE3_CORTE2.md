# Prompt para Claude — continuar Fase 3, corte 2

Trabaja exclusivamente en el worktree
`C:\Users\tito4\Documents\Odoo-gestion-costos`, rama
`codex/gestion-costos`. Revisa primero
`docs/gestion_costos/HANDOFF_FASE3_CORTE1.md`, `DECISION_LOG.md` D03–D06,
`DATA_MODEL.md`, los modelos actuales y toda la suite. Preserva todos los
cambios sin commit existentes; no hagas reset, commit, push ni despliegue.

Implementa **Fase 3, corte 2** del addon `step_management_costs`, subiendo la
versión de `18.0.7.0.0` a `18.0.8.0.0` y agregando upgrade idempotente.

Objetivo funcional: crear el documento de estimación de cosecha por
centro/cuartel a partir de los maestros y curvas validadas del corte 1.

Requisitos mínimos:

1. Crear maestro de versión de estimación, multiempresa, con código/número,
   temporada, fecha límite, estado y unicidad SQL por empresa. No reemplaces
   todavía el `season` Char de presupuestos.
2. Crear cabecera y detalle de estimación con compañía, versión, temporada,
   especie/variedad, unidad de estimación y método de cálculo
   `plantas|hectáreas|kilos`, más una curva validada de cada tipo
   `week|caliber|class`.
3. Filtrar centros por compañía y datos agrícolas disponibles. Copiar al
   detalle, como snapshot, hectáreas, plantas/cuartel y datos descriptivos que
   reproduzcan el cálculo. Si el modelo actual no tiene número de plantas,
   agrega un campo compatible y no destructivo al centro de costo, default 0.
4. Fórmula D05 obligatoria:
   - plantas: `total_ue = plantas × rendimiento_ue`;
   - hectáreas: `total_ue = hectáreas × rendimiento_ue`;
   - kilos: el usuario ingresa directamente `total_kg` y no se aplica otra
     multiplicación;
   - en los otros métodos: `total_kg = total_ue × unidad.kg_factor`;
   - nunca multipliques dos veces por `rendimiento_ue`.
   Bloquea división por cero en kg/ha y kg/planta; muestra 0 con explicación,
   sin `#DIV/0!`.
5. Acción Validar: exige tres curvas validadas, activas, del tipo correcto y de
   la misma empresa; genera distribuciones por semana, grupo de calibre y clase
   como líneas normalizadas. La suma de kg por cada eje debe conciliar con el
   total kg usando una política explícita de redondeo y residuo determinista.
6. La validación debe ser idempotente y transaccional. Una estimación validada,
   sus entradas y distribuciones quedan inmutables. Para corregir, crea una
   nueva revisión; no uses bypass basados en `context` enviable por RPC.
7. Mantén aislamiento multiempresa, ACL encadenadas, método-gates y constraints
   SQL para claves naturales/duplicados. Operador crea/calcula; aprobador valida;
   consulta sólo lee; administrador mantiene maestros.
8. Agrega vistas, acciones y menús `Estimaciones > Estimaciones`; no implementes
   aún carga Excel ni informes documentales.
9. Añade pruebas Odoo reales para fórmulas, factor kg, tres conciliaciones,
   redondeo, idempotencia, revisiones/inmutabilidad, roles/RPC, curvas incorrectas,
   semana 53, dos compañías, constraints y preservación en upgrade.

Antes de entregar, ejecuta `py_compile`, parseo de todos los XML y
`git diff --check`. Después prueba únicamente en bases desechables: upgrade de
un clon de `LAB_TAREAS` e instalación limpia, con
`--test-tags=/step_management_costs`. Exige RC 0 y 0 failed/0 errors; elimina
bases, dumps y artefactos temporales. No escribas ni reinicies servicios de
`LAB_TAREAS`, `STEPS_DEMO` o `STEPS_DEMO_SYS`.

Al finalizar, crea `docs/gestion_costos/HANDOFF_FASE3_CORTE2.md` con alcance,
decisiones, migración, pruebas exactas, límites y siguiente corte. Informa los
archivos modificados, resultados verificables y cualquier supuesto pendiente.
