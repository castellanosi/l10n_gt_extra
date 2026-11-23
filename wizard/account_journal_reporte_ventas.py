# -*- encoding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import time
import base64
import logging

from .libro_excel import generar_excel

class AsistenteReporteVentas(models.TransientModel):
    _name = 'l10n_gt_extra.reporte_ventas.wizard'
    _description = 'Libro de Ventas'

    diarios_id = fields.Many2many("account.journal", string="Diarios", required=True)
    impuestos_id = fields.Many2many("account.tax", string="Impuestos", required=True)
    folio_inicial = fields.Integer(string="Folio Inicial", required=True, default=1)
    resumido = fields.Boolean(string="Resumido")
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

    def print_report(self):
        data = {
             'ids': [],
             'model': 'l10n_gt_extra.reporte_ventas.wizard',
             'form': self.read()[0]
        }
        return self.env.ref('l10n_gt_extra.ventas_reporte_wizard_report').with_context(landscape=True).report_action(self, data=data)


    def preview_report(self):
        data = {
            'ids': [],
            'model': self._name,
            'form': self.read()[0],
        }
        action = self.env.ref('l10n_gt_extra.ventas_reporte_wizard_report').with_context(landscape=True).report_action(self, data=data)
        action['report_type'] = 'qweb-html'
        return action

    def print_report_excel(self):
        for w in self:
            dict = {}
            dict['fecha_hasta'] = w['fecha_hasta']
            dict['fecha_desde'] = w['fecha_desde']
            dict['impuestos_id'] = [i.id for i in w.impuestos_id]
            dict['diarios_id'] =[x.id for x in w.diarios_id]
            dict['resumido'] = w['resumido']
            dict['incluir_control'] = w.incluir_control

            res = self.env['report.l10n_gt_extra.reporte_ventas'].lineas(dict)
            contenido = generar_excel(
                w.diarios_id[0].company_id, w.fecha_desde, w.fecha_hasta, res, compras=False,
            )
            datos = base64.b64encode(contenido)
            self.write({'archivo':datos, 'name':'libro_de_ventas.xlsx'})

        return {
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'l10n_gt_extra.reporte_ventas.wizard',
            'res_id': self.id,
            'view_id': False,
            'type': 'ir.actions.act_window',
            'target': 'new',
        }
