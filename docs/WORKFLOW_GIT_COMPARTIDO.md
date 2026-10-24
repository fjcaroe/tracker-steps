# Trabajo compartido entre Claude y Codex

Regla de Fernando, 03-10-2026: quien termina una tarea deja sus cambios útiles
en la rama y subidos, sin código local sin trazar.

## Inicio

1. Consultar `git status --short`, `git branch --show-current`, `git worktree list`
   y la documentación del producto. Elegir la rama por el producto/ticket, nunca
   por la rama que quedó abierta de una tarea anterior.
2. Hacer fetch y verificar la rama remota vigente. Steps Móvil parte de
   `origin/codex/steps-movil`; Web Tracker sigue
   `origin/codex/web-tracker-redesign`. Los otros productos conservan las ramas
   y destinos documentados en sus tickets/runbooks.
3. Usar un worktree propio si otro agente trabaja en el mismo producto. No
   hacer checkout, reset o limpieza sobre archivos del otro agente.
4. Si hay cambios anteriores: revisar contenido y autoría, guardar una copia
   recuperable fuera del checkout y registrar/integrar lo útil. No ejecutar
   scripts encontrados por casualidad: pueden corresponder a una acción ya hecha.

## Durante el desarrollo

- Código de producto en sus módulos; herramientas reutilizables en `tools/` o
  `scripts/`; pruebas en su conjunto de pruebas. No desarrollar en `tmp/`.
- Los adjuntos de clientes, resultados de consultas, documentos generados,
  capturas, dumps y paquetes se guardan fuera del checkout, en
  `~/.codex/local-artifacts/<tarea>/`. Los datos privados y secretos no se suben
  al repositorio público, aunque hayan sido necesarios para una prueba.
- Integrar mejoras concurrentes sobre la base vigente y verificar el resultado.
  No desplegar ramas alternativas que sustituyan avances de otros agentes.
- Un cambio funcional incompleto pero necesario para retomar el trabajo debe
  quedar en un commit y rama explícitos, con su estado documentado. No en stash
  ni en un archivo ignorado.

## Cierre

1. Revisar el diff y archivos nuevos; comprobar que no contengan secretos ni
   datos de clientes. Ejecutar las pruebas pertinentes.
2. Crear commits que expliquen el cambio. Subir la rama. Si el producto tiene
   una base canónica de entrega, integrarlo allí con las verificaciones necesarias.
3. Si se pidió desplegar, publicar el commit exacto según el runbook del producto
   y verificar lo servido. Commit y push por sí solos no prueban el despliegue.
4. Ejecutar `python tools/git/verify_handoff.py --require-pushed`.
   Para barrer todos los worktrees: agregar `--all-worktrees`.
5. Entregar resultado, rama/commit y validación. No afirmar cierre limpio si el
   comprobador detecta cambios pendientes. Explicar un bloqueo real sin perder
   los cambios ya guardados.

El comprobador es de solo lectura. No hace commits, pushes, merges ni borra
archivos. Tampoco prueba que las ramas de distintos módulos puedan fusionarse:
esa integración necesita revisar código, dependencias y ambientes.
