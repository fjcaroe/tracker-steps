from odoo.addons.payroll import models as oca_models

# The SyS first-init overlay registers this exact master with the OCA engine
# so its native related fields already resolve during the first reflection.
if not hasattr(oca_models, "step_sys_input_type"):
    from . import input_type

from . import payroll

from . import work_entries

from . import ytd
from . import structure_scope
from . import original_configuration
from . import original_types
from . import original_relations
from . import original_type_relations
from . import original_translations
from . import original_nullable
from . import saved_inputs

from . import original_input_storage

from . import original_rule_projection
from . import original_history_deletion
from . import original_history_storage
