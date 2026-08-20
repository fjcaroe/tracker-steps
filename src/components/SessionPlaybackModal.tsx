import { useMemo } from "react";
import { CartesianGrid, Line, LineChart, ReferenceDot, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import SessionTrackMap from "./SessionTrackMap";
import { useTrackPlayback } from "../hooks/useTrackPlayback";
import { buildSessionTrack, DEMO_FIELDS, type DemoSession } from "../demo/scenario";

const PLAYBACK_RATES = [0.5, 1, 3, 8];

function formatClock(totalSeconds: number): string {
  const s = Math.max(0, Math.round(totalSeconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
}

export default function SessionPlaybackModal({ session, onClose }: { session: DemoSession; onClose: () => void }) {
  const field = DEMO_FIELDS.find((item) => item.id === session.fieldId);
  const track = useMemo(() => buildSessionTrack(session), [session]);
  const durationSeconds = Math.round(session.durationHours * 3600);
  const playback = useTrackPlayback(track, durationSeconds);

  const chartData = useMemo(
    () => track.map((point) => ({ atSeconds: point.atSeconds, speedKmh: Number(point.speedKmh.toFixed(1)) })),
    [track],
  );
  const activePoint = chartData.reduce(
    (closest, point) => (Math.abs(point.atSeconds - playback.elapsed) < Math.abs(closest.atSeconds - playback.elapsed) ? point : closest),
    chartData[0],
  );

  return (
    <div className="ops-modal-backdrop" role="dialog" aria-modal="true" aria-label={`Reproducción de la sesión ${session.id}`} onClick={onClose}>
      <div className="ops-modal ops-modal--wide" onClick={(event) => event.stopPropagation()}>
        <header className="ops-session-modal__head">
          <div>
            <span className="section-kicker">Sesión {session.id} · Dataset demostrativo</span>
            <h2>{session.machine} · {session.driver}</h2>
            <p>{session.field} · {session.labor}</p>
          </div>
          <button type="button" className="ops-action" onClick={onClose}>Cerrar</button>
        </header>

        <div className="ops-session-modal__map">
          <SessionTrackMap field={field} path={track} cursor={playback.sample} />
        </div>

        <div className="ops-session-modal__controls">
          <button type="button" className="ops-action ops-action--dark" onClick={playback.toggle}>
            {playback.playing ? "Pausar" : playback.elapsed >= durationSeconds ? "Reiniciar" : "Reproducir"}
          </button>
          <input
            type="range"
            className="ops-session-modal__seek"
            aria-label="Línea de tiempo de la sesión"
            min={0}
            max={durationSeconds}
            step={1}
            value={Math.round(playback.elapsed)}
            onChange={(event) => playback.seek(Number(event.target.value))}
          />
          <span className="ops-session-modal__clock">{formatClock(playback.elapsed)} / {formatClock(durationSeconds)}</span>
          <label className="demo-speed">Velocidad
            <select value={playback.rate} onChange={(event) => playback.setRate(Number(event.target.value))}>
              {PLAYBACK_RATES.map((rate) => <option key={rate} value={rate}>{rate}×</option>)}
            </select>
          </label>
        </div>

        <div className="ops-session-modal__chart">
          <ResponsiveContainer width="100%" height={150}>
            <LineChart data={chartData}>
              <CartesianGrid vertical={false} stroke="rgba(20,37,31,.09)" />
              <XAxis dataKey="atSeconds" tickFormatter={formatClock} axisLine={false} tickLine={false} minTickGap={48} />
              <YAxis axisLine={false} tickLine={false} width={34} />
              <Tooltip labelFormatter={(value) => formatClock(Number(value))} formatter={(value?: number) => [`${value ?? 0} km/h`, "Velocidad"]} />
              <Line type="monotone" dataKey="speedKmh" stroke="#2f9e72" strokeWidth={2} dot={false} isAnimationActive={false} />
              {activePoint && <ReferenceDot x={activePoint.atSeconds} y={activePoint.speedKmh} r={5} fill="#d94835" stroke="#fff" strokeWidth={2} />}
            </LineChart>
          </ResponsiveContainer>
        </div>

        <dl className="ops-session-modal__readout" aria-live="polite">
          <div><dt>Tiempo</dt><dd>{formatClock(playback.elapsed)}</dd></div>
          <div><dt>Velocidad actual</dt><dd>{playback.sample.speedKmh.toFixed(1)} km/h</dd></div>
          <div><dt>Posición</dt><dd>{playback.sample.lat.toFixed(5)}, {playback.sample.lon.toFixed(5)}</dd></div>
          <div><dt>Duración total</dt><dd>{session.durationHours.toFixed(1)} h</dd></div>
          <div><dt>Distancia</dt><dd>{session.distanceKm.toFixed(1)} km</dd></div>
          <div><dt>Superficie</dt><dd>{session.coveredHa.toFixed(1)} ha</dd></div>
        </dl>
      </div>
    </div>
  );
}
