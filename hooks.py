# -*- coding: utf-8 -*-
"""
Post-init hook: corrige la fórmula de IVA Retención Global
en instalaciones nuevas del módulo (cambio -0.80 → -0.15).
La migración 18.0.5.44 cubre las instalaciones existentes.
"""
import logging
_logger = logging.getLogger(__name__)

OLD_FORMULA_FRAGMENT = '* -0.80)'
NEW_FORMULA_FRAGMENT = '* -0.15)'


def post_init_hook(env):
    taxes = env['account.tax'].search([
        ('name', 'ilike', 'IVA Retención Global'),
        ('amount_type', '=', 'code'),
    ])
    count = 0
    for tax in taxes:
        if OLD_FORMULA_FRAGMENT in (tax.formula or ''):
            tax.formula = tax.formula.replace(
                OLD_FORMULA_FRAGMENT, NEW_FORMULA_FRAGMENT
            )
            count += 1
    if count:
        _logger.info(
            "l10n_gt_extra post_init_hook: "
            "corregida fórmula IVA Retención Global en %d impuesto(s)", count
        )
