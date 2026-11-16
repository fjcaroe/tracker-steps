const assert = require('node:assert/strict');
const { createServer } = require('node:http');
const { readFile } = require('node:fs/promises');
const { extname, resolve, sep } = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

const dist = resolve(process.argv[2] || 'mobile/dist');
const version = process.argv[3] || '1.9.1';
const mime = { '.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript' };
const server = createServer(async (req, res) => {
  const path = new URL(req.url, 'http://localhost').pathname;
  const file = resolve(dist, '.' + (path === '/' ? '/index.html' : path));
  if (!file.startsWith(dist + sep)) return res.writeHead(404).end();
  try {
    const bytes = await readFile(file);
    res.writeHead(200, { 'Content-Type': mime[extname(file)] || 'application/octet-stream' }).end(bytes);
  } catch {
    res.writeHead(404).end();
  }
});

const account = { id: 10, full_name: 'Operador de prueba', username: 'prueba', is_admin: true };
const session = {
  sessionId: 'journey-qa', machineId: 1, machineName: 'Vehículo de prueba', workOrderId: 1,
  hourmeterStart: null, tankStart: null, tankCapacity: null, distanceM: 0, distanceBased: true,
};

async function openTracker(browser, base, legacy) {
  const context = await browser.newContext({ viewport: { width: legacy ? 375 : 320, height: 760 }, colorScheme: 'dark' });
  const page = await context.newPage();
  await page.addInitScript(({ legacy, account, session }) => {
    if (legacy) delete HTMLDialogElement.prototype.showModal;
    localStorage.setItem('steps_movil_token', 'fixture-only');
    localStorage.setItem('steps_movil_token_refreshed', String(Date.now()));
    localStorage.setItem('steps_movil_owner', JSON.stringify({ userId: account.id, name: account.full_name }));
    localStorage.setItem('steps_movil_active', JSON.stringify({ ...session, startedAt: Date.now() }));
  }, { legacy, account, session });
  await context.route('**/*', async (route) => {
    const url = new URL(route.request().url());
    if (url.origin !== base) return route.abort();
    if (!url.pathname.startsWith('/tracker-dev-api/')) return route.continue();
    assert.equal(route.request().headers()['x-steps-app-version'], version);
    const path = url.pathname.slice('/tracker-dev-api'.length);
    const fixtures = {
      '/auth/me': account,
      '/sessions/journey-qa': { id: 'journey-qa', status: 'open', ended_at: null },
      '/mobile/heartbeat': { ok: true },
    };
    return route.fulfill({ json: fixtures[path] ?? [] });
  });
  await page.goto(base);
  return page;
}

async function assertDialogFocus(page, opener, title, closeLabel) {
  await opener.focus();
  await page.keyboard.press('Enter');
  const dialog = page.getByRole('dialog', { name: title, exact: true });
  await dialog.waitFor();
  const close = dialog.getByRole('button', { name: closeLabel });
  await page.waitForFunction(() => document.activeElement?.closest('[role="dialog"], dialog'));
  assert.equal(await close.evaluate((button) => button === document.activeElement), true);
  await page.keyboard.press('Tab');
  const focusStayed = await dialog.evaluate(element => document.activeElement === document.body || element.contains(document.activeElement));
  assert.ok(focusStayed);
  await close.focus();
  await page.keyboard.press('Escape');
  await dialog.waitFor({ state: 'hidden' });
  await page.waitForFunction(() => document.activeElement?.tagName === 'BUTTON');
  assert.equal(await opener.evaluate((button) => button === document.activeElement), true);
}

async function colorContrast(page) {
  return page.getByRole('navigation', { name: 'Secciones' }).evaluate((nav) => {
    const luminance = (css) => {
      const [r, g, b] = css.match(/\d+/g).slice(0, 3).map(Number)
        .map(channel => channel / 255)
        .map(channel => channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4);
      return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    };
    const text = luminance(getComputedStyle(nav.querySelector('[aria-current="page"]')).color);
    const background = luminance(getComputedStyle(nav).backgroundColor);
    return (Math.max(text, background) + 0.05) / (Math.min(text, background) + 0.05);
  });
}

async function assertNoHorizontalScroll(page) {
  const overflowing = await page.evaluate(() => {
    if (document.documentElement.scrollWidth <= innerWidth + 1) return [];
    return [innerWidth, document.documentElement.scrollWidth, ...Array.from(document.querySelectorAll('main *, nav *'))
      .filter(element => element.getBoundingClientRect().right > innerWidth)
      .map(element => element.tagName + '.' + element.getAttribute('class') + ' ' + element.textContent.slice(0, 50))
      .slice(0, 8)];
  });
  assert.deepEqual(overflowing, []);
}

async function run(browser, base, legacy) {
  const page = await openTracker(browser, base, legacy);
  try {
    const initialHelp = page.getByRole('dialog', { name: 'Cómo usar Steps Móvil' });
    await initialHelp.waitFor();
    if (!legacy) assert.equal(await initialHelp.evaluate(element => element.matches(':modal')), true);
    await page.keyboard.press('Escape');
    await initialHelp.waitFor({ state: 'hidden' });
    await page.getByRole('button', { name: 'Continuar jornada y registrar ruta' }).click();
    await assertDialogFocus(page, page.getByRole('button', { name: 'Reportar incidente' }), 'Reportar incidente', 'Cerrar');
    await assertDialogFocus(page, page.getByRole('button', { name: 'Finalizar jornada' }), 'Finalizar jornada', 'Seguir en jornada');

    await page.getByRole('button', { name: 'Perfil', exact: true }).click();
    await page.getByText('Versión ' + version, { exact: false }).waitFor();
    await page.getByLabel('Modo noche').selectOption('off');
    assert.ok(await colorContrast(page) >= 4.5, 'legible active section in forced light mode');
    await page.emulateMedia({ colorScheme: 'light' });
    await page.getByLabel('Modo noche').selectOption('on');
    assert.ok(await colorContrast(page) >= 4.5, 'legible active section in forced dark mode');
    await page.getByLabel('Tamaño de letra').selectOption('1.3');
    await page.getByLabel('Modo guantes (botones más grandes)').check();
    const navigation = page.getByRole('navigation', { name: 'Secciones' });
    assert.ok((await navigation.boundingBox()).height >= 72);
    await assertNoHorizontalScroll(page);
    await assertDialogFocus(page, page.getByRole('button', { name: 'Ayuda de primer uso' }), 'Cómo usar Steps Móvil', 'Cerrar');
    await page.getByRole('button', { name: 'Jornada', exact: true }).click();
    await assertNoHorizontalScroll(page);
  } finally {
    await page.context().close();
  }
}

(async () => {
  await new Promise((done) => server.listen(0, '127.0.0.1', done));
  const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || 'msedge' });
  try {
    const base = 'http://127.0.0.1:' + server.address().port;
    await run(browser, base, false);
    await run(browser, base, true);
    console.log('TRACKER_I14_BROWSER_OK focus escape dialogs contrast font gloves legacy');
  } finally {
    await browser.close();
  }
})().catch((error) => { console.error(error); process.exitCode = 1; }).finally(() => server.close());
