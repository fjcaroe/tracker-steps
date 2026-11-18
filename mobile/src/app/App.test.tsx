// @vitest-environment jsdom
// Pantallas reales (React) sobre el servidor FALSO del contrato: no prueban Odoo, prueban lo que ve y puede hacer la persona.
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import App from './App';
import { Runtime } from './runtime';
import { SessionManager } from './session';
import { MODULES } from '../modules';
import { supportedContracts } from '../modules/registry';
import { memorySecureStore } from '../platform/secureStore';
import { memoryKv } from '../shared/storage';
import { FakeSteps } from '../testing/fakeServer';

let server: FakeSteps, kv: ReturnType<typeof memoryKv>;
const build = () => {
  const session = new SessionManager({ kv, secure: memorySecureStore(), device: async () => ({ uuid: 'dev-ui', platform: 'web', app_version: 't' }), supported: supportedContracts(MODULES), fetchImpl: server.fetch, baseUrl: 'https://fake.test/steps_app/v1', now: () => server.now });
  return new Runtime(session, kv, MODULES);
};
beforeEach(() => { server = new FakeSteps(); kv = memoryKv(); });
afterEach(cleanup);

const submitLogin = async (email: string) => {
  fireEvent.change(await screen.findByLabelText('Correo'), { target: { value: email } });
  fireEvent.change(screen.getByLabelText(/Contraseña/), { target: { value: 'clave-segura-2026' } });
  fireEvent.submit(screen.getByLabelText('Correo').closest('form')!);
};

