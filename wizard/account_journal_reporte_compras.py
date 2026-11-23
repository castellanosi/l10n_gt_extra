# -*- encoding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import time
import base64
import logging

from ..report.tipos_dte import REGIMENES_IVA, regimen_en_fecha
from .libro_excel import generar_excel

class AsistenteReporteCompras(models.TransientModel):
    _name = 'l10n_gt_extra.reporte_compras.wizard'
    _description = 'Libro de Compras'

    diarios_id = fields.Many2many("account.journal", string="Diarios", required=True)
    impuestos_id = fields.Many2many("account.tax", string="Impuestos", required=True)
    regimen_comprador = fields.Selection(
        REGIMENES_IVA,
        string="Régimen de la empresa en el periodo",
        required=True,
        default=lambda self: self._regimen_de_la_empresa(time.strftime('%Y-%m-01')),
        help="Se toma del régimen de la empresa (l10n_gt_peq) vigente en la "
             "fecha inicial, según su historial. PEQ o EXE: ninguna compra da "
             "crédito fiscal y todo va a exento. Cambiar solo si el dato de "
             "la empresa no corresponde al periodo.",
    )
    folio_inicial = fields.Integer(string="Folio Inicial", required=True, default=1)
    incluir_control = fields.Boolean(
        string="Incluir control",
        default=False,
        help="Agrega al final el bloque «Control»: IVA del libro contra IVA "
             "contable, redondeo del IVA de los DTE, documentos que no cuadran "
             "y avisos. Es para revisión del contador: el libro oficial se "
             "imprime sin marcar esta casilla.",
    )
    fecha_desde = fields.Date(string="Fecha Inicial", required=True, default=lambda self: time.strftime('%Y-%m-01'))
    fecha_hasta = fields.Date(string="Fecha Final", required=True, default=lambda self: time.strftime('%Y-%m-%d'))
    name = fields.Char('Nombre archivo')
    archivo = fields.Binary('Archivo')

    def _regimen_de_la_empresa(self, fecha):
        """Régimen de l10n_gt_peq en la fecha, sin depender de ese módulo.

        Si l10n_gt_peq no está instalado (servidores sin él), GEN: el libro
        se comporta como siempre.
        """
        company = self.env.company
        if 'gt_tax_regime' not in company._fields:
            return 'GEN'
        historial = []
        if 'regime_history_ids' in company._fields:
            historial = company.sudo().regime_history_ids
        return regimen_en_fecha(historial, company.gt_tax_regime, fields.Date.to_date(fecha))

    @api.onchange('fecha_desde')
    def _onchange_fecha_desde_regimen(self):
        for w in self:
            w.regimen_comprador = w._regimen_de_la_empresa(w.fecha_desde)

    def print_report(self):
        data = {
             'ids': [],
             'model': 'l10n_gt_extra.reporte_compras.wizard',
             'form': self.read()[0]
        }
        return self.env.ref('l10n_gt_extra.reporte_compras_wizard_report').with_context(landscape=True).report_action(self, data=data)


    def preview_report(self):
        data = {
            'ids': [],
            'model': self._name,
            'form': self.read()[0],
        }
        action = self.env.ref('l10n_gt_extra.reporte_compras_wizard_report').with_context(landscape=True).report_action(self, data=data)
        action['report_type'] = 'qweb-html'
        return action

    def print_report_excel(self):
        for w in self:
            dict = {}
            dict['fecha_hasta'] = w['fecha_hasta']
            dict['fecha_desde'] = w['fecha_desde']
            dict['impuestos_id'] = [i.id for i in w.impuestos_id]
            dict['diarios_id'] =[x.id for x in w.diarios_id]
            dict['regimen_comprador'] = w.regimen_comprador
            dict['incluir_control'] = w.incluir_control

            res = self.env['report.l10n_gt_extra.reporte_compras'].lineas(dict)
            contenido = generar_excel(
                w.diarios_id[0].company_id, w.fecha_desde, w.fecha_hasta, res, compras=True,
            )
            datos = base64.b64encode(contenido)
            self.write({'archivo':datos, 'name':'libro_de_compras.xlsx'})

        return {
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'l10n_gt_extra.reporte_compras.wizard',
            'res_id': self.id,
            'view_id': False,
            'type': 'ir.actions.act_window',
            'target': 'new',
        }
