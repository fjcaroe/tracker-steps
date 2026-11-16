// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { mobile } from '../lib/api';
import TrackerHealth from './TrackerHealth';

vi.mock('../lib/api', () => ({ mobile: { devices: vi.fn() } }));
afterEach(cleanup);

it('muestra la versión de cada conductor, permite buscar y conserva la última consulta si falla el refresco', async () => {
  vi.mocked(mobile.devices).mockResolvedValueOnce([
    { user_id: 1, user_name: 'Ana Pérez', version: '1.9.0', platform: 'android', pending: 0,
      last_sync_at: '2026-11-16T12:30:00Z', last_seen_at: '2026-11-16T13:30:00Z' },
    { user_id: 2, user_name: 'Bruno Díaz', version: null, platform: 'web', pending: null,
      last_sync_at: null, last_seen_at: '2026-11-16T12:00:00Z' },
  ]).mockRejectedValueOnce(new Error('Sin red'));

  render(<TrackerHealth />);
  await screen.findByRole('heading', { name: 'Ana Pérez' });
  fireEvent.change(screen.getByRole('searchbox', { name: 'Buscar conductor' }), { target: { value: 'ana' } });
  expect(screen.queryByRole('heading', { name: 'Bruno Díaz' })).toBeNull();
  const card = within(screen.getByRole('heading', { name: 'Ana Pérez' }).closest('article')!);
  expect(card.getByText('1.9.0')).toBeDefined();
  expect(card.getByText('0')).toBeDefined();
  expect([...screen.getByRole('region').querySelectorAll('time')].map(node => node.dateTime))
    .toEqual(['2026-11-16T12:30:00Z', '2026-11-16T13:30:00Z']);
  fireEvent.click(screen.getByRole('button', { name: 'Actualizar estado' }));
  expect((await screen.findByRole('alert')).textContent).toContain('Se muestra la última consulta');
  expect(screen.getByRole('heading', { name: 'Ana Pérez' })).toBeDefined();
});
