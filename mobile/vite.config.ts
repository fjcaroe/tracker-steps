import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

// base relativa: sirve igual bajo https://stepsapp.cl/truck/ y dentro del contenedor Android/iOS.
// En desarrollo, /steps_app se reenvía al Odoo de demostración (mismo origen: sin CORS). Uso: VITE_STEPS_API_BASE=/steps_app/v1 npm run dev
export default defineConfig({ base: './', plugins: [react()], server: { proxy: { '/steps_app': process.env.STEPS_DEV_ODOO ?? 'http://localhost:8070' } }, test: { environment: 'node', exclude: ['e2e/**', 'node_modules/**', 'dist/**'] } });
