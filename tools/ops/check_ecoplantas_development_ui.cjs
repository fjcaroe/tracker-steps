/** Verify the migrated demo in the private Desarrollo copy. Login via stdin. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

async function main() {
    const request = JSON.parse(fs.readFileSync(0, "utf8"));
    const [executablePath, output, sha256] = process.argv.slice(2);
    const origin = "http://127.0.0.1:41477";
    const route = `/odoo/invernadero?cids=${request.company}`;
    assert(path.isAbsolute(output));
    assert(/^[a-f0-9]{64}$/.test(sha256));
    assert(/^ECOPLANTAS_DEV_QA_[a-z0-9_]+$/.test(request.db));
    fs.mkdirSync(output, { recursive: true });
    const browser = await chromium.launch({ executablePath, headless: true });
    const page = await browser.newPage({ viewport: { width: 1440, height: 1040 } });
    page.setDefaultTimeout(50000);
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    const board = page.locator(".o_ecoplantas_dashboard");
    const save = name => page.screenshot({ path: path.join(output, name + ".png") });
    const content = value => page.waitForFunction(text =>
        document.body.innerText.includes(text) ||
        Array.from(document.querySelectorAll(".o_form_view input")).some(input => input.value.includes(text)), value);
    const returnToBoard = async () => {
        await page.goto(origin + route, { waitUntil: "domcontentloaded" });
        await board.waitFor();
    };
    try {
        const login = new URL(origin + "/web/login");
        login.searchParams.set("db", request.db);
        login.searchParams.set("redirect", route);
        await page.goto(login.href, { waitUntil: "domcontentloaded" });
        await page.locator('input[name="login"]').fill(request.login);
        await page.locator('input[name="password"]').fill(request.password);
        await page.locator('form.oe_login_form button[type="submit"]').click();
        await board.waitFor();
        assert.equal(await page.locator("body").evaluate(body => body.classList.contains("o_ecoplantas_company")), true);
        assert.equal(await page.locator(".o_main_navbar").evaluate(node => getComputedStyle(node).backgroundColor), "rgb(23, 63, 51)");
        assert.deepEqual(await board.locator(".eco-metrics strong").allTextContents(), ["100", "2", "4"]);
        await save("invernadero-desarrollo");
        const visits = [
            ["Abrir recepción", "[DEMO] Semillas y sustrato"],
            ["Abrir orden", "Plantín de tomate [DEMO]"],
            ["Abrir control", "Revisión visual del lote de plantines [DEMO]"],
            ["Abrir despacho", "[DEMO] Despacho de plantines"],
            [/^Mantenimiento de riego/, "Revisar bomba y goteros [DEMO]"],
        ];
        for (const [label, value] of visits) {
            await board.getByRole("button", { name: label, exact: typeof label === "string" }).click();
            await page.locator(".o_ecoplantas_native_form").first().waitFor();
            await content(value);
            await returnToBoard();
        }
        await board.getByRole("button", { name: /^Labores de cultivo/ }).click();
        await page.getByText("Registrar riego y condición de bandejas [DEMO]", { exact: true }).first().waitFor();
        await returnToBoard();
        await board.getByRole("button", { name: /^Costos compartidos/ }).click();
        await page.locator(".o_list_view .o_data_row").filter({ hasText: "Servicios compartidos del vivero [DEMO]" }).click();
        await page.getByRole("button", { name: "Confirmar reparto", exact: true }).waitFor();
        assert.match(await page.locator('.o_field_widget[name="cost_total"]').innerText(), /200[.\s]?000/);
        assert.equal(await page.locator('.o_field_widget[name="line_ids"] .o_data_row').count(), 4);
        await save("reparto-desarrollo");

        await page.goto(origin + "/odoo?cids=1", { waitUntil: "domcontentloaded" });
        await page.locator(".o_web_client .o_main_navbar").waitFor();
        await page.waitForFunction(() => document.cookie.split(";").some(item => item.trim() === "cids=1"));
        assert.equal(await page.locator("body").evaluate(body => body.classList.contains("o_ecoplantas_company")), false);
        assert.deepEqual(errors, []);
        const proof = { sha256, company: request.company, other_company_unthemed: true, cost_preview: true, forms: visits.length };
        fs.writeFileSync(path.join(output, "browser-proof.json"), JSON.stringify(proof, null, 2));
        console.log("ECOPLANTAS_DEVELOPMENT_BROWSER_OK", JSON.stringify(proof));
    } catch (error) {
        await save("diagnostic").catch(() => {});
        const clean = value => value.replaceAll(request.login, "[usuario]").replaceAll(request.password, "[clave]");
        console.error(clean(error.message));
        console.error(JSON.stringify(errors.map(clean)));
        process.exitCode = 1;
    } finally {
        await browser.close();
    }
}

main().catch(error => { console.error(error.message); process.exitCode = 1; });
