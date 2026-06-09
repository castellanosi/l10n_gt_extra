# -*- coding: utf-8 -*-
"""
v5.44: corrige fórmula IVA Retención Global (-0.80 → -0.15).
Nota: en Odoo 18 el campo name de account.tax es jsonb (traducible),
requiere cast explícito a text para usar LOWER/LIKE.
"""
import logging
_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("""
        UPDATE account_tax
        SET formula = REPLACE(formula, '* -0.80)', '* -0.15)')
        WHERE LOWER(name::text) LIKE '%%iva%%retenci%%global%%'
          AND amount_type = 'code'
          AND formula LIKE '%%* -0.80)%%'
    """)
    affected = cr.rowcount
    _logger.info(
        "l10n_gt_extra 5.44: fórmula IVA Retención corregida "
        "en %d impuesto(s)", affected
    )
