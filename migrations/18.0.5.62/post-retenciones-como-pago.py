# -*- coding: utf-8 -*-
"""
v5.62: las retenciones de IVA e ISR se registran como pago (asistente
«Registrar retención»), ya no con impuestos de fórmula.

1. Archiva los impuestos «IVA/ISR Retención Global» (compras y ventas).
   Las facturas antiguas que los usan no cambian: archivar no borra.
2. Marca como diario de retención los diarios banco/efectivo cuyo nombre
   dice «Retención» e «IVA» o «ISR» (p. ej. «Retención IVA Recibida»).
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def _norm(texto):
    return (texto or '').lower().replace('ó', 'o')


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    impuestos = env['account.tax'].with_context(active_test=False).search([
        ('amount_type', '=', 'code'), ('active', '=', True)])
    globales = impuestos.filtered(
        lambda t: 'retencion global' in _norm(t.name))
    for tax in globales:
        try:
            with cr.savepoint():
                tax.active = False
            _logger.info("l10n_gt_extra 5.62: archivado impuesto %s (empresa %s)",
                         tax.name, tax.company_id.name)
        except Exception as e:  # noqa: BLE001 — no detener la actualización
            _logger.warning("l10n_gt_extra 5.62: no se pudo archivar %s: %s", tax.name, e)

    diarios = env['account.journal'].with_context(active_test=False).search([
        ('type', 'in', ('bank', 'cash')), ('l10n_gt_retencion', '=', False)])
    marcados = 0
    for j in diarios:
        nombre = _norm(j.name)
        if 'retencion' not in nombre:
            continue
        if 'iva' in nombre:
            j.l10n_gt_retencion = 'iva'
        elif 'isr' in nombre:
            j.l10n_gt_retencion = 'isr'
        else:
            continue
        marcados += 1
        _logger.info("l10n_gt_extra 5.62: diario «%s» marcado como retención %s",
                     j.name, j.l10n_gt_retencion.upper())
    _logger.info("l10n_gt_extra 5.62: %d impuesto(s) archivado(s), %d diario(s) marcado(s)",
                 len(globales), marcados)
