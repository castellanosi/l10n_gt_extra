import logging
_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """No hay vistas viejas que limpiar para los reportes nuevos en v18.
    Esta migración existe para marcar la versión 6.0 como instalada."""
    _logger.info("l10n_gt_extra: migración a 18.0.6.0 — reportes nuevos instalados")
