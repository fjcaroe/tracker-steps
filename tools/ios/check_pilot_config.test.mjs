import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const script = fileURLToPath(new URL('./check_pilot_config.mjs', import.meta.url));
for (const [url, allowed] of [
  ['', false], ['http://localhost:8075/steps_app/v1', false],
  ['https://localhost/steps_app/v1', false], ['https://test.invalid/other', false],
  ['https://user:example@test.invalid/steps_app/v1', false],
  ['https://test.invalid/steps_app/v1?token=example', false],
  ['https://test.invalid/steps_app/v1', true],
]) {
  test(`pilot endpoint ${allowed ? 'accepts' : 'rejects'} ${url || 'missing configuration'}`, () => {
    const result = spawnSync(process.execPath, [script], { env: { ...process.env, VITE_STEPS_API_BASE: url }, encoding: 'utf8' });
    assert.equal(result.status === 0, allowed);
    assert.ok(!(result.stdout + result.stderr).includes('user:example'));
  });
}
