import { defineConfig } from 'vitest/config';

// Recorrido extremo a extremo contra un Odoo REAL con datos sintéticos (ver tools/steps_app_demo/run_demo.sh).
export default defineConfig({ test: { environment: 'node', include: ['e2e/**/*.e2e.test.ts'], testTimeout: 60_000, hookTimeout: 60_000, fileParallelism: false } });
