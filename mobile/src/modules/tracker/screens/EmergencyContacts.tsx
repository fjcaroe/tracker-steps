import { useState, type FormEvent } from 'react';
import { getEmergencyContacts, MAX_EMERGENCY_CONTACTS, saveEmergencyContacts, type EmergencyContact } from '../lib/emergencyContacts';

export default function EmergencyContacts({ userId }: { userId: number }) {
  const [draft, setDraft] = useState(() => {
    const saved = getEmergencyContacts(userId);
    return Array.from({ length: MAX_EMERGENCY_CONTACTS }, (_, index) => saved[index] ?? { name: '', phone: '' });
  });
  const [status, setStatus] = useState<{ text: string; error?: boolean } | null>(null);

  function change(index: number, patch: Partial<EmergencyContact>) {
    setDraft(previous => previous.map((contact, i) => i === index ? { ...contact, ...patch } : contact));
    setStatus(null);
  }

  function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      saveEmergencyContacts(userId, draft);
      setStatus({ text: 'Contactos guardados.' });
    } catch (error) {
      setStatus({ text: error instanceof Error && error.name === 'Error'
        ? error.message : 'No se pudieron guardar los contactos en este dispositivo.', error: true });
    }
  }

  return <form className="card stack" onSubmit={save}>
    <h3>Contactos de emergencia</h3>
    <p className="muted">Aparecen en SOS para llamar o abrir un SMS. Se guardan para tu cuenta en este dispositivo.</p>
    {draft.map((contact, index) => <fieldset key={index} className="stack">
      <legend>Contacto {index + 1}</legend>
      <label>Nombre<input value={contact.name} onChange={e => change(index, { name: e.target.value })} maxLength={60} /></label>
      <label>Teléfono<input type="tel" autoComplete="off" value={contact.phone} onChange={e => change(index, { phone: e.target.value })} maxLength={32} /></label>
    </fieldset>)}
    <button className="primary">Guardar contactos</button>
    {status && <p className={status.error ? 'error' : 'muted'} role={status.error ? 'alert' : 'status'}>{status.text}</p>}
  </form>;
}
