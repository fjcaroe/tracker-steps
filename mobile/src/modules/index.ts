import type { ModuleManifest } from './registry';
import { colacionesHandlers } from './colaciones/service';
import { mobilizationHandlers } from './mobilization/service';

// Módulos incluidos en esta versión de la app. El id debe coincidir con `step.app.module.code` en Odoo.
export const MODULES: ModuleManifest[] = [
  {
    id: 'colaciones', contractVersion: 1, name: 'Colaciones', tagline: 'Tu colación y registro de entregas', icon: 'restaurant',
    capabilities: [], requiredPermissions: ['colaciones.read_own', 'colaciones.register'],
    quickActions: [{ id: 'registrar', label: 'Registrar entrega', permission: 'colaciones.register' }],
    load: () => import('./colaciones/Colaciones'), handlers: colacionesHandlers,
  },
  {
    id: 'mobilization', contractVersion: 1, name: 'Movilización', tagline: 'Servicios de transporte y pasajeros', icon: 'directions_bus',
    capabilities: ['gps'], requiredPermissions: ['mobilization.drive', 'mobilization.supervise'],
    quickActions: [{ id: 'servicios', label: 'Mis servicios', permission: 'mobilization.drive' }],
    load: () => import('./mobilization/Mobilization'), handlers: mobilizationHandlers,
  },
  {
    id: 'tracker', contractVersion: 1, name: 'Tracker', tagline: 'Jornadas de maquinaria, tareas y ruta', icon: 'agriculture',
    capabilities: ['gps'], requiredPermissions: ['tracker.session'],
    load: () => import('./tracker'),
  },
];
