// src/pages/FieldsPage.tsx
/* eslint-disable @typescript-eslint/no-explicit-any */

import { useCallback, useEffect, useState } from "react";
import type { CSSProperties } from "react";
import {
  GoogleMap,
  Polygon,
  Marker,
  useJsApiLoader,
} from "@react-google-maps/api";
import { MAPS_LIBRARIES, MAPS_LOADER_ID } from "../mapsConfig";

const apiBaseUrl =
  ((import.meta.env.VITE_API_BASE_URL as string | undefined) ||
    "http://localhost:8000").replace(/\/+$/, "");

type CostCenter = {
  id: number;
  name: string;
};

type FieldPolygon = {
  id: number;
  name: string;
  cost_center_id: number | null;
  cost_center_name?: string | null;
  color?: string | null;
  polygon: { lat: number; lon: number }[];
};

type DraftPoint = google.maps.LatLngLiteral;

const defaultCenter: google.maps.LatLngLiteral = {
  lat: -33.45, // Santiago aprox
  lng: -70.65,
};

const polygonOptions: google.maps.PolygonOptions = {
  strokeColor: "#22c55e",
  strokeOpacity: 0.9,
  strokeWeight: 2,
  fillColor: "#22c55e",
  fillOpacity: 0.15,
  clickable: false,
  editable: false,
  draggable: false,
};

const existingPolygonOptions: google.maps.PolygonOptions = {
  strokeColor: "#1d4ed8",
  strokeOpacity: 0.9,
  strokeWeight: 2,
  fillColor: "#1d4ed8",
  fillOpacity: 0.14,
  clickable: true,
};

const mapContainerStyle: CSSProperties = {
  width: "100%",
  minHeight: "460px",
  borderRadius: "14px",
  overflow: "hidden",
};

