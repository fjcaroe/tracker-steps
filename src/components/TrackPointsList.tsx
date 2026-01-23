// src/components/TrackPointsList.tsx
import type { TrackPoint } from "../types";

type Props = {
  points: TrackPoint[];
  formatTime: (ts: number) => string;
  formatNumber: (n: number | null | undefined, decimals?: number) => string;
};

const TrackPointsList = ({ points, formatTime, formatNumber }: Props) => {
  return (
    <div className="points-list">
      <ul className="points-list__items">
        {points
          .slice()
          .reverse()
          .map((p) => (
            <li key={p.id} className="points-list__item">
              <strong>{formatTime(p.timestamp)}</strong>{" "}
              · lat {formatNumber(p.lat)}, lon {formatNumber(p.lon)}{" "}
              {p.speed_mps != null && !Number.isNaN(p.speed_mps) && (
                <> · {(p.speed_mps * 3.6).toFixed(1)} km/h</>
              )}
            </li>
          ))}
        {points.length === 0 && (
          <li className="points-list__item points-list__item--empty">
            Sin puntos aún. Inicia el rastreo para ver datos.
          </li>
        )}
      </ul>
    </div>
  );
};

export default TrackPointsList;
