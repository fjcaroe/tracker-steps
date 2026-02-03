// src/pages/MastersPage.tsx
import DriversPage from "./DriversPage";
import MachinesPage from "./MachinesPage";
import CostCentersPage from "./CostCentersPage";
import FieldsPage from "./FieldsPage";
import ActivitiesLaborsPage from "./ActivitiesLaborsPage"; // ✅ nuevo

export type MastersView =
  | "drivers"
  | "machines"
  | "activitiesLabors" // ✅ nuevo
  | "costCenters"
  | "fields";

type Props = {
  value: MastersView;
  onChange: (v: MastersView) => void;
};

const ITEMS: { key: MastersView; label: string; subtitle: string }[] = [
  {
    key: "drivers",
    label: "Choferes",
    subtitle: "Catálogo de conductores.",
  },
  {
    key: "machines",
    label: "Maquinarias",
    subtitle: "Registro de máquinas (capacidad, consumos, defaults).",
  },
  {
    key: "activitiesLabors",
    label: "Actividades y Labores",
    subtitle: "Maestros operacionales: actividades (padre) y labores (hijas).",
  },
  {
    key: "costCenters",
    label: "Centro de costo",
    subtitle:
      "CC + catálogos: Fundo, Sector (SDP), Especie y Variedad (incluidos en esta pantalla).",
  },
  {
    key: "fields",
    label: "Campos / Polígonos",
    subtitle: "Cuarteles, polígonos y asociaciones.",
  },
];

export default function MastersPage({ value, onChange }: Props) {
  const current = ITEMS.find((x) => x.key === value) ?? ITEMS[0];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {/* Header + selector */}
      <section className="card">
        <div className="card-header">
          <div>
            <div className="card-title">Maestros</div>
            <div className="card-subtitle">
              Administración de catálogos base del sistema.
            </div>
          </div>

          {/* Select (útil en móvil / simple) */}
          <div style={{ marginLeft: "auto", minWidth: 260 }}>
            <select
              className="app-nav-select"
              value={value}
              onChange={(e) => onChange(e.target.value as MastersView)}
            >
              {ITEMS.map((it) => (
                <option key={it.key} value={it.key}>
                  {it.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Botonera (desktop) */}
        <div
          style={{
            padding: "0 14px 14px",
            display: "flex",
            gap: 8,
            flexWrap: "wrap",
          }}
        >
          {ITEMS.map((it) => (
            <button
              key={it.key}
              type="button"
              className={`app-nav-button ${value === it.key ? "active" : ""}`}
              onClick={() => onChange(it.key)}
              title={it.subtitle}
            >
              {it.label}
            </button>
          ))}
        </div>

        {/* Contexto de la subpestaña */}
        <div style={{ padding: "0 14px 14px" }}>
          <div className="card-subtitle">{current.subtitle}</div>
        </div>
      </section>

      {/* Contenido */}
      {value === "drivers" && <DriversPage />}
      {value === "machines" && <MachinesPage />}
      {value === "activitiesLabors" && <ActivitiesLaborsPage />}
      {value === "costCenters" && <CostCentersPage />}
      {value === "fields" && <FieldsPage />}
    </div>
  );
}