const FieldsPage = () => {
  const { isLoaded, loadError } = useJsApiLoader({
    id: MAPS_LOADER_ID,
    googleMapsApiKey: import.meta.env.VITE_GOOGLE_MAPS_API_KEY as string,
    libraries: MAPS_LIBRARIES,
  });

  const [costCenters, setCostCenters] = useState<CostCenter[]>([]);
  const [fields, setFields] = useState<FieldPolygon[]>([]);
  const [selectedFieldId, setSelectedFieldId] = useState<number | null>(null);

  const [draftPoints, setDraftPoints] = useState<DraftPoint[]>([]);
  const [isDrawing, setIsDrawing] = useState(false);

  const [fieldName, setFieldName] = useState("");
  const [selectedCostCenterId, setSelectedCostCenterId] = useState<string>("");
  const [color, setColor] = useState<string>("#22c55e");

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [mapRef, setMapRef] = useState<google.maps.Map | null>(null);
  const [mapCenter, setMapCenter] = useState<google.maps.LatLngLiteral>(
    defaultCenter
  );
  const [locating, setLocating] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  // Edición de polígonos existentes
  const [editingFieldId, setEditingFieldId] = useState<number | null>(null);
  const [activePolygonRef, setActivePolygonRef] =
    useState<google.maps.Polygon | null>(null);

  // --- centro inicial en el primer campo, si existe ---
  useEffect(() => {
    if (fields.length > 0 && fields[0].polygon.length > 0) {
      const p = fields[0].polygon[0];
      const center = { lat: p.lat, lng: p.lon };
      setMapCenter(center);
      if (mapRef) {
        mapRef.panTo(center);
      }
    }
  }, [fields, mapRef]);

  // --- cargar centros de costo y campos existentes ---
  useEffect(() => {
    const fetchData = async () => {
      try {
        const [ccRes, fieldsRes] = await Promise.all([
          fetch(`${apiBaseUrl}/cost_centers`),
          fetch(`${apiBaseUrl}/fields`),
        ]);

        if (ccRes.ok) {
          setCostCenters(await ccRes.json());
        }

        if (fieldsRes.ok) {
          const data: FieldPolygon[] = await fieldsRes.json();
          setFields(data);
        }
      } catch (e: any) {
        console.error(e);
        setError(
          "No se pudieron cargar los centros de costo o los campos existentes."
        );
      }
    };

    fetchData();
  }, []);

  // --- centrar mapa en mi ubicación ---
  const handleCenterOnMe = () => {
    setLocalError(null);

    if (!navigator.geolocation) {
      setLocalError("Este navegador no soporta geolocalización.");
      return;
    }

    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const coords = {
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
        };
        setMapCenter(coords);
        if (mapRef) {
          mapRef.panTo(coords);
          mapRef.setZoom(19);
        }
        setLocating(false);
      },
      (err) => {
        console.error(err);
        setLocalError("No se pudo obtener tu ubicación actual.");
        setLocating(false);
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 0,
      }
    );
  };

  // --- click en mapa para dibujar polígono nuevo ---
  const handleMapClick = useCallback(
    (e: google.maps.MapMouseEvent) => {
      if (!isDrawing) return;
      if (!e.latLng) return;

      const lat = e.latLng.lat();
      const lng = e.latLng.lng();

      setDraftPoints((prev) => [...prev, { lat, lng }]);
    },
    [isDrawing]
  );

  const handleStartDrawing = () => {
    setError(null);
    setSuccess(null);
    setDraftPoints([]);
    setIsDrawing(true);
  };

  const handleUndoPoint = () => {
    setDraftPoints((prev) => prev.slice(0, -1));
  };

  const handleClearDraft = () => {
    setDraftPoints([]);
  };

  const canSave =
    fieldName.trim().length > 0 &&
    draftPoints.length >= 3 &&
    !saving &&
    isLoaded;

  const handleSaveField = async () => {
    if (!canSave) return;

    try {
      setSaving(true);
      setError(null);
      setSuccess(null);

      const payload = {
        name: fieldName.trim(),
        cost_center_id: selectedCostCenterId
          ? Number(selectedCostCenterId)
          : null,
        color,
        polygon: draftPoints.map((p) => ({
          lat: p.lat,
          lon: p.lng,
        })),
      };

      const res = await fetch(`${apiBaseUrl}/fields`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(`Error ${res.status}: ${text}`);
      }

      const created: FieldPolygon = await res.json();
      setFields((prev) => [created, ...prev]);
      setSelectedFieldId(created.id);

      setSuccess("Campo guardado correctamente.");
      setFieldName("");
      setDraftPoints([]);
      setIsDrawing(false);
    } catch (e: any) {
      console.error(e);
      setError(e?.message || "No se pudo guardar el campo.");
    } finally {
      setSaving(false);
    }
  };

  // --- selección de campo existente ---
  const handleSelectField = (field: FieldPolygon) => {
    setSelectedFieldId(field.id);
    setSuccess(null);
    setError(null);
    // si cambio de campo, salgo del modo edición
    setEditingFieldId(null);
    setActivePolygonRef(null);

    // centrar mapa en el nuevo campo
    if (field.polygon.length > 0 && mapRef) {
      const p = field.polygon[0];
      const center = { lat: p.lat, lng: p.lon };
      setMapCenter(center);
      mapRef.panTo(center);
    }
  };

  const selectedField = fields.find((f) => f.id === selectedFieldId) ?? null;

  // --- edición de polígono existente ---
  const handleStartFieldEdit = () => {
    if (!selectedField) return;
    setEditingFieldId(selectedField.id);
    setSuccess(null);
    setError(null);
  };

  const handleCancelFieldEdit = () => {
    setEditingFieldId(null);
    setActivePolygonRef(null);
    setSuccess(null);
    setError(null);
  };

  const handleSaveFieldEdit = async () => {
    if (!editingFieldId || !activePolygonRef) return;

    try {
      setSaving(true);
      setError(null);
      setSuccess(null);

      const path = activePolygonRef.getPath();
      const points: DraftPoint[] = [];
      for (let i = 0; i < path.getLength(); i++) {
        const p = path.getAt(i);
        points.push({ lat: p.lat(), lng: p.lng() });
      }

      if (points.length < 3) {
        throw new Error("El polígono debe tener al menos 3 puntos.");
      }

      const payload = {
        polygon: points.map((p) => ({
          lat: p.lat,
          lon: p.lng,
        })),
      };

      const res = await fetch(`${apiBaseUrl}/fields/${editingFieldId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(`Error ${res.status}: ${text}`);
      }

      const updated = (await res.json()) as FieldPolygon;

      setFields((prev) =>
        prev.map((f) => (f.id === updated.id ? updated : f))
      );
      setSuccess("Polígono actualizado correctamente.");
      setEditingFieldId(null);
      setActivePolygonRef(null);
    } catch (e: any) {
      console.error(e);
      setError(e?.message || "No se pudo actualizar el polígono.");
    } finally {
      setSaving(false);
    }
  };

  if (loadError) {
    return (
      <section className="card">
        <div className="card-header">
          <div>
            <div className="card-title">Campos / Polígonos</div>
            <div className="card-subtitle">
              No se pudo cargar Google Maps. Revisa tu API key.
            </div>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="card fields-page">
      <div className="card-header">
        <div>
          <div className="card-title">Campos / Polígonos</div>
          <div className="card-subtitle">
            Dibuja polígonos sobre el mapa para definir los campos y sectores
            por donde pasará la maquinaria.
          </div>
        </div>
      </div>

      <div className="fields-layout">
        {/* Panel izquierdo: control */}
        <div className="fields-sidebar">
          <div className="fields-section">
            <div className="fields-section-title">Nuevo Sector</div>

            <div className="form-field">
              <label className="form-label">Nombre del Sector</label>
              <input
                className="form-input"
                value={fieldName}
                onChange={(e) => setFieldName(e.target.value)}
                placeholder="Ej: Cuartel 3 - Manzanos sur"
              />
            </div>

            <div className="form-field">
              <label className="form-label">Centro de costo</label>
              <select
                className="form-select"
                value={selectedCostCenterId}
                onChange={(e) => setSelectedCostCenterId(e.target.value)}
              >
                <option value="">(Opcional) Seleccionar centro de costo</option>
                {costCenters.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-field">
              <label className="form-label">Color de referencia</label>
              <div className="fields-color-row">
                <input
                  type="color"
                  value={color}
                  onChange={(e) => setColor(e.target.value)}
                />
                <span className="fields-color-code">{color}</span>
              </div>
            </div>

            <div className="fields-draw-controls">
              <button
                type="button"
                className="form-button-secondary"
                onClick={handleStartDrawing}
              >
                {draftPoints.length === 0
                  ? "Comenzar dibujo"
                  : "Reiniciar dibujo"}
              </button>
              <button
                type="button"
                className="form-button-ghost"
                onClick={handleUndoPoint}
                disabled={draftPoints.length === 0}
              >
                Deshacer último punto
              </button>
              <button
                type="button"
                className="form-button-ghost"
                onClick={handleClearDraft}
                disabled={draftPoints.length === 0}
              >
                Limpiar
              </button>
            </div>

            <div className="fields-draw-hint">
              {isDrawing ? (
                <>
                  🟢 Modo dibujo activo. Haz click (o toca) en el mapa para ir
                  marcando los vértices del campo.
                  <br />
                  Se requiere al menos 3 puntos para formar el polígono.
                </>
              ) : (
                <>
                  Pulsa <strong>“Comenzar dibujo”</strong> y luego clickea en el
                  mapa para definir el contorno del campo.
                </>
              )}
            </div>

            <div className="fields-draft-info">
              <span>Puntos actuales: {draftPoints.length}</span>
            </div>

            <div className="fields-save-row">
              <button
                type="button"
                className="form-button-primary"
                disabled={!canSave}
                onClick={handleSaveField}
              >
                {saving ? "Guardando..." : "Guardar campo"}
              </button>
            </div>

            {error && <div className="tracker-error">⚠️ {error}</div>}
            {success && <div className="tracker-success">✅ {success}</div>}
          </div>

          <div className="fields-section">
            <div className="fields-section-title">
              Cuarteles existentes ({fields.length})
            </div>

            {fields.length === 0 ? (
              <div className="fields-empty">
                Aún no hay campos creados. Dibuja el primero en el mapa.
              </div>
            ) : (
              <ul className="fields-list">
                {fields.map((f) => (
                  <li
                    key={f.id}
                    className={
                      "fields-list-item " +
                      (selectedFieldId === f.id
                        ? "fields-list-item--active"
                        : "")
                    }
                    onClick={() => handleSelectField(f)}
                  >
                    <div className="fields-list-main">
                      <span className="fields-list-name">{f.name}</span>
                      {f.polygon.length > 0 && (
                        <span className="fields-list-badge">
                          {f.polygon.length} pts
                        </span>
                      )}
                    </div>
                    <div className="fields-list-meta">
                      <span>
                        {f.cost_center_name || "Centro de costo no asignado"}
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        {/* Panel derecho: mapa */}
        <div className="fields-map-wrapper">
          {/* Toolbar superior del mapa */}
          <div className="fields-map-toolbar">
            <button
              type="button"
              className="form-button-secondary"
              onClick={handleCenterOnMe}
              disabled={locating}
            >
              {locating ? "Localizando…" : "Centrar en mi ubicación"}
            </button>

            {selectedField && (
              <div className="fields-edit-toolbar">
                {editingFieldId === selectedField.id ? (
                  <>
                    <button
                      type="button"
                      className="form-button-primary"
                      onClick={handleSaveFieldEdit}
                      disabled={saving}
                    >
                      {saving ? "Guardando…" : "Guardar cambios"}
                    </button>
                    <button
                      type="button"
                      className="form-button-ghost"
                      onClick={handleCancelFieldEdit}
                      disabled={saving}
                    >
                      Cancelar
                    </button>
                  </>
                ) : (
                  <button
                    type="button"
                    className="form-button-secondary"
                    onClick={handleStartFieldEdit}
                  >
                    Editar polígono seleccionado
                  </button>
                )}
              </div>
            )}
          </div>

          {localError && (
            <div className="tracker-error" style={{ marginBottom: 8 }}>
              ⚠️ {localError}
            </div>
          )}

          {!isLoaded ? (
            <div className="fields-map-loading">Cargando mapa…</div>
          ) : (
            <GoogleMap
              onLoad={(map) => setMapRef(map)}
              center={mapCenter}
              zoom={18}
              mapContainerStyle={mapContainerStyle}
              options={{
                mapTypeId: "hybrid",
                streetViewControl: false,
                fullscreenControl: true,
                mapTypeControl: true,
              }}
              onClick={handleMapClick}
            >
              {/* Polígono que se está dibujando */}
              {draftPoints.length > 0 && (
                <>
                  <Polygon
                    path={draftPoints}
                    options={{
                      ...polygonOptions,
                      strokeColor: color,
                      fillColor: color,
                    }}
                  />
                  {draftPoints.map((p, idx) => (
                    <Marker
                      key={idx}
                      position={p}
                      label={(idx + 1).toString()}
                      clickable={false}
                    />
                  ))}
                </>
              )}

              {/* Campos existentes */}
              {fields.map((f) => {
                const path = f.polygon.map((p) => ({
                  lat: p.lat,
                  lng: p.lon,
                }));

                const isActive = selectedFieldId === f.id;
                const baseColor = f.color || "#1d4ed8";
                const isEditing = editingFieldId === f.id;

                return (
                  <Polygon
                    key={f.id}
                    path={path}
                    options={{
                      ...existingPolygonOptions,
                      strokeColor: baseColor,
                      fillColor: baseColor,
                      strokeWeight: isActive ? 3 : 2,
                      fillOpacity: isActive ? 0.28 : 0.14,
                      editable: isEditing,
                      draggable: isEditing,
                    }}
                    onLoad={(poly) => {
                      if (isEditing) {
                        setActivePolygonRef(poly);
                      }
                    }}
                    onUnmount={() => {
                      if (isEditing) {
                        setActivePolygonRef(null);
                      }
                    }}
                    onClick={() => handleSelectField(f)}
                  />
                );
              })}
            </GoogleMap>
          )}
        </div>
      </div>
    </section>
  );
};

export default FieldsPage;
