# -*- coding: utf-8 -*-
import logging
_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    v5.42: elimina registros UI de los 3 reportes quitados:
      Inventario | FEL | Pequeño Contribuyente

    Nombres de tabla reales en Odoo 18 (PostgreSQL):
      ir.actions.act_window  → ir_act_window      (NO ir_actions_act_window)
      ir.actions.report      → ir_act_report_xml  (NO ir_actions_report)
    """
    TABLE_MAP = {
        'ir.ui.menu':            'ir_ui_menu',
        'ir.actions.act_window': 'ir_act_window',
        'ir.actions.report':     'ir_act_report_xml',
        'ir.ui.view':            'ir_ui_view',
    }

    to_delete = {
        'ir.ui.menu': [
            'l10n_gt_extra.reporte_inventario_wizard_menu',
            'l10n_gt_extra.reporte_fel_wizard_menu',
            'l10n_gt_extra.reporte_pequeno_wizard_menu',
        ],
        'ir.actions.act_window': [
            'l10n_gt_extra.reporte_inventario_wizard_action',
            'l10n_gt_extra.reporte_fel_wizard_action',
            'l10n_gt_extra.reporte_pequeno_wizard_action',
        ],
        'ir.actions.report': [
            'l10n_gt_extra.reporte_inventario_wizard_report',
            'l10n_gt_extra.reporte_fel_wizard_report',
            'l10n_gt_extra.reporte_pequeno_wizard_report',
        ],
        'ir.ui.view': [
            'l10n_gt_extra.reporte_inventario_wizard_view_form',
            'l10n_gt_extra.reporte_fel_wizard_view_form',
            'l10n_gt_extra.reporte_pequeno_wizard_view_form',
            'l10n_gt_extra.reporte_inventario',
            'l10n_gt_extra.reporte_fel',
            'l10n_gt_extra.reporte_pequeno',
        ],
    }

    for model, xml_ids in to_delete.items():
        table = TABLE_MAP[model]
        for xml_id in xml_ids:
            module, name = xml_id.split('.')
            cr.execute(
                "SELECT res_id FROM ir_model_data "
                "WHERE module=%s AND name=%s AND model=%s",
                (module, name, model)
            )
            row = cr.fetchone()
            if row:
                cr.execute(f"DELETE FROM {table} WHERE id=%s", (row[0],))
                cr.execute(
                    "DELETE FROM ir_model_data WHERE module=%s AND name=%s",
                    (module, name)
                )
                _logger.info("5.42 eliminado: %s [%s]", xml_id, model)
            else:
                _logger.info("5.42 no encontrado (ok): %s", xml_id)

    _logger.info("l10n_gt_extra 5.42: migración completada")
