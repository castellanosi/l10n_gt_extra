# -*- coding: utf-8 -*-
"""
v5.43: agrega columna numero_retencion en account_move.
Odoo la crea automáticamente en nuevas instalaciones, pero en bases
existentes necesita el ALTER TABLE manual para no fallar en el inicio.
"""
import logging
_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("""
        ALTER TABLE account_move
        ADD COLUMN IF NOT EXISTS numero_retencion VARCHAR
    """)
    _logger.info("l10n_gt_extra 5.43: columna numero_retencion agregada")
