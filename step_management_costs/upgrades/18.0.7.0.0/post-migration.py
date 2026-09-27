import logging


_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Las tablas nuevas se crean por ORM; conservar evidencia de upgrade."""
    cr.execute("SELECT count(*) FROM step_management_estimation_curve")
    count = cr.fetchone()[0]
    _logger.info(
        "Gestión y Costos 18.0.7.0.0: %s curvas de estimación disponibles.", count,
    )
