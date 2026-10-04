import type { ButtonHTMLAttributes, ReactNode } from 'react';
import './tokens.css';
import './ui.css';

const ICONS: Record<string, string> = {
  inicio: 'M3 10 12 3l9 7M5 9v12h5v-7h4v7h5V9',
  sync: 'M20 7a9 9 0 0 0-15-2L3 8m0-5v5h5M4 17a9 9 0 0 0 15 2l2-3m0 5v-5h-5',
  perfil: 'M20 21a8 8 0 0 0-16 0M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8',
  colaciones: 'M4 3v6a3 3 0 0 0 6 0V3M7 3v18M18 3c-3 3-3 8 0 9h2V3h-2Zm2 9v9',
  mobilization: 'M5 17H3V6a3 3 0 0 1 3-3h12a3 3 0 0 1 3 3v11h-2M9 17h6M3 10h18M7 3v7M17 3v7M9 17a2 2 0 1 1-4 0 2 2 0 0 1 4 0Zm10 0a2 2 0 1 1-4 0 2 2 0 0 1 4 0Z',
  tracker: 'M12 21s7-6 7-11a7 7 0 1 0-14 0c0 5 7 11 7 11Zm3-11a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z',
  company: 'M4 21V3h12v18M16 9h4v12M2 21h20M8 7h4M8 11h4M8 15h4',
  arrow: 'm9 5 7 7-7 7',
  ok: 'm5 12 4 4L19 6',
  warn: 'M12 8v5m0 3v.01M12 3 2 21h20L12 3Z',
  bad: 'M12 8v5m0 3v.01M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z',
  info: 'M12 8v.01m0 3v5M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z',
  empty: 'M3 8h18v13H3V8Zm0 0 4-5h10l4 5M8 12h8',
};
export function Icon({ name }: { name: string }) {
  return <svg className="ui-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={ICONS[name] ?? ICONS.empty} /></svg>;
}

type Tone = 'info' | 'ok' | 'warn' | 'bad';

export function Button({ variant = 'default', className = '', ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'default' | 'primary' | 'danger' | 'quiet' }) {
  const v = variant === 'default' ? '' : ` ui-btn--${variant}`;
  return <button type="button" className={`ui-btn${v} ${className}`.trim()} {...rest} />;
}
export const Card = ({ children, label, className = '' }: { children: ReactNode; label?: string; className?: string }) => <section className={`ui-card ${className}`.trim()} aria-label={label}>{children}</section>;
export const Chip = ({ tone = 'info', children }: { tone?: Tone; children: ReactNode }) => <span className={`ui-chip${tone === 'info' ? '' : ` ui-chip--${tone}`}`}><Icon name={tone} />{children}</span>;
export const Banner = ({ tone = 'info', children }: { tone?: Tone; children: ReactNode }) => <p className={`ui-banner${tone === 'info' ? '' : ` ui-banner--${tone}`}`} role={tone === 'bad' ? 'alert' : 'status'}>{children}</p>;
export const Empty = ({ title, hint }: { title: string; hint?: string }) => <div className="ui-empty"><Icon name="empty" /><strong>{title}</strong>{hint && <p>{hint}</p>}</div>;
export const Spinner = ({ label = 'Cargando…' }: { label?: string }) => <div className="boot" role="status"><span className="spinner" />{label}</div>;
export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return <label className="ui-field">{label}{children}{hint && <small>{hint}</small>}</label>;
}
export function Sheet({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  return (
    <div className="ui-sheet" role="dialog" aria-modal="true" aria-label={title}>
      <div className="ui-sheet__panel"><h2>{title}</h2>{children}<Button variant="quiet" onClick={onClose}>Cerrar</Button></div>
    </div>
  );
}
/** Confirmación explícita para acciones que no se pueden deshacer. */
export function Confirm({ title, body, confirmLabel, onConfirm, onCancel, danger }: { title: string; body: ReactNode; confirmLabel: string; onConfirm: () => void; onCancel: () => void; danger?: boolean }) {
  return (
    <div className="ui-sheet" role="alertdialog" aria-modal="true" aria-label={title}>
      <div className="ui-sheet__panel"><h2>{title}</h2><div>{body}</div>
        <Button variant={danger ? 'danger' : 'primary'} onClick={onConfirm}>{confirmLabel}</Button>
        <Button onClick={onCancel}>Cancelar</Button>
      </div>
    </div>
  );
}
export function TopBar({ title, onBack, right }: { title: string; onBack?: () => void; right?: ReactNode }) {
  return <header className="ui-topbar">{onBack ? <Button onClick={onBack} aria-label="Volver">‹ Volver</Button> : <strong className="brand"><b aria-hidden="true">S</b>{title}</strong>}{onBack && <strong>{title}</strong>}{right ?? <span />}</header>;
}
export function NavBar<T extends string>({ items, current, onSelect }: { items: { id: T; label: string; badge?: number }[]; current: T; onSelect: (id: T) => void }) {
  return (
    <nav className="ui-nav" aria-label="Secciones">
      {items.map((i) => (
        <button key={i.id} aria-current={current === i.id ? 'page' : undefined} onClick={() => onSelect(i.id)}>
          <Icon name={i.id} /><span>{i.label}</span>{!!i.badge && <span className="ui-badge" aria-label={`${i.badge} pendientes`}>{i.badge}</span>}
        </button>
      ))}
    </nav>
  );
}
