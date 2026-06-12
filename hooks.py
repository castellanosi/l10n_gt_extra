# -*- coding: utf-8 -*-
import logging
_logger = logging.getLogger(__name__)

OLD_FORMULA_FRAGMENT = '* -0.80)'
NEW_FORMULA_FRAGMENT = '* -0.15)'


def post_init_hook(env):
    """
    Corrige formula IVA Retencion Global en instalaciones nuevas.
    Aplica a TODAS las empresas (independiente de regimen).
    Si l10n_gt_peq esta instalado, su propio hook corrige luego PEQ a 5%%.
    """
    taxes = env['account.tax'].search([
        ('name', 'ilike', 'IVA Retencion Global'),
        ('amount_type', '=', 'code'),
    ])
    count = 0
    for tax in taxes:
        if OLD_FORMULA_FRAGMENT in (tax.formula or ''):
            tax.formula = tax.formula.replace(OLD_FORMULA_FRAGMENT, NEW_FORMULA_FRAGMENT)
            count += 1
    if count:
        _logger.info(
            "l10n_gt_extra post_init_hook: corregida formula en %d impuesto(s)", count
        )
