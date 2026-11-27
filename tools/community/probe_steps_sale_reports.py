"""Print the original Steps quotations and sales orders as an existing non-administrator."""
import hashlib
import os
from pathlib import Path
import re
import subprocess
import tempfile
from unittest.mock import patch

from lxml import html
from PIL import Image
from odoo.tools import format_amount

from probe_steps_crm_pipeline import digest


def clean(value):
    return ' '.join(value.split())


def run(env, pdf=False, output=None):
    if not __debug__ or not re.fullmatch(r'(?:MANAGEMENT_QA|COMMUNITY)_STEPS_CRM_[A-Z0-9_]+', env.cr.dbname):
        raise ValueError('Use the private Steps customer-sales pair.')
    orders = env['sale.order'].with_user(7).with_context(allowed_company_ids=[1])
    scope = orders.env
    assert not scope.su and not scope.user.has_group('base.group_system')
    action = scope.ref('sale.action_report_saleorder')
    bindings = scope['ir.actions.actions'].get_bindings('sale.order')['report']
    assert action.id in {row['id'] for row in bindings}
    assert action.model == 'sale.order' and action.report_type == 'qweb-pdf'
    rows = orders.search([],order='id')
    assert len(rows)==4 and sorted(rows.mapped('state')) == ['draft','sale','sale','sale']
    if output is not None:
        output = Path(output)
        assert pdf and output.resolve(strict=True) == output and output.is_relative_to('/opt/steps-validation')
        assert output.name == 'private-pages' and output.parent.parent.name == 'sale-reports'
        assert output.stat().st_mode & 0o777 == 0o700 and output.stat().st_uid == os.getuid()
    rendered = []
    for order in rows:
        order.check_access('read')
        request = action.report_action(order)
        assert request['report_name'] == action.report_name
        body, kind = action._render_qweb_html(request['report_name'],order.ids)
        assert kind == 'html'
        root = html.fromstring(body)
        pages = root.xpath('//*[contains(concat(" ",normalize-space(@class)," ")," page ")]')
        assert pages
        visible = [clean(' '.join(p.itertext())) for p in pages]
        text = clean(' '.join(root.xpath('//body//text()[not(ancestor::script) and not(ancestor::style)]')))
        assert order.name in text
        currency = scope(context={**scope.context,'lang':order.partner_id.lang or scope.user.lang})
        amount = clean(format_amount(currency,order.amount_total,order.currency_id))
        assert amount.replace(' ','') in text.replace(' ','')
        row = {'id':order.id,'state':order.state,'body':digest(visible),'printed_total':True}
        if pdf:
            loopback = os.environ['STEPS_PRIVATE_REPORT_URL']
            assert re.fullmatch(r'http://127\.0\.0\.1:[0-9]+',loopback)
            model = type(scope['ir.config_parameter'])
            original = model.get_param
            def get_param(record, key, default=False):
                return loopback if key in ('report.url','web.base.url') else original(record,key,default)
            with patch.object(model,'get_param',get_param):
                file, ext = action.with_context(force_report_rendering=True)._render_qweb_pdf(request['report_name'],res_ids=order.ids)
            assert ext=='pdf' and file.startswith(b'%PDF-')
            with tempfile.TemporaryDirectory() as folder:
                path=Path(folder)/'sale.pdf'
                path.write_bytes(file)
                gs = ['gs','-q','-dSAFER','-dNOPAUSE','-dBATCH']
                lines = subprocess.check_output([*gs,'-sDEVICE=txtwrite','-dTextFormat=3',
                                                 '-sOutputFile=-',str(path)],encoding='utf-8')
                page_pattern = Path(folder)/'page-%04d.pgm'
                subprocess.run([*gs,'-sDEVICE=pgmraw','-r96','-sOutputFile='+str(page_pattern),str(path)],
                               check=True,stdout=subprocess.DEVNULL)
                rendered_pages = []
                for index, page in enumerate(sorted(Path(folder).glob('page-*.pgm')),start=1):
                    with Image.open(page) as paper:
                        pixels = paper.convert('L')
                        rendered_pages.append(digest([list(pixels.size),hashlib.sha256(pixels.tobytes()).hexdigest()]))
                        if output is not None:
                            pixels.save(output/f'{order.id}-{index}.png')
                if output is not None:
                    with (output/f'{order.id}.pdf').open('xb') as archived:
                        archived.write(file)
                    with (output/f'{order.id}.html').open('xb') as archived:
                        archived.write(body)
            pages_pdf = len(rendered_pages)
            normalized=clean(lines)
            assert order.name in normalized and amount.replace(' ','') in normalized.replace(' ','') and pages_pdf > 0
            row.update(pdf_pages=pages_pdf,pdf_text=digest(normalized),page_images=rendered_pages,
                       bytes_sha256=hashlib.sha256(file).hexdigest())
        rendered.append(row)
    return {'database':env.cr.dbname,'action':action.id,'uid':scope.uid,'documents':rendered}
