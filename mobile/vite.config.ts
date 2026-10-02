import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

// base relativa: sirve igual bajo https://stepsapp.cl/truck/ y dentro del contenedor Android/iOS.
export default defineConfig({ base: './', plugins: [react()], test: { environment: 'node' } });
