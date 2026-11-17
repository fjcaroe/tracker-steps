"""Replace the center-only uniqueness without rewriting historical rows."""
def migrate(cr, version):
    cr.execute("""
        ALTER TABLE step_management_estimation_line
        DROP CONSTRAINT IF EXISTS step_management_estimation_line_estimation_line_center_unique
    """)
