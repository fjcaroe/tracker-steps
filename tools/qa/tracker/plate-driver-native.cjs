/* Same-origin review of the assigned Odoo driver. Only reads are allowed. */
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  const proof = JSON.parse(fs.readFileSync(process.env.GPS_BROWSER_PROOF, 'utf8'));
  const origin = 'https://' + proof.host;
  const output = process.env.GPS_UI_OUTPUT;
  const expectedPlate = process.env.GPS_EXPECTED_PLATE;
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, serviceWorkers: 'block' });
    await context.addCookies([
      { name: 'session_id', value: proof.session_id, domain: proof.host, path: '/', secure: true, httpOnly: true },
      { name: 'cids', value: String(proof.company_id), domain: proof.host, path: '/', secure: true },
    ]);
    const page = await context.newPage();
    const errors = [];
    const writes = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route(origin + '/**', route => {
      const request = route.request();
      if (['GET', 'HEAD'].includes(request.method())) return route.continue();
      if (request.url().startsWith(origin + '/web/dataset/call_kw/') &&
          ['read', 'search_read'].includes(request.postDataJSON().params.method)) return route.continue();
      writes.push(new URL(request.url()).pathname);
      return route.abort();
    });
    await page.goto(origin + '/tracker#map');
    const target = await page.evaluate(async ({ company, plate }) => {
      const fleet = await (await fetch('/steps_tracker/api/fleet/snapshot')).json();
      const asset = plate ? fleet.items.find(row => row.plate === plate) : fleet.items[0];
      if (!asset) throw new Error('Vehicle unavailable in the selected fleet');
      async function search(model, domain, fields) {
        const response = await fetch('/web/dataset/call_kw/' + model + '/search_read', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ jsonrpc: '2.0', method: 'call', params: {
            model, method: 'search_read', args: [], kwargs: { domain, fields, context: { allowed_company_ids: [company] } },
          } }),
        });
        const { result, error } = await response.json();
        if (error) throw new Error('Native vehicle review denied');
        return result;
      }
      const [link] = await search('step.tracker.asset.link', [
        ['company_id', '=', company], ['asset_id', '=', asset.asset_id], ['active', '=', true],
      ], ['vehicle_id']);
      const [vehicle] = link ? await search('fleet.vehicle', [['id', '=', link.vehicle_id[0]]], ['driver_id']) : [];
      return { id: asset.asset_id, plate: asset.plate, name: asset.name, located: Boolean(asset.last_position),
        driver: vehicle ? (vehicle.driver_id ? vehicle.driver_id[1] : null) : undefined };
    }, { company: proof.company_id, plate: expectedPlate });
    if (expectedPlate) assert.ok(target.driver, 'The requested plate must have an assigned Odoo driver');
    const driverLabel = target.driver ? 'Chofer asignado: ' + target.driver :
      target.driver === null ? 'Sin chofer asignado' : 'Chofer no disponible';
    const card = page.locator('.fleet-card').filter({ hasText: target.plate || target.name });
    await card.getByText(driverLabel, { exact: true }).waitFor();
    await card.click();
    await page.locator('.inspector-header').getByText(driverLabel, { exact: true }).waitFor();
    if (target.located) {
      const marker = page.locator('.ops-map-vehicle').filter({ has: page.getByText(target.plate || target.name, { exact: true }) });
      const label = marker.getByText(driverLabel, { exact: true });
      await label.waitFor();
      if (target.driver) assert.ok((await label.boundingBox()).width >= 95, 'Driver label has room to read');
    }
    if (target.driver) {
      const search = page.getByRole('searchbox', { name: 'Buscar equipo, patente o chofer' });
      await search.fill(target.driver);
      assert.ok(await card.isVisible());
      await search.fill('');
    }
    fs.mkdirSync(output, { recursive: true });
    await page.screenshot({ path: path.join(output, 'map-desktop.png') });
    await page.getByRole('navigation', { name: 'Áreas Tracker' }).getByRole('button', { name: 'Flota', exact: true }).click();
    await page.locator('.fleet-table tr.is-selected').getByText(driverLabel, { exact: true }).waitFor();
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(origin + '/tracker?asset=' + encodeURIComponent(target.id) + '#live');
    await page.locator('.my-vehicle-title').getByText(driverLabel, { exact: true }).waitFor();
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    await page.screenshot({ path: path.join(output, 'vehicle-mobile.png') });
    assert.deepEqual(writes, []);
    assert.deepEqual(errors, []);
    console.log('TRACKER_PLATE_DRIVER_NATIVE_OK assigned=' + Boolean(target.driver) + ' marker=' + target.located);
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error(error.message);
  process.exitCode = 1;
});
