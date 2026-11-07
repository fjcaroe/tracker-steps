/** Inspect the shared-cost demo in an authenticated browser. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

async function main() {
    const request = JSON.parse(fs.readFileSync(0, "utf8"));
    const [executablePath, output, origin, sha256] = process.argv.slice(2);
    assert(path.isAbsolute(output));
    assert(["https://ecoplantas.stepsapp.cl", "http://127.0.0.1:41476"].includes(origin));
    assert(/^[a-f0-9]{64}$/.test(sha256));
    fs.mkdirSync(output, { recursive: true });
    const browser = await chromium.launch({ executablePath, headless: true });
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    page.setDefaultTimeout(45000);
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    const save = name => page.screenshot({ path: path.join(output, name + ".png") });
    const board = page.locator(".o_ecoplantas_dashboard");
    const poolName = "Servicios compartidos del vivero [DEMO]";
    try {
        await page.goto(origin + "/web/login?redirect=%2Fodoo", { waitUntil: "domcontentloaded" });
        await page.locator('input[name="login"]').fill(request.login);
        await page.locator('input[name="password"]').fill(request.password);
        await page.locator('form.oe_login_form button[type="submit"]').click();
        const card = board.getByRole("button", { name: /^Costos compartidos/ });
        await card.scrollIntoViewIfNeeded();
        await save("portada-costos");
        await card.click();
        const row = page.locator(".o_list_view .o_data_row").filter({ hasText: poolName });
        await row.waitFor();
        await row.click();

        const form = page.locator(".o_form_view.o_ecoplantas_native_form, .o_form_view .o_ecoplantas_native_form").first();
        await form.waitFor();
        await page.getByRole("button", { name: "Confirmar reparto", exact: true }).waitFor();
        const preview = page.locator('.o_field_widget[name="line_ids"] .o_data_row');
        assert.equal(await preview.count(), 4);
        const totals = await preview.allTextContents();
        assert(totals.some(row => row.includes("Propagación Norte") && /90[.\s]?000/.test(row)));
        assert(totals.some(row => row.includes("Propagación Sur") && /60[.\s]?000/.test(row)));
        assert.match(await page.locator('.o_field_widget[name="cost_total"]').innerText(), /200[.\s]?000/);
        await save("reparto-semanal");

        const openMenu = async name => {
            await page.locator(".o_main_navbar").getByText("Costos compartidos", { exact: true }).click();
            await page.getByText(name, { exact: true }).last().click();
        };
        await openMenu("Carga semanal");
        const weeklyGrid = page.locator(".o_list_view").filter({
            has: page.getByRole("columnheader", { name: /Cantidad semanal/ }),
        });
        const measures = weeklyGrid.locator(".o_data_row");
        await measures.first().waitFor();
        assert.equal(await measures.count(), 4);
        assert((await measures.allTextContents()).some(row => row.includes("Propagación Norte") &&
            row.includes("Superficie atendida") && row.includes("300")));
        await save("carga-drivers");
        await openMenu("Centros de costo");
        await page.locator(".o_list_view .o_data_row").filter({ hasText: poolName }).click();
        await page.getByText("Labores y drivers", { exact: true }).click();
        await page.getByText("Superficie atendida [DEMO]", { exact: true }).waitFor();
        await save("centro-padre");
        await page.getByText("Centros hijos", { exact: true }).click();
        await page.getByText("Propagación Norte [DEMO]", { exact: true }).waitFor();

        await page.setViewportSize({ width: 390, height: 844 });
        await page.goto(origin + "/odoo/invernadero", { waitUntil: "domcontentloaded" });
        await card.scrollIntoViewIfNeeded();
        assert(await board.evaluate(node => node.scrollWidth <= node.clientWidth + 1));
        await save("portada-movil");
        assert.deepEqual(errors, []);
        const proof = { sha256, origin, workflow: true, total: 200000, previews: 4, measures: 4, mobile: true };
        fs.writeFileSync(path.join(output, "browser-proof.json"), JSON.stringify(proof, null, 2));
        console.log("ECOPLANTAS_COST_BROWSER_OK", JSON.stringify(proof));
    } catch (error) {
        await save("diagnostic").catch(() => {});
        const clean = text => text.replaceAll(request.login, "[usuario]").replaceAll(request.password, "[clave]");
        console.error(clean(error.message));
        console.error(JSON.stringify(errors.map(clean)));
        process.exitCode = 1;
    } finally {
        await browser.close();
    }
}

main().catch(error => { console.error(error.message); process.exitCode = 1; });
