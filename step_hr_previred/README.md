# Steps — Previred por departamento (core)

Capa técnica del archivo Previred. **No conoce ningún motor de nómina**:
depende sólo de `hr_payroll`, de modo que se instala igual en Desarrollo y
Demo (motor Blueminds) y en Demo-SyS (motor SimpleDigital).

```text
Nómina Steps  (una sola UX)
  └─ step_hr_previred                    core: dataset canónico, validación,
     │                                   TXT/ZIP/Excel, perfiles, lote, permisos
     ├─ step_hr_previred_blueminds       bridge → l10n_cl_hr
     └─ step_hr_previred_simpledigital   bridge → l10n_cl_simpledigital_payroll
```

Cada bridge declara su dependencia real del proveedor, aporta la **matriz de
los 105 campos**, su perfil de formato y la **redirección del menú Previred
que el motor ya publicaba**. No hay una segunda aplicación ni un segundo menú:
el usuario ve un solo flujo Previred.

## Qué produce

| Modo | Formato | Entrega |
|---|---|---|
| Consolidado | TXT | un archivo |
| Por departamento | TXT | uno por departamento, en ZIP con manifiesto |
| Consolidado + departamentos | TXT | ambos, en un solo ZIP |
| cualquiera | Excel | libro de revisión con hoja `Resumen` |

Previred admite **TXT, CSV o ZIP**. El XLSX es un archivo de control para
personas, va rotulado `Archivo de revisión; no cargar en Previred` y no
aparece en el manifiesto de archivos cargables.

## Dataset canónico y correcciones deliberadas

Hay **una sola** función que construye el lote (`step.previred.extractor.
build_dataset`); el consolidado, cada archivo por departamento y todos los
Excel son particiones de su resultado. Ninguna salida recalcula un importe.

La fila base sigue viniendo del generador del proveedor, que es lo que la
empresa concilia hoy. El core normaliza y completa únicamente los campos que
la especificación oficial vigente exige (entre ellos 14, 93, 94 y 95), además
de corregir alcance y seguridad. Cada diferencia queda cubierta por pruebas:

| Defecto del generador anterior | Corrección |
|---|---|
| Blueminds no filtraba compañía | el lote es por empresa; lo ajeno se descarta |
| Blueminds no filtraba estado | sólo estados validados; nunca `draft` ni `cancel` |
| Estados como lista global | cada motor declara los suyos y los justifica |
| Compañía tomada de la URL | se revalida en servidor, en el asistente y en la ruta |
| `sudo()` sin permiso previo | se exige el grupo antes de generar |

## Líneas anexas

La especificación exige que una línea anexa (01/02/03) vaya inmediatamente
después de su línea principal; si no, Previred no la contabiliza. La unidad de
agrupación es el **trabajador**, no la línea, así que al partir por
departamento las anexas viajan con su principal.

**No se inventan anexas.** Cada motor declara si tiene datos que las
justifiquen:

- **SimpleDigital** sí: `hr.payslip.previred_movement_ids`. Se validan sus
  condicionales (fechas obligatorias según el código de movimiento, datos del
  afiliado voluntario en las líneas 03).
- **Blueminds** no: su movimiento de personal es un único código
  (`hr.payslip.movimientos_personal`) que ya viaja en el campo 15 de la línea
  principal. Emitir anexas ahí declararía movimientos inexistentes.

## Matriz de los 105 campos

Ninguna correspondencia entre regla salarial y campo oficial se dedujo: la
matriz se **genera desde el código** del generador de cada proveedor.

- Documento: [`docs/PREVIRED_MATRIZ.md`](../docs/PREVIRED_MATRIZ.md)
- En la interfaz: perfil de formato → pestaña «Matriz de los 105 campos»
- Regenerar: `python tools/regen_previred_matrix.py /opt/rrhh`

## Formato oficial

Formato estándar largo variable, por separador, seleccionado por vigencia:

* **versión 84** para remuneraciones entre agosto de 2025 y julio de 2026;
* **versión 98, agosto de 2026**, para remuneraciones desde agosto de 2026.

Fuente oficial vigente:
<https://www.previred.com/documents/FormatosArchivos/FormatoLargoVariablePorSeparador.pdf>

La versión, su fuente y su vigencia viven en un **perfil de formato**, y cada
lote queda atado al perfil con el que se produjo.

## Permisos

| Grupo | Permite |
|---|---|
| Previred: consultar resumen | abrir el asistente, validar y ver el detalle |
| Previred: generar exportaciones | producir TXT, Excel y ZIP |
| Previred: administrar perfiles de formato | editar versión, motor y estados |
| Previred: auditar lotes | consultar el historial y los hashes |

## Lo que este módulo NO hace

* No envía nada a Previred ni confirma la aceptación de un archivo.
* No recalcula ni confirma liquidaciones.
* No modifica ningún addon de proveedor.
* No guarda RUT, nombres ni importes por persona en la auditoría.
