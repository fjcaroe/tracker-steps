"""Private diagnostics around the real official PDF pipeline, never replacements."""
from contextlib import ExitStack, contextmanager
import base64
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from lxml import html as etree


def write_private(path, content):
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    raw = content if isinstance(content, bytes) else str(content).encode('utf-8')
    with path.open('xb') as handle:
        handle.write(raw)
    path.chmod(0o600)
    return {'file': path.name, 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}


@contextmanager
def capture_pdf_pipeline(reports, output, company_name, country_name):
    """Call all official methods unchanged while retaining their actual inputs.

    Captured arguments come from _build_wkhtmltopdf_args, before the runner adds
    temporary session/cookie files. Neither cookies nor full context are saved.
    """
    output = Path(output)
    result = {'prepare_calls': [], 'run_calls': [], 'argument_calls': []}
    cls = type(reports)
    real_prepare = cls._prepare_html
    real_run = cls._run_wkhtmltopdf
    real_args = cls._build_wkhtmltopdf_args

    def environment(records):
        return {'uid': records.env.uid, 'sudo': records.env.su,
                'allowed_company_ids': list(records.env.context.get('allowed_company_ids', []))}

    def save_parts(prefix, bodies, header, footer):
        return {
            'bodies': [write_private(output / ('%s-body-%s.html' % (prefix, index)), body)
                       for index, body in enumerate(bodies)],
            'header': write_private(output / (prefix + '-header.html'), header or ''),
            'footer': write_private(output / (prefix + '-footer.html'), footer or ''),
        }

    def prepare(records, html, report_model=False):
        value = real_prepare(records, html, report_model=report_model)
        bodies, ids, header, footer, paper = value
        index = len(result['prepare_calls'])
        tree = etree.fromstring(header)
        text = tree.text_content()
        logos = []
        for source in tree.xpath('//img/@src'):
            if source.startswith('data:') and ';base64,' in source:
                raw = base64.b64decode(source.split(';base64,', 1)[1], validate=True)
                logos.append({'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)})
        result['prepare_calls'].append({
            'environment': environment(records), 'report_model': report_model,
            'html': write_private(output / ('prepare-%s.html' % index), html),
            **save_parts('prepare-%s' % index, bodies, header, footer),
            'document_ids': ids, 'specific_paperformat_args': paper,
            'company_name_present': company_name in text,
            'country_name_present': country_name in text, 'embedded_images': logos,
        })
        return value

    def build_args(records, paperformat_id, landscape, specific_paperformat_args=None,
                   set_viewport_size=False):
        value = real_args(records, paperformat_id, landscape,
                          specific_paperformat_args=specific_paperformat_args,
                          set_viewport_size=set_viewport_size)
        fields = ['id', 'format', 'page_height', 'page_width', 'orientation', 'margin_top',
                  'margin_bottom', 'margin_left', 'margin_right', 'header_line',
                  'header_spacing', 'dpi', 'disable_shrinking']
        if 'css_margins' in paperformat_id._fields:
            fields.append('css_margins')
        result['argument_calls'].append({
            'environment': environment(records),
            'paperformat': paperformat_id.read(fields) if paperformat_id else [],
            'landscape': landscape, 'specific_paperformat_args': specific_paperformat_args,
            'set_viewport_size': set_viewport_size, 'arguments': list(value),
            'session_arguments_captured': False,
        })
        return value

    def run(records, bodies, report_ref=False, header=None, footer=None, landscape=False,
            specific_paperformat_args=None, set_viewport_size=False):
        index = len(result['run_calls'])
        result['run_calls'].append({
            'environment': environment(records),
            **save_parts('run-%s' % index, bodies, header, footer),
            'landscape': landscape, 'specific_paperformat_args': specific_paperformat_args,
            'set_viewport_size': set_viewport_size,
        })
        return real_run(records, bodies, report_ref=report_ref, header=header, footer=footer,
                        landscape=landscape, specific_paperformat_args=specific_paperformat_args,
                        set_viewport_size=set_viewport_size)

    try:
        with ExitStack() as stack:
            stack.enter_context(patch.object(cls, '_prepare_html', prepare))
            stack.enter_context(patch.object(cls, '_build_wkhtmltopdf_args', build_args))
            stack.enter_context(patch.object(cls, '_run_wkhtmltopdf', run))
            yield result
    finally:
        write_private(output / 'pipeline.json', json.dumps(result, indent=2, sort_keys=True))
