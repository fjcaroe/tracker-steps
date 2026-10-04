# Astra: primera entrega visual de Steps App

## Encargo

Mejora la presentación de la app móvil Steps existente. Entrega cambios implementados y comprobados en navegador. La estructura funcional ya existe; esta sesión se concentra en una primera mejora visual coherente, sin ampliar funcionalidades.

Parte de `origin/codex/steps-movil` actualizado, en un worktree propio. Lee `AGENTS.md`, `mobile/AGENTS.md` y `docs/STEPS_APP_UI_CONTRATO.md`. Consulta otros documentos solo cuando una decisión concreta lo requiera. No reinvestigues el backend ni reconstruyas el inventario.

## Dirección visual

Steps es una herramienta de trabajo en terreno. Busca una apariencia cuidada y clara: verde profundo como identidad, fondos neutros, acentos discretos, tipografía legible y jerarquía consistente. Usa la identidad existente; no inventes un logotipo oficial.

Destaca la empresa activa, la siguiente acción y el estado de sincronización. Presenta los módulos como tarjetas reconocibles, con iconos y acciones claras. Mantén el español y la legibilidad bajo uso práctico. Evita adornos que compitan con los datos, animaciones extensas y dependencias innecesarias. Usa recursos existentes o SVG sencillos.

## Alcance y orden

1. Tokens y componentes compartidos: botones, campos, tarjetas, avisos, estados, barra superior e inferior. Unifica espaciados, contraste, foco y tamaños táctiles de al menos 48 px.
2. Acceso (`Welcome`), selección de empresa (`CompanyPicker`) y portada (`Portal`): mejora jerarquía, composición y tarjetas.
3. Colaciones y Movilización: aplica los mismos patrones a formularios, servicios, historial y estados existentes. Conserva acciones y confirmaciones.
4. Sincronización: deja muy clara la diferencia entre pendiente, confirmado, requiere acceso y rechazado. Perfil e incorporación reciben coherencia mediante componentes compartidos; no requieren rediseño profundo en esta entrega.

Trabaja una sola propuesta visual. No prepares variantes, una biblioteca nueva ni una reconstrucción de Tracker. Comprueba que los estilos globales no deterioren Tracker; conserva sus vistas y lógica.

## Límites

Archivos de presentación: `mobile/src/shared/ui/*`, `mobile/src/styles.css`, pantallas indicadas y JSX/clases de `mobile/src/app/App.tsx` cuando sea necesario para la estructura común.

Preserva hooks, callbacks, condiciones, navegación, nombres accesibles y textos de acciones. No añadas router ni cambies sesión, permisos, contratos, APIs, colas, migraciones, almacenamiento, servicios, configuración nativa u Odoo. No añadas un botón Google/Apple operativo si su integración no existe. No ocultes errores, pendientes ni la franja de demostración para mejorar una captura.

Una necesidad funcional encontrada se informa como pendiente concreto; no amplía automáticamente este encargo.

## Comprobación acotada

Ejecuta `cd mobile && npm run demo` y abre `/?scenario=<nombre>`.

- Revisa `conductor`, `beneficiaria` y `pendientes` a 390 px de ancho; en `conductor` abre el servicio y revisa sus acciones.
- Revisa acceso con `nuevo` y selección con `multiempresa`.
- Comprueba `sin-modulos` para el estado vacío, un caso a 360 px y un caso oscuro.
- Verifica navegación, campos, mensajes largos, contraste, foco, áreas seguras y ausencia de desplazamiento horizontal o contenido tapado por la barra inferior.

Haz una pasada visual y una corrección de los problemas detectados. Guarda unas pocas capturas representativas fuera del checkout. Si no tienes navegador, declara esa limitación y no presentes el build como revisión visual.

Ejecuta `npm test` y `npm run build` al finalizar, además de los checks exigidos por las instrucciones del producto. Repite solo lo pertinente si hay fallos o cambios posteriores. No cambies expectativas para hacer pasar una regresión ni añadas pruebas que solo comprueben clases CSS. No necesitas levantar nuevamente Odoo para esta tarea visual.

## Cierre

Publica los cambios y una PR hacia `codex/steps-movil`, sin mergear ni desplegar el piloto por este encargo. Ejecuta `python tools/git/verify_handoff.py --require-pushed`.

Entrega un resumen breve: qué mejoró, archivos principales, escenarios inspeccionados, resultados de pruebas, rama/commit/PR y límites reales. La entrega termina cuando la propuesta visual priorizada funciona y está publicada; no continúes agregando trabajo para consumir cuota. No afirmar validación Android/iOS a partir del navegador.
