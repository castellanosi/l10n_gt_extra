# -*- coding: utf-8 -*-
"""
v5.65: crea en cada empresa que ya tiene plan contable la «Cuenta transitoria
retenciones (no tocar)» y los diarios RETENCION IVA / RETENCION ISR, sin
cuentas de pagos entrantes/salientes (las define el contador). No duplica:
si la empresa ya tiene un diario de retención de ese tipo, lo respeta.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for company in env['res.company'].search([]):
        if not company.chart_template:
            continue
        try:
            with cr.savepoint():
                company.with_context(allowed_company_ids=company.ids)._l10n_gt_crear_diarios_retencion()
            _logger.info("l10n_gt_extra 5.65: diarios de retención listos en %s", company.name)
        except Exception as e:  # noqa: BLE001 — no detener la actualización
            _logger.warning("l10n_gt_extra 5.65: no se pudieron crear en %s: %s", company.name, e)
