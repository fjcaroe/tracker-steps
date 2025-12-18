// src/pages/CostCentersPage.tsx
/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useState } from "react";

type CostCenter = {
  id: number;
  name: string;
  external_id?: string | null;
  hectares?: number | null;
};

const apiBaseUrl =
  ((import.meta.env.VITE_API_BASE_URL as string | undefined) || "http://localhost:8000").replace(
    /\/+$/,
    ""
  );

const CostCentersPage = () => {
  const [costCenters, setCostCenters] = useState<CostCenter[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [externalId, setExternalId] = useState("");
  const [hectares, setHectares] = useState("");

  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const loadCostCenters = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetch(`${apiBaseUrl}/cost_centers`);
      if (!res.ok) {
        const text = await res.text();
        throw new Error(`Error ${res.status}: ${text}`);
      }
      const data: CostCenter[] = await res.json();
      setCostCenters(data);
    } catch (e: any) {
      console.error(e);
      setError(e?.message || "No se pudieron cargar los centros de costo.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadCostCenters();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setSaveError("El nombre del centro de costo es obligatorio.");
      return;
    }

    const hectaresNumber = hectares ? Number(hectares) : null;
    if (hectares && Number.isNaN(hectaresNumber)) {
      setSaveError("Las hectáreas deben ser un número.");
      return;
    }

    try {
      setSaving(true);
      setSaveError(null);

      const body: any = {
        name: name.trim(),
        external_id: externalId.trim() || null,
      };
      if (hectaresNumber != null) {
        body.hectares = hectaresNumber;
      }

      const res = await fetch(`${apiBaseUrl}/cost_centers`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(`Error ${res.status}: ${text}`);
      }

      setName("");
      setExternalId("");
      setHectares("");
      await loadCostCenters();
    } catch (e: any) {
      console.error(e);
      setSaveError(e?.message || "No se pudo crear el centro de costo.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="card entity-page">
      {/* Formulario */}
      <div>
        <div className="card-header">
          <div>
            <div className="card-title">Centros de costo</div>
            <div className="card-subtitle">
              Predios / unidades de negocio donde se registran las máquinas y recorridos.
            </div>
          </div>
        </div>

        <form className="form-grid" onSubmit={handleCreate}>
          <div className="form-field">
            <label className="form-label">Nombre centro de costo *</label>
            <input
              className="form-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Ej: Fundo Los Aromos - Lote Norte"
            />
          </div>

          <div className="form-field">
            <label className="form-label">ID externo (Odoo / ERP)</label>
            <input
              className="form-input"
              value={externalId}
              onChange={(e) => setExternalId(e.target.value)}
              placeholder="Código en Odoo u otro sistema"
            />
          </div>

          <div className="form-field">
            <label className="form-label">Hectáreas (opcional)</label>
            <input
              className="form-input"
              value={hectares}
              onChange={(e) => setHectares(e.target.value)}
              placeholder="Ej: 42.5"
            />
          </div>

          {saveError && <div className="tracker-error">⚠️ {saveError}</div>}

          <div>
            <button
              type="submit"
              className="form-button-primary"
              disabled={saving}
            >
              {saving ? "Guardando..." : "Agregar centro de costo"}
            </button>
          </div>
        </form>
      </div>

      {/* Tabla */}
      <div>
        {error && <div className="tracker-error">⚠️ {error}</div>}
        <div className="entity-table-wrapper">
          {loading ? (
            <div className="sessions-loading">Cargando centros de costo…</div>
          ) : costCenters.length === 0 ? (
            <div className="sessions-empty">
              No hay centros de costo aún. Crea uno con el formulario.
            </div>
          ) : (
            <table className="entity-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Nombre</th>
                  <th>ID externo</th>
                  <th>Hectáreas</th>
                </tr>
              </thead>
              <tbody>
                {costCenters.map((c) => (
                  <tr key={c.id}>
                    <td>{c.id}</td>
                    <td>{c.name}</td>
                    <td>{c.external_id || "—"}</td>
                    <td>{c.hectares != null ? c.hectares : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </section>
  );
};

export default CostCentersPage;
