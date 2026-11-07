/** Read-only browser proof of the demo's internal apps. Credentials use stdin. */
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

(async () => {
  const request = JSON.parse(fs.readFileSync(0, 'utf8'));
  const [browserPath, output, scope] = process.argv.slice(2);
  if (!browserPath || !path.isAbsolute(output)) throw new Error('Use an existing browser and private absolute artifact directory');
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ executablePath: browserPath, headless: true });
  let page;
  try {
    page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    await page.goto('https://ecoplantas.stepsapp.cl/web/login?db=ECOPLANTAS&redirect=%2Fodoo', { waitUntil: 'domcontentloaded' });
    await page.locator('input[name="login"]').fill(request.login);
    await page.locator('input[name="password"]').fill(request.password);
    await page.locator('form.oe_login_form button[type="submit"]').click();
    await page.waitForURL(url => url.pathname.startsWith('/odoo') || url.pathname === '/web',
      { waitUntil: 'commit', timeout: 30000 });
    await page.locator('.o_web_client').waitFor({ timeout: 60000 });
    await page.waitForTimeout(2000);
    const openApps = async () => {
      if (!(await page.locator('.o_app').first().isVisible())) {
        await page.locator('.o_navbar_apps_menu button, .o_menu_toggle').first().click();
        await page.locator('.o_app').first().waitFor({ timeout: 15000 });
      }
    };
    await openApps();
    const applications = (await page.locator('.o_app').allTextContents()).map(value => value.trim()).filter(Boolean);
    if (!applications.some(value => /CRM/i.test(value))) throw new Error('The CRM app is missing from the internal panel');
    await page.screenshot({ path: path.join(output, 'applications.png'), fullPage: true });
    await page.locator('.o_app').filter({ hasText: 'CRM' }).first().click();
    await page.locator('.o_action_manager').waitFor({ timeout: 30000 });
    await page.waitForTimeout(2000);
    await page.screenshot({ path: path.join(output, 'crm.png'), fullPage: true });
    const proof = { internal_login: true, application_panel: true, crm_opened: true, applications,
      url: page.url(), writes: false };
    if (scope === 'greenhouse') {
      const greenhouse = [/^Fabricaci[oó]n$/i, /^Calidad$/i, /^Mantenimiento$/i, /^Proyectos?$/i];
      if (!greenhouse.every(label => applications.some(name => label.test(name)))) {
        throw new Error('The internal panel is missing greenhouse apps');
      }
      await openApps();
      await page.locator('.o_app').filter({ hasText: greenhouse[3] }).click();
      const project = page.getByText('Labores del invernadero [DEMO]', { exact: true }).first();
      await project.waitFor({ timeout: 30000 });
      await project.click();
      await page.getByText('Registrar riego y condición de bandejas [DEMO]', { exact: true }).first().waitFor({ timeout: 30000 });
      await page.getByText('Revisar sanidad y uniformidad [DEMO]', { exact: true }).first().waitFor({ timeout: 30000 });
      await page.screenshot({ path: path.join(output, 'greenhouse-tasks.png'), fullPage: true });
      proof.greenhouse_apps = true;
      proof.greenhouse_tasks_opened = true;
      proof.url = page.url();
    }
    fs.writeFileSync(path.join(output, 'ui-proof.json'), JSON.stringify(proof, null, 2));
    process.stdout.write('ECOPLANTAS_UI_OK '+JSON.stringify(proof)+'\n');
  } catch (error) {
    if (page) {
      const currentPath = new URL(page.url()).pathname;
      const alerts = (await page.locator('.alert-danger').allTextContents())
        .map(value => value.replaceAll(request.login, '[usuario]').replaceAll(request.password, '[clave]'));
      process.stderr.write(JSON.stringify({ path: currentPath, alerts })+'\n');
      await page.screenshot({ path: path.join(output, 'diagnostic.png'), fullPage: true }).catch(() => {});
    }
    throw error;
  } finally { await browser.close(); }
})().catch(error => { process.stderr.write(error.message+'\n'); process.exitCode=1; });
