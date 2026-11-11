/* Compile and exercise the actual header with the destination's Owl runtime. */
const fs = require('node:fs');
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
(async () => {
    const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH });
    try {
        const page = await browser.newPage();
        await page.setContent('<html><body></body></html>');
        await page.addScriptTag({ path: process.argv[2] });
        const source = fs.readFileSync('step_packing_dashboard/static/src/dashboard.xml','utf8');
        const results = await page.evaluate(async source => {
            const doc = new DOMParser().parseFromString(source,'text/xml');
            const header = doc.querySelector('.o_packing_period_filters').outerHTML;
            class Fixture extends owl.Component {
                static template = 'T201Header';
                setup() { this.state = owl.useState({ filters: { period:'season', date_from:'2026-09-01',
                    date_to:'2027-08-31', species_id:'' }, loading:false,
                    data:{species:[{id:2,name:'Arándano'}],period_label:'T2627'} }); }
                selectPeriod() {}
                changeDate() {}
                changeSpecies(event) { this.state.filters.species_id = Number(event.target.value); }
                loadDashboard() {}
            }
            const app = new owl.App(Fixture,{templates:'<templates><t t-name="T201Header">'+header+'</t></templates>'});
            const component = await app.mount(document.body);
            const select = document.querySelector('select');
            const options = [...select.options].map(o => ({value:o.value,label:o.textContent}));
            select.value = '2'; select.dispatchEvent(new Event('change',{bubbles:true}));
            await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
            return {options,selected:select.value,state:component.state.filters.species_id,
                seasonLabel:document.body.textContent.includes('T2627')};
        }, source);
        assert.equal(results.options.length,2);
        assert.equal(results.options[1].label,'Arándano');
        assert.equal(results.selected,'2');
        assert.equal(results.state,2);
        assert.equal(results.seasonLabel,true);
        console.log('PACKING_HEADER_TEMPLATE_OK '+JSON.stringify(results));
    } finally { await browser.close(); }
})().catch(error => { console.error(error.stack);process.exitCode=1; });
