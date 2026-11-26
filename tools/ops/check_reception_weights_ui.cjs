/* Read-only live acceptance; private native session is removed by the caller. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { chromium } = require('playwright');

(async () => {
    const proof = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
    assert.equal(proof.host, 'cerroelplomo.stepsapp.cl');
    const output = process.argv[3];
    fs.mkdirSync(output, { recursive: true });
    const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH });
    let page;
    try {
        const context = await browser.newContext({ locale: 'es-CL', viewport: { width: 1440, height: 1000 } });
        await context.addCookies([
            { name:'session_id',value:proof.session_id,domain:proof.host,path:'/',secure:true,httpOnly:true },
            { name:'cids',value:String(proof.company_id),domain:proof.host,path:'/',secure:true },
        ]);
        page = await context.newPage();
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        // Reject every business write from this browser acceptance.
        await page.route('**/web/dataset/call_kw/**', async route => {
            const body = route.request().postDataJSON();
            const method = body?.params?.method || '';
            if (/^(create|write|unlink|web_save|action_)/.test(method)) {
                throw new Error('Unexpected browser business write: ' + method);
            }
            await route.continue();
        });
        async function open(action, model, id) {
            await page.goto(`https://${proof.host}/web#action=${action}&model=${model}&id=${id}&view_type=form&cids=${proof.company_id}`,
                { waitUntil:'domcontentloaded',timeout:120000 });
            await page.locator('.o_form_view').waitFor({timeout:120000});
            assert.equal(await page.locator('.o_error_dialog').count(), 0);
        }
        const checked = [];
        for (const tag of proof.tags) {
            const response = page.waitForResponse(r => r.url().includes('/stock.quant.package/web_read'), {timeout:60000});
            await open(proof.actions.tags, 'stock.quant.package', tag.package_id);
            const result = await (await response).json();
            assert.ok(!result.error, result.error?.data?.message);
            const row = result.result.find(r => r.id === tag.package_id);
            assert.ok(row, 'Wrong tag form');
            assert.equal(row.name, tag.name);
            assert.equal(row.step_actual_kg, tag.new_kg);
            await page.getByText(tag.name, {exact:true}).first().waitFor({timeout:30000});
            const kilos = page.locator('.o_field_widget[name="step_actual_kg"]');
            await kilos.waitFor();
            await page.screenshot({path:path.join(output, `${tag.name}.png`),fullPage:true});
            checked.push({id:tag.package_id,kilos:row.step_actual_kg});
        }
        for (const id of [...new Set(proof.tags.map(t => t.picking_id))]) {
            await open(proof.actions.receipts, 'stock.picking', id);
            await page.screenshot({path:path.join(output, `receipt-${id}.png`),fullPage:true});
        }
        for (const draft of proof.drafts) {
            const response = page.waitForResponse(r => r.url().includes('/purchase.order/web_read'), {timeout:60000});
            await open(proof.actions.advances, 'purchase.order', draft.id);
            const result = await (await response).json();
            assert.ok(!result.error, result.error?.data?.message);
            const row = result.result.find(r => r.id === draft.id);
            assert.equal(row.step_fruit_state, 'draft');
            assert.equal(row.amount_total, draft.total);
            await page.screenshot({path:path.join(output, `advance-${draft.id}.png`),fullPage:true});
        }
        assert.deepEqual(errors, []);
        const result = {tags:checked,receipts:2,advanceDrafts:2,totalKg:proof.total_kg,
                        nativeForms:true,browserWrites:0,errors};
        fs.writeFileSync(path.join(output,'ui-result.json'), JSON.stringify(result,null,2));
        console.log('T240_BROWSER_OK '+JSON.stringify(result));
    } catch (error) {
        if (page) await page.screenshot({path:path.join(output,'failure.png'),fullPage:true}).catch(()=>{});
        throw error;
    } finally { await browser.close(); }
})().catch(error => { console.error(error.message); process.exitCode=1; });
