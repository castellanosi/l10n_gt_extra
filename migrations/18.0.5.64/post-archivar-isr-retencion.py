# -*- coding: utf-8 -*-
"""
v5.64: archiva el impuesto «ISR Retención» (fórmula por línea, base / 1.12)
que creaba la plantilla. Ya no está en account.tax-gt.csv: las retenciones
se registran con el botón «Retención» (pago) desde 5.62.

Se busca por su xmlid de plantilla (<empresa>_impuestos_plantilla_isr_retencion),
así no toca impuestos que el usuario haya creado con un nombre parecido.
Archivar no borra: las facturas antiguas que lo usan no cambian.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    datos = env['ir.model.data'].search([
        ('model', '=', 'account.tax'),
        ('name', '=like', '%impuestos_plantilla_isr_retencion'),
    ])
    impuestos = env['account.tax'].with_context(active_test=False).browse(
        datos.mapped('res_id')).exists().filtered('active')

    archivados = 0
    for tax in impuestos:
        try:
            with cr.savepoint():
                tax.active = False
            archivados += 1
            _logger.info("l10n_gt_extra 5.64: archivado impuesto %s (empresa %s)",
                         tax.name, tax.company_id.name)
        except Exception as e:  # noqa: BLE001 — no detener la actualización
            _logger.warning("l10n_gt_extra 5.64: no se pudo archivar %s: %s", tax.name, e)
    _logger.info("l10n_gt_extra 5.64: %d impuesto(s) ISR Retención archivado(s)", archivados)
