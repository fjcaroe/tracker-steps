# Qué sigue — Gestión y Costos, después del Corte V2 G (2026-09-07)

Estado al cierre de esta sesión: **Cortes V2 A–G completos.** A–F
implementados y verificados contra Odoo real (`odoo-new`, bases
desechables); G es una auditoría que concluyó legítimamente sin
adaptadores nuevos (ver `HANDOFF_V2_CORTE_G.md`). Nada de esto está
commiteado ni desplegado — todo vive sólo en este worktree
(`C:\Users\tito4\Documents\Odoo-gestion-costos`, rama `codex/gestion-costos`).

Versión actual: `step_management_costs` `18.0.20.0.0` +
`step_management_costs_agriculture` `18.0.1.0.0` +
`step_management_costs_machinery` `18.0.1.0.0`.

## 1. Lo único que queda del alcance original de los cortes V2 A–G

### 1.1 Puente BPA (foliar) — el único candidato con camino técnico
Corte V2 G lo identificó como el único de los 8 dominios auditados con
datos de origen suficientes (`x_aplicacion_foliar`, addon real
`step_bpa_irrigation`). No se construyó porque faltan dos decisiones que
no me corresponde tomar unilateralmente:

- **¿Automático o manual?** El modelo destino no tiene ningún estado de
  anulación — si se crea mal, no hay forma limpia de deshacerlo. Un botón
  "Generar borrador BPA" que el usuario dispare a propósito es mucho más
  seguro que crear automáticamente al autorizar la OP.
- **¿Dependencia dura o lectura defensiva de `step_bpa_irrigation`?** El
  propio código real de `odoo-new` no es consistente en esto (ver
  `HANDOFF_V2_CORTE_G.md` §3.7 para el detalle con las dos citas de código
  encontradas).

Con esas dos decisiones tomadas, el trabajo de construcción es de un
alcance comparable al Corte V2 E (un addon puente nuevo, un método de
generación con idempotencia propia, vistas, pruebas contra Odoo real) —
probablemente una sesión completa por sí sola.

### 1.2 Auditoría final de `MATRIZ_REQUISITOS.md`
Se mantuvo al día corte a corte (cada handoff agrega su propia sección),
pero nunca se hizo la pasada explícita de "auditar TODO el backlog de una
vez contra el estado real del código", como pedía la instrucción original.
Con los 7 cortes cerrados es un buen momento para esa pasada consolidada:
recorrer cada fila de la matriz y confirmar que el estado marcado sigue
siendo cierto contra el código actual (no debería haber sorpresas grandes
— se fue verificando en el camino — pero es la única pieza explícitamente
pedida que no se hizo como paso independiente).

## 2. Despliegue (nunca ejecutado en esta sesión)

El runbook acordado: `git push` de esta rama, luego a Desarrollo
(`LAB_TAREAS`) primero, y sólo si sale bien, a Demo (`STEPS_DEMO`) —
**nunca Demo-SyS**. Nada de esto se ha hecho. Antes de ejecutarlo:

1. Decidir si el puente BPA (§1.1) se construye antes o se despliega sin
   él (es perfectamente desplegable sin él — es 100% opcional y
   `auto_install` sólo si `step_bpa_irrigation` estuviera presente, que
   hoy no lo está en el manifiesto de nada de lo construido).
2. Pedir autorización explícita para el despliegue mismo — no está
   autorizado por instrucción permanente, es una decisión operacional del
   cliente sobre cuándo.
3. Antes de desplegar a Desarrollo: un backup de `LAB_TAREAS`, y repetir el
   mismo patrón de verificación (clean install + upgrade) que ya se hizo
   contra clones desechables, esta vez contra el `LAB_TAREAS` real (no un
   clon) — con la salvedad del punto 3 más abajo.

## 3. Bloqueo de infraestructura para quien administre `odoo-new`

`res_company.security_lead` (campo de `sale_stock`) quedó sin poder
resolver su valor por defecto fuera de modo interactivo en `LAB_TAREAS`
desde hoy ~04:06 — confirmado **persistente**, no transitorio (probado 3
veces en el mismo día, horas de diferencia, sin cambios). Esto bloquea
**cualquier** verificación por upgrade contra un clon de `LAB_TAREAS`
(no sólo la de este módulo) porque cualquier prueba que cree una
`res.company` nueva falla. No se identificó la causa raíz exacta más
allá de que `sale_stock` se modificó ese día — alguien con acceso de
administrador a esa instancia debería revisarlo (probablemente falta un
`ir.default` a nivel de empresa para ese campo). Mientras no se resuelva,
**la verificación por upgrade real de `LAB_TAREAS` seguirá bloqueada para
cualquier corte futuro**, no sólo los de este módulo — vale la pena
resolverlo antes del despliegue, aunque técnicamente no impide desplegar
(la vía de instalación limpia ya viene siendo la verificación decisiva).

## 4. Limitación externa ya documentada, sin acción pendiente real

`test_fase2_variance.py` (hereda de `AccountTestInvoicingCommon`, común de
Odoo core) es incompatible con `step_hr.grupo_labor` en instalación limpia
combinada — defecto de diseño de `step_hr` (campo obligatorio sin default
utilizable sobre `product.template`), no de este addon, y no corregible
sin tocar código ajeno. Aparece igual en cada corte desde V2 D; no requiere
ninguna acción nueva, sólo queda anotado aquí para que no sorprenda en la
próxima verificación.

## 5. Lo que NO quedó pendiente (para no reabrir sin necesidad)

Todo el resto de los 7 frentes de los Cortes V2 A–F está implementado,
verificado contra Odoo real y documentado: maestros agrícolas reales
(V2 D), presupuesto de maquinaria (V2 E), comparativos/tablero/fuera de OP
(V2 F), más lo heredado de cortes anteriores (presupuesto, planificación,
programas fito/fertilización, necesidades de stock, Orden de Producción,
carga histórica). Los bloqueos permanentes ya conocidos siguen igual, sin
cambios ni novedades: K3, H1, K5, D20, BPA-Riego (el documento del
cliente, no el addon — son cosas distintas, ver `HANDOFF_V2_CORTE_G.md`
§3.7/§3.8 para el addon), usuarios reales/UAT.

## 6. Documentos de referencia

- `DECISION_LOG.md` — todas las decisiones, sección por corte (D-A hasta D-Q).
- `ADR_001_ARQUITECTURA_Y_CONTABILIDAD.md` — arquitectura y contabilidad.
- `MATRIZ_REQUISITOS.md` — estado de cada requisito, sección por corte.
- `HANDOFF_V2_CORTE_A.md` … `HANDOFF_V2_CORTE_G.md` — entrega de cada corte,
  con la evidencia exacta de verificación contra Odoo real.
