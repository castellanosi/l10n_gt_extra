# -*- encoding: utf-8 -*-

import base64
import io
import time

import xlsxwriter

from odoo import fields, models


class AsistenteReporteConciliacion(models.TransientModel):
    _name = 'l10n_gt_extra.reporte_conciliacion.wizard'
    _description = 'Conciliación Bancaria'

    folio_inicial = fields.Integer(string='Folio Inicial', required=True, default=1)

    def _default_cuenta(self):
        ids = self.env.context.get('active_ids', [])
        return ids[0] if ids else None

    cuenta_id = fields.Many2one(
        'account.account', string='Cuenta bancaria', required=True,
        default=_default_cuenta,
        domain="[('account_type', 'in', ['asset_cash', 'asset_current'])]",
    )
    fecha_hasta = fields.Date(
        string='Al corte del', required=True,
        default=lambda self: time.strftime('%Y-%m-%d'),
    )
    saldo_banco = fields.Float(
        string='Saldo según estado de cuenta', digits=(16, 2),
        help='Saldo que muestra el estado de cuenta del banco al corte. No se guarda: '
             'se escribe cada vez que se genera el reporte.',
    )
    name = fields.Char('Nombre archivo')
    archivo = fields.Binary('Archivo')

    def _build_dict(self):
        return {
            'folio_inicial': self.folio_inicial,
            'cuenta_id': [self.cuenta_id.id, self.cuenta_id.display_name],
            'fecha_hasta': self.fecha_hasta,
            'saldo_banco': self.saldo_banco,
        }

    def print_report(self):
        data = {'ids': [], 'model': self._name, 'form': self._build_dict()}
        return self.env.ref('l10n_gt_extra.reporte_conciliacion_wizard_report').report_action(self, data=data)

    def preview_report(self):
        action = self.print_report()
        action['report_type'] = 'qweb-html'
        return action

    def print_report_excel(self):
        res = self.env['report.l10n_gt_extra.reporte_conciliacion'].datos(self._build_dict())
        cia = self.env.company

        f = io.BytesIO()
        wb = xlsxwriter.Workbook(f)
        ws = wb.add_worksheet('Conciliación')
        fmt_titulo = wb.add_format({'bold': True, 'font_size': 12})
        fmt_fecha = wb.add_format({'num_format': 'dd/mm/yyyy'})
        num = '#,##0.00;(#,##0.00);0.00'
        fmt_num = wb.add_format({'num_format': num})
        fmt_num_b = wb.add_format({'num_format': num, 'bold': True})
        fmt_num_t = wb.add_format({'num_format': num, 'bold': True, 'top': 1})
        fmt_bold = wb.add_format({'bold': True})
        fmt_head = wb.add_format({'bold': True, 'bg_color': '#ede9f7'})
        fmt_ok = wb.add_format({'bold': True, 'font_color': '#1F7A1F', 'num_format': num})
        fmt_no = wb.add_format({'bold': True, 'font_color': '#C00000', 'num_format': num})
        ws.set_column(0, 0, 12)
        ws.set_column(1, 1, 22)
        ws.set_column(2, 2, 50)
        ws.set_column(3, 3, 16)

        ws.write(0, 0, cia.name, fmt_titulo)
        ws.write(1, 0, 'NIT {}'.format(cia.vat or ''), fmt_bold)
        ws.write(2, 0, 'Conciliación Bancaria', fmt_bold)
        ws.write(3, 0, 'Cuenta: ' + self.cuenta_id.display_name)
        ws.write(4, 0, 'Al {}'.format(self.fecha_hasta.strftime('%d/%m/%Y')))

        y = 6
        ws.write(y, 0, 'Saldo según libros', fmt_bold)
        ws.write_number(y, 3, res['saldo_libro'], fmt_num_b)

        def bloque(y, titulo, filas, total_titulo, total):
            y += 2
            ws.write(y, 0, titulo, fmt_bold)
            y += 1
            for col, h in enumerate(['Fecha', 'Documento', 'Concepto', 'Monto']):
                ws.write(y, col, h, fmt_head)
            for r in filas:
                y += 1
                ws.write_datetime(y, 0, r['fecha'], fmt_fecha)
                ws.write(y, 1, r['documento'])
                ws.write(y, 2, r['concepto'])
                ws.write_number(y, 3, r['monto'], fmt_num)
            y += 1
            ws.write(y, 2, total_titulo, fmt_bold)
            ws.write_number(y, 3, total, fmt_num_t)
            return y

        y = bloque(y, 'MÁS: Cheques y débitos en tránsito', res['cheques_pendientes'],
                   'Total cheques y débitos en tránsito', res['total_cheques'])
        y = bloque(y, 'MENOS: Depósitos y créditos en tránsito', res['depositos_transito'],
                   'Total depósitos y créditos en tránsito', res['total_depositos'])
        y += 2
        ws.write(y, 0, 'Saldo según banco (calculado)', fmt_bold)
        ws.write_number(y, 3, res['saldo_banco_calculado'], fmt_num_b)
        y += 1
        ws.write(y, 0, 'Saldo según estado de cuenta')
        ws.write_number(y, 3, res['saldo_banco'], fmt_num)
        y += 1
        cuadra = abs(res['diferencia']) < 0.01
        ws.write(y, 0, 'Diferencia (debe ser 0.00)', fmt_bold)
        ws.write_number(y, 3, res['diferencia'], fmt_ok if cuadra else fmt_no)

        wb.close()
        self.write({'archivo': base64.b64encode(f.getvalue()), 'name': 'conciliacion_bancaria.xlsx'})
        return {'type': 'ir.actions.act_window', 'res_model': self._name,
                'view_mode': 'form', 'res_id': self.id, 'target': 'new'}
