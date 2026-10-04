model = env['impuesto_2da_categoria']
record = model.cron_scraping_impuesto_2da_categoria()
print('T39_RESULT', record.id, record.date, record.first_line_to,
      record.second_line_from, record.second_line_factor,
      record.eighth_line_from, record.eighth_line_tasa_rebaja)
assert record.first_line_to == 974038.5
assert record.eighth_line_tasa_rebaja == 2800901.82
env.cr.commit()
