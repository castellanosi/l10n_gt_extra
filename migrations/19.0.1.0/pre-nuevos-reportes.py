import logging
_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """No hay vistas viejas que limpiar para los reportes nuevos en v19.
    Esta migración existe para marcar la versión 1.0 como instalada."""
    _logger.info("l10n_gt_extra: migración a 19.0.1.0 — reportes nuevos instalados")
