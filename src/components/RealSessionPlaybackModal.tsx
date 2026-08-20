import { useEffect, useMemo, useState } from "react";
import { CartesianGrid, Line, LineChart, ReferenceDot, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { DemoTrackPoint } from "../demo/scenario";
import { useTrackPlayback } from "../hooks/useTrackPlayback";
import { apiJson } from "../services/http";
import SessionTrackMap from "./SessionTrackMap";

type ApiPoint = { ts: string; lat: number; lon: number; speed_mps?: number | null };

export type RealPlaybackSession = {
  id: string;
  machine: string;
  driver: string;
  field: string;
  labor: string;
  durationHours: number | null;
  distanceKm: number | null;
};

const PLAYBACK_RATES = [0.5, 1, 3, 8];

function clock(totalSeconds: number) {
  const value = Math.max(0, Math.round(totalSeconds));
  const hours = Math.floor(value / 3600);
  const minutes = Math.floor((value % 3600) / 60);
  const seconds = value % 60;
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function heading(a: ApiPoint, b: ApiPoint) {
  const lat1 = a.lat * Math.PI / 180;
  const lat2 = b.lat * Math.PI / 180;
  const deltaLon = (b.lon - a.lon) * Math.PI / 180;
  const y = Math.sin(deltaLon) * Math.cos(lat2);
  const x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(deltaLon);
  return (Math.atan2(y, x) * 180 / Math.PI + 360) % 360;
}

function toTrack(points: ApiPoint[]): DemoTrackPoint[] {
  if (!points.length) return [];
  const first = new Date(points[0].ts).getTime();
  return points.map((point, index) => ({
    atSeconds: Math.max(0, (new Date(point.ts).getTime() - first) / 1000),
    lat: Number(point.lat),
    lon: Number(point.lon),
    speedKmh: Number(point.speed_mps ?? 0) * 3.6,
    headingDeg: index < points.length - 1 ? heading(point, points[index + 1]) : index ? heading(points[index - 1], point) : 0,
  }));
}

function PlaybackContent({ session, points, onClose }: { session: RealPlaybackSession; points: ApiPoint[]; onClose: () => void }) {
  const track = useMemo(() => toTrack(points), [points]);
  const durationSeconds = Math.max(1, track.at(-1)?.atSeconds ?? 1);
  const playback = useTrackPlayback(track, durationSeconds);
  const activePoint = track.reduce((closest, point) => Math.abs(point.atSeconds - playback.elapsed) < Math.abs(closest.atSeconds - playback.elapsed) ? point : closest, track[0]);

  return <div className="ops-modal ops-modal--wide" onClick={(event) => event.stopPropagation()}>
    <header className="ops-session-modal__head"><div><span className="section-kicker">Sesión {session.id} · Datos productivos</span><h2>{session.machine} · {session.driver}</h2><p>{session.field} · {session.labor}</p></div><button type="button" className="ops-action" onClick={onClose}>Cerrar</button></header>
    <div className="ops-session-modal__map"><SessionTrackMap path={track} cursor={playback.sample} /></div>
    <div className="ops-session-modal__controls">
      <button type="button" className="ops-action ops-action--dark" onClick={playback.toggle}>{playback.playing ? "Pausar" : playback.elapsed >= durationSeconds ? "Reiniciar" : "Reproducir"}</button>
      <input type="range" className="ops-session-modal__seek" aria-label="Línea de tiempo de la sesión" min={0} max={durationSeconds} step={1} value={Math.round(playback.elapsed)} onChange={(event) => playback.seek(Number(event.target.value))}/>
      <span className="ops-session-modal__clock">{clock(playback.elapsed)} / {clock(durationSeconds)}</span>
      <label className="demo-speed">Velocidad<select value={playback.rate} onChange={(event) => playback.setRate(Number(event.target.value))}>{PLAYBACK_RATES.map((rate) => <option key={rate} value={rate}>{rate}×</option>)}</select></label>
    </div>
    <div className="ops-session-modal__chart"><ResponsiveContainer width="100%" height={150}><LineChart data={track}><CartesianGrid vertical={false} stroke="rgba(20,37,31,.09)"/><XAxis dataKey="atSeconds" tickFormatter={clock} axisLine={false} tickLine={false}/><YAxis axisLine={false} tickLine={false} width={34}/><Tooltip labelFormatter={(value) => clock(Number(value))} formatter={(value?: number) => [`${Number(value ?? 0).toFixed(1)} km/h`, "Velocidad"]}/><Line type="monotone" dataKey="speedKmh" stroke="#2f9e72" strokeWidth={2} dot={false} isAnimationActive={false}/>{activePoint && <ReferenceDot x={activePoint.atSeconds} y={activePoint.speedKmh} r={5} fill="#d94835" stroke="#fff" strokeWidth={2}/>}</LineChart></ResponsiveContainer></div>
    <dl className="ops-session-modal__readout"><div><dt>Puntos GPS</dt><dd>{track.length.toLocaleString("es-CL")}</dd></div><div><dt>Velocidad actual</dt><dd>{playback.sample.speedKmh.toFixed(1)} km/h</dd></div><div><dt>Posición</dt><dd>{playback.sample.lat.toFixed(5)}, {playback.sample.lon.toFixed(5)}</dd></div><div><dt>Duración GPS</dt><dd>{clock(durationSeconds)}</dd></div><div><dt>Distancia calculada</dt><dd>{session.distanceKm != null ? `${session.distanceKm.toFixed(1)} km` : "—"}</dd></div></dl>
  </div>;
}

export default function RealSessionPlaybackModal({ session, onClose }: { session: RealPlaybackSession; onClose: () => void }) {
  const [points, setPoints] = useState<ApiPoint[] | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    let active = true;
    apiJson<ApiPoint[]>(`/sessions/${session.id}/points?limit=20000`).then((data) => { if (active) setPoints(data); }).catch(() => { if (active) setError(true); });
    return () => { active = false; };
  }, [session.id]);

  return <div className="ops-modal-backdrop" role="dialog" aria-modal="true" aria-label={`Reproducción de la sesión ${session.id}`} onClick={onClose}>
    {points && points.length > 0 ? <PlaybackContent session={session} points={points} onClose={onClose}/> : <div className="ops-modal" onClick={(event) => event.stopPropagation()}><h2>Recorrido GPS</h2><p>{error ? "No fue posible consultar los puntos de esta sesión." : points ? "Esta sesión todavía no tiene puntos GPS registrados." : "Cargando recorrido productivo…"}</p><div className="ops-modal__actions"><button type="button" className="ops-action" onClick={onClose}>Cerrar</button></div></div>}
  </div>;
}
