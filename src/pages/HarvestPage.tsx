import { env } from "../config/env";

const steps = [
  { number: "01", title: "Registrar", text: "Identifique la cosecha, fundo, cuartel, variedad, cuadrilla y cantidades." },
  { number: "02", title: "Revisar y aprobar", text: "Valide tarjas, personas y kilos antes de avanzar el estado." },
  { number: "03", title: "Costear", text: "Calcule el costo propio o contratista conservando el detalle original." },
  { number: "04", title: "Contabilizar y recibir", text: "Genere la contabilización y controle la recepción en bodega." },
];

const areas = [
  { icon: "P", title: "Cosecha propia", text: "Cuadrillas, registro diario, costeo y contabilización." },
  { icon: "C", title: "Contratistas", text: "Tarifas, tarjas, proformas y recepción de fruta." },
  { icon: "H", title: "Histórico", text: "Consulta de temporadas, fundos, especies, variedades y kilos." },
  { icon: "M", title: "Maestros", text: "Ubicaciones, procesos, temporadas, fundos y productos." },
];

export default function HarvestPage() {
  const openCosecha = () => window.open(env.cosechaOdooUrl, "_blank", "noopener,noreferrer");

  return (
    <section className="harvest-hub">
      <header className="harvest-hub__hero">
        <div className="harvest-hub__copy">
          <span className="section-kicker">CONECTADO CON ODOO · LAB_TAREAS</span>
          <h2>La cosecha completa, en un flujo claro</h2>
          <p>Esta pestaña reúne el acceso a la aplicación desarrollada para registrar, revisar, costear y recibir la cosecha sin mezclar sus datos con el monitoreo de transportes.</p>
          <div className="harvest-hub__actions">
            <button type="button" onClick={openCosecha}>Abrir aplicación Cosecha <span>↗</span></button>
            <small>Se abrirá Odoo en una pestaña nueva y mantendrá sus permisos habituales.</small>
          </div>
        </div>
        <div className="harvest-hub__illustration" aria-hidden="true"><i/><i/><i/><span><b>4</b><small>etapas controladas</small></span></div>
      </header>

      <section className="harvest-hub__notice"><span>✓</span><div><b>Una sola fuente de información</b><p>Los registros continúan viviendo en Odoo. Transportes actúa como puerta de entrada y no crea copias que puedan quedar desactualizadas.</p></div></section>

      <div className="harvest-hub__content">
        <section className="harvest-hub__panel">
          <header><span className="section-kicker">FLUJO DE TRABAJO</span><h3>Qué puede hacer en Cosecha</h3><p>La portada nueva de Odoo muestra indicadores y accesos directos, pero mantiene las validaciones y estados originales.</p></header>
          <div className="harvest-flow">{steps.map((step, index) => <article key={step.number}><i>{step.number}</i><div><b>{step.title}</b><p>{step.text}</p></div>{index < steps.length - 1 && <em/>}</article>)}</div>
        </section>

        <aside className="harvest-hub__panel harvest-hub__help">
          <header><span className="section-kicker">ACCESO SEGURO</span><h3>Antes de comenzar</h3></header>
          <ol><li>Abra la aplicación con el botón superior.</li><li>Inicie sesión en Odoo si se lo solicita.</li><li>Seleccione <b>Cosecha</b>; verá el nuevo tablero.</li></ol>
          <button type="button" onClick={openCosecha}>Ir a Cosecha en Odoo</button>
        </aside>
      </div>

      <section className="harvest-areas">{areas.map((area) => <article key={area.title}><i>{area.icon}</i><div><b>{area.title}</b><p>{area.text}</p></div></article>)}</section>
    </section>
  );
}
