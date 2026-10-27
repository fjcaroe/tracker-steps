"""Private agricultural extraction runner; retain canonical FKs and view IDs."""
import sys
sys.path.insert(0, '/opt/odoo18')
from preserve_fruit_constraints import install as install_fruit
from preserve_field_translations import install as install_field_translations
from preserve_action_view_ids import install as install_views, install_menu_order

install_fruit()
install_field_translations()
install_views()
install_menu_order()

import odoo.cli
odoo.cli.main()
