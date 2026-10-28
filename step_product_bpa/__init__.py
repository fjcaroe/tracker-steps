from . import models


def pre_init_hook(env):
    env.cr.execute("SELECT to_regclass('x_aptitud_plaguicidas')")
    assert not env.cr.fetchone()[0], 'Run the versioned in-place BPA migration before installing this addon'
