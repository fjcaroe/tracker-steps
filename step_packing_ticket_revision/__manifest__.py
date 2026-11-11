{'name': 'Steps Packing reception and process reports', 'version': '18.0.1.2.4',
 'license': 'AGPL-3',
 'depends': ['step_packing_reception_revision', 'step_producer_fruit_reports',
             'step_export_document_revision', 'step_packing_ot_layout', 'step_packing_operations',
             'step_packing_overweight', 'step_packing_tag_split', 'step_dispatch_guide'],
 'data': ['ir.model.access.csv', 'views/packing.xml', 'views/reports.xml', 'views/reception_template_security.xml',
          'views/external_reception.xml', 'views/external_process.xml', 'views/external_multitag.xml',
          'views/dispatch_type.xml'], 'installable': True}
