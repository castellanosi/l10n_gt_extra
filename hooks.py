import logging
_logger = logging.getLogger(__name__)
OLD = '* -0.80)'
NEW = '* -0.15)'
def post_init_hook(env):
    taxes = env['account.tax'].search([('name','ilike','IVA Retencion Global'),('amount_type','=','code')])
    count = 0
    for tax in taxes:
        if OLD in (tax.formula or ''):
            tax.formula = tax.formula.replace(OLD, NEW)
            count += 1
    if count:
        _logger.info("l10n_gt_extra post_init_hook: %d impuesto(s) corregidos", count)
