import { lazy, Suspense, useEffect, useState } from "react";

const ClassicApp = lazy(() => import("./ClassicApp"));
const FleetWorkspace = lazy(() => import("./pages/FleetWorkspace"));

type Mode = "probing" | "portal" | "classic";

/**
 * Un solo build para todos los sitios: si el host tiene el puente Odoo (`/steps_tracker/context`)
 * se muestra el portal de flota (que incluye la operación clásica); si no existe (404, p. ej. el
 * sitio de producción compartido) se muestra la operación clásica con su login propio.
 */
async function detectMode(): Promise<Mode> {
  if (import.meta.env.VITE_ODOO_PORTAL === "true") return "portal";
  try {
    const r = await fetch("/steps_tracker/context", { credentials: "same-origin", redirect: "manual", headers: { Accept: "application/json" } });
    return r.status === 404 ? "classic" : "portal";
  } catch { return "classic"; }
}

function Loader() {
  return <main className="view-loader" aria-live="polite" aria-busy="true"><span className="view-loader__spinner" aria-hidden="true"/><span>Cargando módulo…</span></main>;
}

export default function App() {
  const [mode, setMode] = useState<Mode>("probing");
  useEffect(() => { void detectMode().then(setMode); }, []);
  if (mode === "probing") return <Loader/>;
  return <Suspense fallback={<Loader/>}>{mode === "portal" ? <FleetWorkspace/> : <ClassicApp/>}</Suspense>;
}
