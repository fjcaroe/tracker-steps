import type { ButtonHTMLAttributes, ReactNode } from 'react';
import './tokens.css';
import './ui.css';

type Tone = 'info' | 'ok' | 'warn' | 'bad';

export function Button({ variant = 'default', className = '', ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'default' | 'primary' | 'danger' | 'quiet' }) {
  const v = variant === 'default' ? '' : ` ui-btn--${variant}`;
  return <button type="button" className={`ui-btn${v} ${className}`.trim()} {...rest} />;
}
export const Card = ({ children, label }: { children: ReactNode; label?: string }) => <section className="ui-card" aria-label={label}>{children}</section>;
export const Chip = ({ tone = 'info', children }: { tone?: Tone; children: ReactNode }) => <span className={`ui-chip${tone === 'info' ? '' : ` ui-chip--${tone}`}`}>{children}</span>;
export const Banner = ({ tone = 'info', children }: { tone?: Tone; children: ReactNode }) => <p className={`ui-banner${tone === 'info' ? '' : ` ui-banner--${tone}`}`} role={tone === 'bad' ? 'alert' : 'status'}>{children}</p>;
export const Empty = ({ title, hint }: { title: string; hint?: string }) => <div className="ui-empty"><strong>{title}</strong>{hint && <p>{hint}</p>}</div>;
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
  return <header className="ui-topbar">{onBack ? <Button onClick={onBack} aria-label="Volver">‹ Volver</Button> : <strong>{title}</strong>}{onBack && <strong>{title}</strong>}{right ?? <span />}</header>;
}
export function NavBar<T extends string>({ items, current, onSelect }: { items: { id: T; label: string; badge?: number }[]; current: T; onSelect: (id: T) => void }) {
  return (
    <nav className="ui-nav" aria-label="Secciones">
      {items.map((i) => (
        <button key={i.id} aria-current={current === i.id ? 'page' : undefined} onClick={() => onSelect(i.id)}>
          {i.label}{!!i.badge && <span className="ui-badge" aria-label={`${i.badge} pendientes`}>{i.badge}</span>}
        </button>
      ))}
    </nav>
  );
}