describe('bienvenida y registro', () => {
  it('una cuenta nueva ve su incorporación y ningún dato de empresa ni módulo', async () => {
    render(<App runtime={build()} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Crear cuenta' }));
    fireEvent.change(screen.getByLabelText('Nombre'), { target: { value: 'Ana Prueba' } });
    fireEvent.change(screen.getByLabelText('Correo'), { target: { value: 'ana@example.test' } });
    fireEvent.change(screen.getByLabelText(/Contraseña/), { target: { value: 'clave-segura-2026' } });
    fireEvent.submit(screen.getByLabelText('Correo').closest('form')!);
    expect(await screen.findByText(/todavía no tienes acceso a una empresa/)).toBeTruthy();
    expect(screen.queryByText('Colaciones')).toBeNull();
    expect(screen.getByText('Solicitar acceso a una empresa')).toBeTruthy();
  });

  it('credenciales incorrectas muestran un mensaje claro y no abren sesión', async () => {
    server.addPerson('ana@example.test');
    render(<App runtime={build()} />);
    fireEvent.change(await screen.findByLabelText('Correo'), { target: { value: 'ana@example.test' } });
    fireEvent.change(screen.getByLabelText(/Contraseña/), { target: { value: 'incorrecta-123' } });
    fireEvent.submit(screen.getByLabelText('Correo').closest('form')!);
    expect(await screen.findByText('Correo o contraseña incorrectos.')).toBeTruthy();
  });

  it('el botón de Google no se ofrece mientras no esté configurado', async () => {
    render(<App runtime={build()} />);
    await screen.findByLabelText('Correo');
    expect(screen.queryByText('Continuar con Google')).toBeNull();
  });
});

describe('recuperación de acceso', () => {
  it('pide el código, define la contraseña nueva, cierra sesiones viejas y permite ingresar', async () => {
    const p = server.addPerson('ana@example.test'); server.grant(p.id, 'org-a', ['colaciones', 'persona']);
    const old = build(); await old.session.boot(); await old.session.login('ana@example.test', 'clave-segura-2026'); // «teléfono perdido»
    render(<App runtime={build()} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Recuperar' }));
    fireEvent.change(screen.getByLabelText('Correo'), { target: { value: 'ana@example.test' } });
    fireEvent.submit(screen.getByLabelText('Correo').closest('form')!);
    expect(await screen.findByText(/código recibido por correo o entregado por tu administrador/)).toBeTruthy();
    fireEvent.change(screen.getByLabelText('Código de recuperación'), { target: { value: server.recoveryCodes['ana@example.test'] } });
    fireEvent.change(screen.getByLabelText(/Contraseña nueva/), { target: { value: 'una-clave-nueva-2027' } });
    fireEvent.submit(screen.getByLabelText('Correo').closest('form')!);
    expect(await screen.findByText(/ya puedes ingresar con tu nueva contraseña/)).toBeTruthy();
    await expect(old.session.api.devices()).rejects.toMatchObject({ status: 401 });
    fireEvent.change(screen.getByLabelText('Correo'), { target: { value: 'ana@example.test' } });
    fireEvent.change(screen.getByLabelText(/Contraseña/), { target: { value: 'una-clave-nueva-2027' } });
    fireEvent.submit(screen.getByLabelText('Correo').closest('form')!);
    expect(await screen.findByText('Empresa A')).toBeTruthy();
  });

  it('un código incorrecto muestra un mensaje claro', async () => {
    server.addPerson('ana@example.test');
    render(<App runtime={build()} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Recuperar' }));
    fireEvent.change(screen.getByLabelText('Correo'), { target: { value: 'ana@example.test' } });
    fireEvent.submit(screen.getByLabelText('Correo').closest('form')!);
    await screen.findByLabelText('Código de recuperación');
    fireEvent.change(screen.getByLabelText('Código de recuperación'), { target: { value: 'inventado' } });
    fireEvent.change(screen.getByLabelText(/Contraseña nueva/), { target: { value: 'una-clave-nueva-2027' } });
    fireEvent.submit(screen.getByLabelText('Correo').closest('form')!);
    expect(await screen.findByText(/código de recuperación no es válido/)).toBeTruthy();
  });
});

describe('portada por permisos', () => {
  it('muestra solo los módulos autorizados y el contexto de empresa', async () => {
    const p = server.addPerson('ana@example.test'); server.grant(p.id, 'org-a', ['colaciones', 'persona']);
    render(<App runtime={build()} />);
    await submitLogin('ana@example.test');
    expect(await screen.findByText('Empresa A')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Abrir Colaciones' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Abrir Movilización' })).toBeNull();
    expect(screen.queryByText('Registrar entrega')).toBeNull(); // acción frecuente solo con permiso de operador
    expect(screen.getByText('Todo enviado')).toBeTruthy();
  });

  it('con varias empresas pide elegir y cada una muestra sus módulos', async () => {
    const p = server.addPerson('ana@example.test'); server.grant(p.id, 'org-a', ['colaciones', 'persona']); server.grant(p.id, 'org-b', ['mobilization', 'conductor']);
    render(<App runtime={build()} />);
    await submitLogin('ana@example.test');
    fireEvent.click(await screen.findByRole('button', { name: 'Empresa B' }));
    expect(await screen.findByRole('button', { name: 'Abrir Movilización' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Abrir Colaciones' })).toBeNull();
  });

  it('sin módulos asignados lo explica en vez de dejar una pantalla vacía', async () => {
    const p = server.addPerson('ana@example.test'); server.grant(p.id, 'org-a');
    render(<App runtime={build()} />);
    await submitLogin('ana@example.test');
    expect(await screen.findByText('Aún no tienes módulos habilitados')).toBeTruthy();
  });
});

describe('Colaciones en pantalla: guardar sin señal, enviar al volver, mostrar el estado real', () => {
  it('operador registra una entrega con la red caída y luego ve «Confirmada»', async () => {
    const p = server.addPerson('op@example.test'); server.grant(p.id, 'org-a', ['colaciones', 'operador']);
    const runtime = build();
    render(<App runtime={runtime} />);
    await submitLogin('op@example.test');
    fireEvent.click(await screen.findByRole('button', { name: 'Registrar entrega' })); // acción frecuente
    const input = await screen.findByLabelText(/Código del trabajador/);
    server.offline = true;
    fireEvent.change(input, { target: { value: 'BR0001' } });
    fireEvent.submit(input.closest('form')!);
    expect(await screen.findByText(/Guardado en el teléfono/)).toBeTruthy();
    expect(await screen.findByText('Pendiente')).toBeTruthy();
    expect(server.registrations.size).toBe(0);
    server.offline = false;
    await runtime.sync();
    expect(await screen.findByText('Confirmada')).toBeTruthy();
    expect(screen.getByText(/Trabajador Uno/)).toBeTruthy();
    expect(server.registrations.size).toBe(1);
  });

  it('si el teléfono no puede guardar, no hay falso éxito', async () => {
    const p = server.addPerson('op@example.test'); server.grant(p.id, 'org-a', ['colaciones', 'operador']);
    const runtime = build();
    render(<App runtime={runtime} />);
    await submitLogin('op@example.test');
    fireEvent.click(await screen.findByRole('button', { name: 'Registrar entrega' }));
    const input = await screen.findByLabelText(/Código del trabajador/);
    kv.failWrites((key) => key.startsWith('steps.queue.'));
    fireEvent.change(input, { target: { value: 'BR0001' } });
    fireEvent.submit(input.closest('form')!);
    expect(await screen.findByText(/No se pudo guardar en el teléfono/)).toBeTruthy();
    expect(screen.queryByText(/Guardado en el teléfono/)).toBeNull();
    expect(server.registrations.size).toBe(0);
  });

  it('un trabajador no habilitado se muestra como rechazado con su motivo, sin esconderlo', async () => {
    const p = server.addPerson('op@example.test'); server.grant(p.id, 'org-a', ['colaciones', 'operador']);
    const runtime = build();
    render(<App runtime={runtime} />);
    await submitLogin('op@example.test');
    fireEvent.click(await screen.findByRole('button', { name: 'Registrar entrega' }));
    const input = await screen.findByLabelText(/Código del trabajador/);
    fireEvent.change(input, { target: { value: 'BR0003' } });
    fireEvent.submit(input.closest('form')!);
    expect(await screen.findByText('Rechazada')).toBeTruthy();
    expect(screen.getByText('El trabajador no está habilitado para recibir colación.')).toBeTruthy();
  });

  it('la persona (no operador) solo ve sus datos y no tiene el formulario de registro', async () => {
    const p = server.addPerson('w@example.test'); server.grant(p.id, 'org-a', ['colaciones', 'persona']).employee = 1;
    render(<App runtime={build()} />);
    await submitLogin('w@example.test');
    fireEvent.click(await screen.findByRole('button', { name: 'Abrir Colaciones' }));
    expect(await screen.findByText(/Hoy aún no registras colación/)).toBeTruthy();
    expect(screen.queryByLabelText(/Código del trabajador/)).toBeNull();
  });

  it('pasado el plazo sin conexión se bloquea registrar de nuevo pero se explica', async () => {
    const p = server.addPerson('op@example.test'); server.grant(p.id, 'org-a', ['colaciones', 'operador']);
    const first = build();
    render(<App runtime={first} />);
    await submitLogin('op@example.test');
    await screen.findByText('Empresa A');
    cleanup();
    server.offline = true; server.now += 80 * 3_600_000; // sesión guardada, sin red y fuera de plazo
    const second = build();
    // reutiliza el mismo almacenamiento seguro simulando que el teléfono se reinició
    (second.session as unknown as { deps: { secure: unknown } }).deps.secure = (first.session as unknown as { deps: { secure: unknown } }).deps.secure;
    render(<App runtime={second} />);
    expect(await screen.findByText(/Pasó el plazo sin conexión/)).toBeTruthy();
  });
});

describe('Movilización en pantalla', () => {
  it('el conductor ve solo su servicio, lo inicia sin señal y marca un pasajero', async () => {
    const d = server.addPerson('c@example.test'), other = server.addPerson('otro@example.test');
    server.grant(d.id, 'org-a', ['mobilization', 'conductor']); server.grant(other.id, 'org-a', ['mobilization', 'conductor']);
    server.addTrip('org-a', d.id); server.addTrip('org-a', other.id);
    const runtime = build();
    render(<App runtime={runtime} />);
    await submitLogin('c@example.test');
    fireEvent.click(await screen.findByRole('button', { name: 'Mis servicios' }));
    const cards = await screen.findAllByText('Ruta prueba');
    expect(cards).toHaveLength(1);
    fireEvent.click(cards[0]);
    server.offline = true;
    fireEvent.click(await screen.findByRole('button', { name: 'Iniciar servicio' }));
    expect(await screen.findByText(/Inicio guardado/)).toBeTruthy();
    const input = await screen.findByLabelText(/Código del pasajero/);
    fireEvent.change(input, { target: { value: 'BR0001' } });
    fireEvent.submit(input.closest('form')!);
    expect(await screen.findByText(/Marca guardada/)).toBeTruthy();
    server.offline = false;
    await runtime.sync();
    await waitFor(() => expect(screen.getAllByText('Confirmada').length).toBeGreaterThan(0));
    expect(server.events.size).toBe(1);
    const list = screen.getByLabelText('Marcas de este teléfono');
    expect(within(list).getByText('Confirmada')).toBeTruthy();
  });
});

describe('Tracker integrado', () => {
  it('se abre como módulo con su propio acceso y se puede volver al inicio sin perder la sesión de Steps', async () => {
    const p = server.addPerson('t@example.test'); server.grant(p.id, 'org-a', ['tracker', 'operador']);
    render(<App runtime={build()} />);
    await submitLogin('t@example.test');
    fireEvent.click(await screen.findByRole('button', { name: 'Abrir Tracker' }));
    // El Tracker conserva su propio ingreso (usuario Tracker), distinto del de Steps.
    expect(await screen.findByLabelText('Usuario')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /Volver al inicio de Steps/ }));
    expect(await screen.findByRole('button', { name: 'Abrir Tracker' })).toBeTruthy();
    expect(screen.getByText('Empresa A')).toBeTruthy();
  });

  it('sin permiso de Tracker el módulo no existe en la portada', async () => {
    const p = server.addPerson('t@example.test'); server.grant(p.id, 'org-a', ['colaciones', 'persona']);
    render(<App runtime={build()} />);
    await submitLogin('t@example.test');
    await screen.findByText('Empresa A');
    expect(screen.queryByRole('button', { name: 'Abrir Tracker' })).toBeNull();
  });
});

describe('perfil y sincronización', () => {
  it('muestra datos de otra cuenta guardados en el teléfono sin enviarlos', async () => {
    const a = server.addPerson('a@example.test'), b = server.addPerson('b@example.test');
    server.grant(a.id, 'org-a', ['colaciones', 'operador']); server.grant(b.id, 'org-a', ['colaciones', 'operador']);
    await kv.set(`steps.queue.v1.${a.id}.org-a`, JSON.stringify([{ id: 'x', module: 'colaciones', kind: 'register', group: 'g', payload: {}, createdAt: '2026-10-04T00:00:00Z', state: 'pending', attempts: 0 }]));
    const runtime = build();
    render(<App runtime={runtime} />);
    await submitLogin('b@example.test');
    await screen.findByText('Empresa A');
    fireEvent.click(screen.getByRole('button', { name: /Sincronización/ }));
    expect(await screen.findByText('Datos de otra cuenta en este teléfono')).toBeTruthy();
    expect(server.registrations.size).toBe(0);
  });

  it('cerrar sesión pide confirmar y avisa de lo pendiente', async () => {
    const p = server.addPerson('op@example.test'); server.grant(p.id, 'org-a', ['colaciones', 'operador']);
    const runtime = build();
    render(<App runtime={runtime} />);
    await submitLogin('op@example.test');
    await screen.findByText('Empresa A');
    server.offline = true;
    await runtime.enqueue({ module: 'colaciones', kind: 'register', group: 'g', payload: { totemId: 1, totemName: 'x', record: { client_uuid: 'u', identifier: 'BR0001', event_datetime: new Date(server.now).toISOString(), offline: true } } });
    fireEvent.click(screen.getByRole('button', { name: 'Perfil' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Cerrar sesión' }));
    expect(await screen.findByText(/Hay 1 elementos sin enviar/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }));
    expect(screen.queryByRole('alertdialog')).toBeNull();
  });
});
