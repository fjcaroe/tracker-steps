"""Build an immutable management release directly from committed Git blobs."""
import argparse
import ast
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import xml.etree.ElementTree as ET

MODULES = ('step_management_costs', 'step_management_costs_agriculture',
           'step_management_costs_machinery', 'step_management_costs_tracker',
           'step_agriculture_catalogs', 'step_management_costs_producers')
SUFFIXES = {'.py', '.xml', '.csv', '.js', '.scss', '.css', '.svg', '.png', '.jpg', '.webp', '.avif', '.md', '.rst', '.po', '.pot'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--commit', default='HEAD')
    parser.add_argument('--kind', choices=('management', 'payroll', 'freight', 'export', 'homepage', 'settings', 'producers', 'fruit-reception', 'packing', 'cerro-stack', 'payroll-days', 'payroll-review', 'payroll-rounding', 'payroll-fixes', 'previred-fix', 'tarja', 'sale-format', 'client-revision', 'estimate-report', 'contract-report', 'fruit-reports', 'estimate-revision', 'fruit-categories', 'daily-estimate', 'shipment-provision', 'budget-design', 'shipping-design', 'document-design', 'purchase-mode', 'producer-change', 'balance-analytic', 'export-control', 'email-login', 'dispatch-improvements', 'export-dashboard', 'agro-analytics', 'harvest-planning', 'harvest-operations', 'agriculture-records', 'treasury-seasons', 'estimate-cancel-folios', 'supply-comparison', 'product-bpa', 'manual-contact', 'company-form', 'species-tariff', 'packaging-master', 'invoice-payments', 'packing-controls', 'packing-stock', 'reception-revision', 'packing-tare', 'export-catalog-currency', 'packing-ot-layout', 'dispatch-design', 'sag-prototype', 'sag-lot', 'traceability', 'sag-traceability'), default='management')
    parser.add_argument('--environment', choices=('development', 'demo-sys', 'sys', 'steps', 'cerro', 'qa-cerro'))
    args = parser.parse_args()
    if args.kind == 'invoice-payments':
        assert args.environment in ('development', 'cerro', 'qa-cerro'), 'T123 is authorized only for Development, Cerro and customer QA'
    assert args.environment != 'qa-cerro' or args.kind in ('payroll-days', 'product-bpa', 'manual-contact', 'company-form', 'species-tariff', 'packaging-master', 'invoice-payments', 'packing-controls', 'packing-stock', 'reception-revision','packing-tare'), 'Only explicit T117/T118/T119/T120/T121/T114/T122 packages are authorized for customer QA'
    root = Path(__file__).resolve().parents[2]
    assert not args.output.resolve().is_relative_to(root)
    commit = subprocess.check_output(['git', 'rev-parse', args.commit + '^{commit}'], cwd=root, text=True).strip()
    commit_time = int(subprocess.check_output(['git','show','-s','--format=%ct',commit],cwd=root,text=True).strip())
    modules = MODULES if args.kind == 'management' else ('step_environment_policy', 'step_payroll_engine_transition', 'step_hr_contract_days', 'step_hr_previred', 'step_hr_previred_simpledigital', 'step_hr_contract_lifecycle', 'step_hr_contract_lifecycle_simpledigital', 'step_hr_remuneration_book', 'step_inventory_packing', 'step_packing_operations', 'step_producer_fruit_flow')
    if args.kind == 'export':
        modules = ('step_export',)
    if args.kind == 'sale-format':
        modules = ('step_sale_export_report',)
    if args.kind == 'client-revision':
        modules = ('step_sale_export_report', 'step_export_client_revision')
    if args.kind in ('estimate-report', 'contract-report'):
        modules = ('step_producer_estimate_report',) if args.kind == 'estimate-report' else ('step_producer_contract_report',)
    if args.kind == 'sag-traceability':
        assert args.environment == 'development', 'Build approved content for Development validation first'
        modules = ('step_inventory_packing','step_packing_operations','step_packing_dispatch','step_packing_sag','step_export_traceability')
    if args.kind == 'traceability':
        assert args.environment == 'development', 'T94 QA en Desarrollo'
        modules = ('step_export_traceability',)
    if args.kind == 'sag-lot':
        assert args.environment == 'development', 'T93 solo Desarrollo para QA'
        modules = ('step_packing_operations', 'step_packing_dispatch', 'step_packing_sag')
    if args.kind == 'sag-prototype':
        assert args.environment == 'development', 'T92 solo autoriza Desarrollo'
        modules = ('step_packing_sag',)
    if args.kind == 'email-login':
        modules = ('step_auth_email_casefold',)
    if args.kind == 'product-bpa':
        assert args.environment in ('development', 'cerro', 'qa-cerro')
        modules = ('step_product_bpa', 'step_product_bpa_agriculture')
    if args.kind == 'manual-contact':
        assert args.environment in ('development','cerro','qa-cerro')
        modules = ('step_partner_manual_entry',)
    if args.kind == 'company-form':
        assert args.environment in ('development','cerro','qa-cerro')
        modules = ('step_company_form_restore','step_company_form_restore_payroll','step_company_edi_readiness')
    if args.kind == 'species-tariff':
        assert args.environment in ('development', 'cerro', 'qa-cerro')
        modules=('step_species_tariff',)
    if args.kind == 'packaging-master':
        assert args.environment in ('development', 'cerro', 'qa-cerro')
        modules=('step_packing_packaging_master',)
    if args.kind == 'invoice-payments':
        modules=('step_treasury_invoice_payment',)
    if args.kind == 'packing-controls':
        assert args.environment in ('development','cerro','qa-cerro')
        modules=('step_packing_analytics','step_application_profiles')
    if args.kind == 'packing-stock':
        assert args.environment in ('development','cerro','qa-cerro')
        modules = ('step_packing_operations','step_packing_stock_flow')
    if args.kind == 'reception-revision':
        assert args.environment in ('development', 'cerro', 'qa-cerro')
        modules = ('step_packing_reception_revision', 'step_packing_ticket_revision')
    if args.kind == 'packing-tare':
        assert args.environment in ('development', 'cerro', 'qa-cerro')
        modules = ('step_packing_tare',)
    if args.kind == 'packing-ot-layout':
        assert args.environment in ('development', 'cerro')
        modules = ('step_packing_ot_layout',)
    if args.kind == 'export-catalog-currency':
        assert args.environment in ('development', 'cerro')
        modules = ('step_export_catalog_currency',)
    if args.kind == 'supply-comparison':
        assert args.environment in ('development', 'cerro')
        modules = ('step_export_supply_comparison',)
    if args.kind == 'estimate-cancel-folios':
        assert args.environment in ('development', 'cerro')
        modules = ('step_producer_estimate_cancel', 'step_export_folio_settings')
    if args.kind == 'treasury-seasons':
        modules = ('step_bank_security', 'step_season_navigation')
    if args.kind == 'agriculture-records':
        assert args.environment in ('development', 'cerro'), 'T103 authorizes Desarrollo and Cerro only (reply 9598)'
        modules = ('step_agriculture_records','step_bpa_irrigation','step_bpa_inventory','step_qa','step_agro_traceability','step_budget_design','step_cosecha','step_cosecha_operations')
    if args.kind == 'harvest-operations':
        modules = ('step_cosecha_operations',)
    if args.kind == 'harvest-planning':
        modules = ('step_cosecha_planning',)
    if args.kind == 'agro-analytics':
        modules = ('step_agro_analytics',)
    if args.kind == 'export-dashboard':
        modules = ('step_export_dashboard',)
    if args.kind == 'dispatch-improvements':
        modules = ('step_packing_dispatch_improvements',)
    if args.kind == 'dispatch-design':
        modules = ('step_packing_dispatch',)
    if args.kind == 'export-control':
        modules = ('step_export_control',)
    if args.kind == 'balance-analytic':
        modules = ('step_account_balance_analytic',)
    if args.kind == 'producer-change':
        modules = ('step_packing_producer_change',)
    if args.kind == 'purchase-mode':
        modules = ('step_producer_purchase_mode',)
    if args.kind == 'document-design':
        modules = ('step_export_document_revision',)
    if args.kind == 'shipping-design':
        modules = ('step_export_shipping_design',)
    if args.kind == 'budget-design':
        modules = ('step_budget_design',)
    if args.kind == 'shipment-provision':
        modules = ('step_export_shipment_provision',)
    if args.kind == 'daily-estimate':
        modules = ('step_producer_daily_estimate',)
    if args.kind == 'fruit-categories':
        modules = ('step_fruit_category_unification',)
    if args.kind == 'estimate-revision':
        modules = ('step_producer_estimate_revision',)
    if args.kind == 'fruit-reports':
        modules = ('step_producer_fruit_reports',)
    if args.kind == 'freight':
        modules = ('step_operations_ui', 'step_dispatch_guide')
    if args.kind == 'homepage':
        modules = ('step_demo_homepage',)
    if args.kind == 'producers':
        modules = ('step_producers', 'step_producer_fruit_flow', 'step_export', 'step_producers_integrations')
    if args.kind == 'settings':
        modules = ('step_account_treasury_batch', 'step_dispatch_guide')
    if args.kind == 'fruit-reception':
        modules = ('step_inventory_packing',)
    if args.kind == 'packing':
        modules = ('step_packing_operations',)
    if args.kind == 'payroll-days':
        assert args.environment in ('development','sys','demo-sys','cerro','qa-cerro')
        modules=('step_hr_contract_days',)
    if args.kind == 'payroll-review':
        assert args.environment in ('development','sys')
        modules = ('step_payroll_engine_transition','step_payroll_batch_period')
    if args.kind == 'payroll-rounding':
        assert args.environment in ('development', 'sys', 'cerro')
        modules = ('step_hr_payroll_rounding',)
    if args.kind == 'payroll-fixes':
        modules = ('step_hr_previred', 'step_hr_previred_simpledigital', 'step_hr_contract_lifecycle_simpledigital')
    if args.kind == 'previred-fix':
        modules = ('step_hr_previred',)
    if args.kind == 'tarja':
        modules = ('step_inventory_packing', 'step_packing_operations')
    if args.kind == 'cerro-stack':
        from stack_scope import MODULES as modules
    if args.environment == 'demo-sys':
        if args.kind not in ('payroll','payroll-days'):
            parser.error('Demo-SYS replica SyS; este publicador solo prepara Nómina para ese destino')
        modules = tuple(name for name in modules if name not in (
            'step_inventory_packing', 'step_packing_operations', 'step_producer_fruit_flow'))
    raw = subprocess.check_output(['git', 'archive', '--format=tar', commit, *modules], cwd=root)
    entries = {}
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        for member in archive.getmembers():
            if not member.isfile() or Path(member.name).suffix not in SUFFIXES:
                continue
            data = archive.extractfile(member).read()
            if member.name.endswith('.py'):
                ast.parse(data.decode('utf-8'), member.name)
            elif member.name.endswith(('.xml', '.svg')):
                ET.fromstring(data)
            entries[member.name] = data
    versions = {name: ast.literal_eval(entries[name + '/__manifest__.py'].decode())['version'] for name in modules}
    proof = {'commit': commit, 'versions': versions, 'files': {name: hashlib.sha256(data).hexdigest() for name, data in entries.items()}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(args.output, 'w:gz') as archive:
        for name, data in [*sorted(entries.items()), ('release.json', json.dumps(proof, indent=2).encode())]:
            member = tarfile.TarInfo(name)
            member.size = len(data)
            member.mode = 0o644
            # Odoo versions asset URLs from file mtimes. Epoch-zero mtimes can
            # keep an earlier JS/template bundle cached after a real update.
            member.mtime = commit_time
            archive.addfile(member, io.BytesIO(data))
    print('MANAGEMENT_RELEASE_OK ' + json.dumps({'commit': commit, 'sha256': hashlib.sha256(args.output.read_bytes()).hexdigest(), 'files': len(entries), 'versions': versions}))


if __name__ == '__main__':
    main()
