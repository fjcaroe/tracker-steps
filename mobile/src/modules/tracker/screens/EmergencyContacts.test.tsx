// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import EmergencyContacts from './EmergencyContacts';
import { SosSheet } from './Sheets';
import { outboxStore, syncAll } from '../lib/sync';
import { api } from '../lib/api';
import type { Active } from '../lib/queue';

const active: Active = {
  sessionId: 'session', machineId: 4, machineName: 'Auto de prueba', workOrderId: 7,
  startedAt: 0, hourmeterStart: null, tankStart: null, tankCapacity: null, distanceM: 0,
};

vi.mock('../lib/api', async (original) => ({
  ...await original<typeof import('../lib/api')>(),
  api: vi.fn(),
  mobile: { heartbeat: vi.fn(async () => {}) },
}));

beforeEach(() => { localStorage.clear(); vi.mocked(api).mockReset(); });
afterEach(cleanup);

it('guarda por cuenta y ofrece llamadas o SMS mientras el SOS queda pendiente sin conexión', () => {
  const { unmount } = render(<EmergencyContacts userId={1} />);
  const contact = within(screen.getByRole('group', { name: 'Contacto 1' }));
  fireEvent.change(contact.getByLabelText('Nombre'), { target: { value: 'Oficina de prueba' } });
  fireEvent.change(contact.getByLabelText('Teléfono'), { target: { value: '+56 900 000 000' } });
  fireEvent.click(screen.getByRole('button', { name: 'Guardar contactos' }));
  expect(screen.getByRole('status').textContent).toBe('Contactos guardados.');
  unmount();

  const onSync = vi.fn(async () => {});
  const props = { userId: 1, active, fix: { lat: -35, lon: -71, ts: 0, speed_mps: null, accuracy_m: 8 },
    onClose: vi.fn(), online: false, onSync };
  const view = render(<SosSheet {...props} />);
  expect(screen.getByRole('link', { name: 'Llamar a Oficina de prueba' }).getAttribute('href')).toBe('tel:+56900000000');
  expect(decodeURIComponent(screen.getByRole('link', { name: 'Abrir SMS para Oficina de prueba' }).getAttribute('href')!))
    .toContain('https://maps.google.com/?q=-35,-71');
  fireEvent.click(screen.getByRole('button', { name: 'Enviar SOS' }));
  expect(screen.getByRole('status').textContent).toContain('SOS pendiente');
  expect(onSync).not.toHaveBeenCalled();
  expect(outboxStore.ops()).toMatchObject([{ body: { category: 'sos', lat: -35, lon: -71 } }]);
  view.unmount();
  render(<SosSheet {...props} userId={2} />);
  expect(screen.queryByRole('link', { name: 'Llamar a Oficina de prueba' })).toBeNull();
});

it('espera el resultado de la sincronización para mostrar que la oficina recibió el SOS', async () => {
  vi.mocked(api).mockResolvedValue({ status: 'open' });
  const onSync = async () => { await syncAll(); };
  render(<SosSheet userId={1} active={active} fix={null} online onSync={onSync} onClose={vi.fn()} />);
  fireEvent.click(screen.getByRole('button', { name: 'Enviar SOS' }));
  expect((await screen.findByRole('status')).textContent).toBe('La oficina recibió el SOS.');
});
