# Release 1 — Previred: evidencia final

Fecha de validación: **28 de agosto de 2026**.

## Resultado

El mismo release funcional quedó instalado en los tres ambientes sin copiar ni
mezclar bases de datos:

| Ambiente | Base | Motor | Módulos instalados |
|---|---|---|---|
| Desarrollo | `LAB_TAREAS` | Blueminds | core `18.0.3.2.0` + bridge Blueminds `18.0.2.0.0` |
| Demo | `STEPS_DEMO` | Blueminds | core `18.0.3.2.0` + bridge Blueminds `18.0.2.0.0` |
| Demo-SyS | `STEPS_DEMO_SYS` | SimpleDigital | core `18.0.3.2.0` + bridge SimpleDigital `18.0.2.0.0` |

La diferencia de bridge es deliberada: conserva el motor y los datos de cada
base, pero entrega la misma experiencia y las mismas reglas de negocio.

## Arquitectura

```text
step_hr_previred                    núcleo agnóstico
├── step_hr_previred_blueminds      integración l10n_cl_hr
└── step_hr_previred_simpledigital  integración SimpleDigital
```

El flujo existente `Nómina → Reportes → Previred TXT Remuneraciones` se dirige
al asistente Steps. No se publica una segunda aplicación ni un menú duplicado.

## Funcionalidad entregada

- TXT consolidado, uno por departamento o ambos en ZIP.
- Excel consolidado y por departamento para revisión, nunca rotulado como
  archivo cargable en Previred.
- Un único dataset canónico para TXT, Excel, ZIP, totales y auditoría.
- Separación por identificador de departamento; nombres homónimos no mezclan
  trabajadores.
- Selección exacta por empresa, período completo y estado permitido.
- Bloqueo de borradores, anulados, duplicidades, filas ambiguas y visibilidad
  multiempresa incompleta.
- Líneas anexas SimpleDigital conservadas inmediatamente después de su línea
  principal.
- Auditoría sin RUT, nombres ni importes por trabajador; incluye perfil,
  conteos y hashes.
- Cuatro permisos: resumen, generación, perfiles técnicos y auditoría. Los
  administradores existentes fueron migrados de forma idempotente.

## Norma vigente

El perfil se selecciona automáticamente por el período:

- v84: agosto de 2025 a julio de 2026;
- v98: desde agosto de 2026.

Fuente oficial vigente:
<https://www.previred.com/documents/FormatosArchivos/FormatoLargoVariablePorSeparador.pdf>

Para v98 se implementaron los campos 93 a 95:

- tipo de jornada: 1 completa o 2 parcial;
- expectativa de vida: primero el cálculo/regla del motor —incluido el caso de
  licencias y RIMA— y luego el respaldo legal;
- rentabilidad protegida: renta imponible AFP por la tasa legal del período.

El tipo de línea principal se escribe en su forma canónica `00`.

## Pruebas automatizadas

| Ambiente | Suite | Resultado |
|---|---|---|
| Desarrollo | core + Blueminds, 98 pruebas | 0 fallas, 0 errores |
| Demo | core + Blueminds, 98 pruebas | 0 fallas, 0 errores |
| Demo-SyS | core + SimpleDigital, 103 pruebas | 0 fallas, 0 errores |

Las suites cubren consolidado/departamentos, líneas 00/01/02/03,
departamentos homónimos, ausencia de departamento, igualdad TXT/Excel,
duplicidades, campos 93-95, perfiles por vigencia, seguridad, rutas antiguas,
auditoría y volumen.

## Validación operativa

- Los tres servicios quedaron `active`.
- Las tres URLs respondieron HTTP 200.
- Con `fcaro.ruiz@gmail.com` se comprobó en cada base el acceso al asistente,
  los permisos, el menú redirigido y la validación de parámetros.
- Julio de 2026 selecciona v84; agosto de 2026 selecciona v98.
- No se enviaron archivos, correos, pagos ni acciones externas.
- No se hizo `git push` y no se publicaron secretos.

La huella agregada del código y documentación de los tres módulos es idéntica
en los tres servidores:
`a19f9613cb9715d0b8a52b6acb489cac8c72ba65e20eca6a3794dbd6e09b5740`.

## Respaldos previos

- Desarrollo: `/opt/backups/steps_20260828_codex_previred_v98/`
- Demo: `/opt/backups/steps_20260828_codex_previred_demo/`
- Demo-SyS: `/opt/backups/steps_20260828_codex_previred_demosys/`

Cada dump fue comprobado con `pg_restore --list` antes de modificar su base.
Sus SHA-256 son:

- Desarrollo: `c46e6e6685ae99d022246e7500022a2a56e147ded69c713ccbdd447125e9b9c9`;
- Demo: `ff66d181c6f7ad0ee0f21381f9f3c87320ce780fff34d0ec1713068826bad835`;
- Demo-SyS: `82f0391d481d8f2256ac8362f70f38c609b59d7631a7e9a825fdba4fc6c4ffac`.

Además se respaldaron localmente los módulos recibidos de Claude en:
`C:\Users\tito4\Documents\Claude_Odoo_Agricola\backups\previred_before_codex_20260827_225445`.

## Archivos de soporte

- Matriz de los 105 campos: `docs/PREVIRED_MATRIZ.md`.
- Diseño y operación: `step_hr_previred/README.md`.
- Historial técnico: `step_hr_previred/CHANGELOG.md`.
