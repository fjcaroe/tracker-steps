"""Upgrade while retaining existing validated canonical fruit relationships."""
import sys
sys.path.insert(0, '/opt/odoo18')
from preserve_fruit_constraints import install
install()
import odoo.cli
odoo.cli.main()
