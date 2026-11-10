/* Native forms only: never save, confirm, receive or invoice live documents. */
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
(async () => {
  const proof = JSON.parse(fs.readFileSync(process.env.T190_BROWSER_PROOF, 'utf8'));
  assert(['desarrollo.stepsapp.cl','cerroelplomo.stepsapp.cl','qa-cerroelplomo.stepsapp.cl'].includes(proof.host));
  const origin = 'https://' + proof.host, out = process.env.T190_OUTPUT;
  fs.mkdirSync(out, { recursive: true });
  const errors = [], denied = [];
  const browser = await chromium.launch({ headless: true });
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, serviceWorkers: 'block' });
    await context.addCookies([{ name: 'session_id', value: proof.session_id, domain: proof.host, path: '/', secure: true, httpOnly: true },
      { name: 'cids', value: String(proof.company_id), domain: proof.host, path: '/', secure: true }]);
    const page = await context.newPage();
    page.setDefaultTimeout(60000);
    page.on('pageerror', error => errors.push(error.message));
    await page.route(origin + '/web/dataset/call_kw/**', route => {
      const params = route.request().postDataJSON()?.params;
      // The global IoT service can write channel state even on a read-only
      // purchase visit. Keep this unrelated subscription disabled in review.
      if (params?.model === 'iot.channel' && params?.method === 'get_iot_channel')
        return route.fulfill({ contentType: 'application/json', body: JSON.stringify({ jsonrpc: '2.0', id: route.request().postDataJSON().id, result: '' }) });
      if (params?.model === 'purchase.order' && params?.method === 'retrieve_dashboard') return route.continue();
      if (['get_views','get_view','web_search_read','search_read','read','web_read','search_count','search','name_search','onchange','default_get','has_group','check_access_rights','get_metadata','get_panel_data','get_import_templates'].includes(params?.method)) return route.continue();
      denied.push(params?.model + '.' + params?.method); return route.abort();
    });
    const seen = [];
    for (const name of ['rfq', 'purchase']) {
      console.log('T190_REVIEWING ' + name);
      await page.goto(origin + '/odoo/action-' + proof.actions[name]);
      await page.locator('.o_list_view').waitFor();
      const create = page.locator('.o_list_button_add');
      await create.waitFor(); await create.click();
      await page.locator('.o_form_view').waitFor();
      await page.locator('button[name="button_confirm"]').first().waitFor();
      assert.equal(await page.locator('button[name="action_fruit_approve"]').count(), 0);
      assert(await page.locator('.o_field_widget[name="order_line"]').isVisible());
      await page.screenshot({ path: path.join(out, name + '-native-form.png'), fullPage: true });
      seen.push(name);
    }
    for (const name of ['fruit', 'advance']) {
      console.log('T190_REVIEWING ' + name);
      await page.goto(origin + '/odoo/action-' + proof.actions[name]);
      await page.locator('.o_list_view').waitFor();
      await page.locator('.o_list_button_add').waitFor({ state: 'detached' });
      assert.equal(await page.locator('.o_list_button_add').count(), 0);
      await page.screenshot({ path: path.join(out, name + '-list.png'), fullPage: true });
      seen.push(name);
    }
    console.log('T190_REVIEWING purchase_proforma_menu');
    await page.goto(origin + '/odoo/action-' + proof.actions.rfq);
    await page.locator('.o_list_view').waitFor();
    await page.locator('[data-menu-xmlid="step_packing_fruit_proforma.menu_purchase_fruit"]').click();
    await page.locator('[data-menu-xmlid="step_packing_fruit_proforma.menu_purchase_prepare_fruit"]').waitFor();
    await page.locator('[data-menu-xmlid="step_packing_fruit_proforma.menu_purchase_fruit_list"]').click();
    await page.locator('.o_list_view').waitFor();
    await page.locator('.o_list_button_add').waitFor({ state: 'detached' });
    assert.equal(await page.locator('.o_list_button_add').count(), 0);
    assert.deepEqual(denied, []);
    assert.deepEqual(errors, []);
    fs.writeFileSync(path.join(out, 'result.json'), JSON.stringify({ forms: seen, native_create_and_confirm: true,
      separate_proformas: true, purchase_proforma_menu: true, saved_live_documents: 0, browser_errors: errors.length }));
    console.log('T190_BROWSER_OK native_purchase=True proformas=True business_writes=0');
  } catch (error) {
    console.error(JSON.stringify({ denied, browser_errors: errors }));
    throw error;
  } finally { await browser.close(); }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
