// Run against scripts/mock-api.mjs and Vite --mode tracker using bundled Playwright.
import fs from 'node:fs/promises';
import { chromium } from 'playwright';
const [base = 'http://127.0.0.1:4173', output] = process.argv.slice(2);
if (!output) throw new Error('Pass a private screenshot path');
const browser = await chromium.launch({headless: true, ...(process.env.PLAYWRIGHT_CHANNEL ? {channel: process.env.PLAYWRIGHT_CHANNEL} : {})});
try {
  const page = await browser.newPage({viewport: {width: 375, height: 812}, timezoneId: 'America/Santiago'});
  await page.route('**/*', (route) => ['127.0.0.1', 'localhost'].includes(new URL(route.request().url()).hostname) ? route.continue() : route.abort());
  await page.addInitScript(() => {
    localStorage.setItem('steps_movil_token', 'mock');
    localStorage.setItem('steps_movil_settings', JSON.stringify({seenHelp: true}));
  });
  await page.goto(base);
  await page.getByRole('button', {name: 'Hoy', exact: true}).click();
  await page.getByRole('heading', {name: 'Mi servicio', exact: true}).waitFor();
  for (const id of [1, 2, 3]) await page.getByText(`Pasajero ficticio ${id}`, {exact: true}).waitFor();
  const card = page.locator('.passenger-service');
  await card.scrollIntoViewIfNeeded();
  if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)) throw new Error('Horizontal overflow at 375 px');
  if (await card.locator('button,input,select').count()) throw new Error('Manifest must remain read-only');
  await card.screenshot({path: output});
  await page.getByText('Asiento 3', {exact: true}).evaluate((element) => element.scrollIntoView({block: 'center'}));
  const seat = await page.getByText('Asiento 3', {exact: true}).boundingBox();
  const bar = await page.getByRole('navigation', {name: 'Secciones'}).boundingBox();
  if (!seat || !bar || seat.y < 0 || seat.y + seat.height > bar.y) throw new Error('Last passenger is obscured by navigation');
  await page.screenshot({path: output.replace(/\.png$/, '.bottom.png')});
  const storage = await page.evaluate(() => JSON.stringify({...localStorage}));
  if (storage.includes('TEST-1') || storage.includes('Pasajero ficticio')) throw new Error('Passenger manifest persisted locally');
  console.log('PASSENGER_UI_375_OK three_passengers=True readonly=True no_local_manifest=True');
} finally { await browser.close(); }
