# Evidencia: los 3 hallazgos de la PR #15 fallan sin el arreglo y quedan corregidos

Reproductor: `tools/reviews/pr15_repro.cjs` (variante parametrizada del script de revisión `codex/cierre-cambios-locales:tools/reviews/pr15_repro.cjs`). Ejecutado el 04-10-2026.

| Caso | Head de la PR #15 (`8797edb`) | Rama `codex/steps-movil` |
| --- | --- | --- |
| 1. Fallo al guardar rechazados seguido de borrado de pendientes | `{"pending":0,"archived":0,"lost":true}` → **se pierde el lote** | `{"pending":1,"archived":0,"lost":false}` → el lote sigue pendiente |
| 2. Descarte silencioso por límite (5.001 puntos) | `{"archived":5000,"missingOldest":true}` → **se pierde el más antiguo** | `{"archived":5001,"missingOldest":false}` |
| 3. Respuesta atrasada reofrece una jornada cerrada | `{"offered":["closed-during-get"]}` → **reofrece** | `{"offered":[]}` |

Cómo repetirlo:

```bash
git worktree add /tmp/pr15-head 8797edb && ln -s "$PWD/mobile/node_modules" /tmp/pr15-head/mobile/node_modules
node tools/reviews/pr15_repro.cjs /tmp/pr15-head/mobile                       # muestra los 3 defectos
LIB_DIR=modules/tracker/lib SCREENS_DIR=modules/tracker/screens \
  node tools/reviews/pr15_repro.cjs "$PWD/mobile"                             # muestra los 3 corregidos
```

Nota sobre el caso 3: el reproductor original inyectaba el cierre sin pasar por la pantalla. En la app real, terminar la jornada anota el
identificador en un historial persistente (`finishedStore`) antes de encolar el cierre; la variante lo hace igual. Además hay regresiones
unitarias en `mobile/src/modules/tracker/lib/lib.test.ts` (cuota llena, 5.001 puntos, corte entre pasos, respuestas obsoletas).

Corrección aplicada en el commit `162c3cf`; la compuerta de propietario de datos locales y la copia de seguridad previa a la migración se añadieron después.
