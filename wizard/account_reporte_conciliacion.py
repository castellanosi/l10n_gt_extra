# -*- encoding: utf-8 -*-

from odoo import models, fields
import time
import xlsxwriter
import base64
import io


class AsistenteReporteConciliacion(models.TransientModel):
    _name = 'l10n_gt_extra.reporte_conciliacion.wizard'
    _description = 'Conciliación Bancaria Cuadrática'

    def _default_cuenta(self):
        ids = self.env.context.get('active_ids', [])
        return ids[0] if ids else None

    cuenta_id = fields.Many2one(
        'account.account', string="Cuenta bancaria", required=True,
        default=_default_cuenta,
        domain="[('account_type', 'in', ['asset_cash', 'asset_current'])]",
    )
    fecha_hasta = fields.Date(
        string="Al corte del", required=True,
        default=lambda self: time.strftime('%Y-%m-%d'),
    )
    saldo_banco = fields.Float(
        string="Saldo extracto bancario", digits=(16, 2),
        help="Ingrese el saldo que aparece en el estado de cuenta del banco",
    )
    name = fields.Char('Nombre archivo')
    archivo = fields.Binary('Archivo')

    def _build_dict(self):
        return {
            'cuenta_id': [self.cuenta_id.id, self.cuenta_id.display_name],
            'fecha_hasta': self.fecha_hasta,
            'saldo_banco': self.saldo_banco,
        }

    def print_report(self):
        data = {'ids': [], 'model': self._name, 'form': self._build_dict()}
        return self.env.ref('l10n_gt_extra.reporte_conciliacion_wizard_report').report_action(
            self, data=data)

    def print_report_excel(self):
        res = self.env['report.l10n_gt_extra.reporte_conciliacion'].datos(self._build_dict())

        f = io.BytesIO()
        libro = xlsxwriter.Workbook(f)
        hoja = libro.add_worksheet('Conciliación')
        fmt_fecha = libro.add_format({'num_format': 'dd/mm/yy'})
        fmt_num = libro.add_format({'num_format': '#,##0.00'})
        fmt_bold = libro.add_format({'bold': True})

        hoja.write(0, 0, self.env.company.name + ': Conciliación Bancaria')
        hoja.write(1, 0, 'Cuenta: ' + self.cuenta_id.display_name)
        hoja.write(2, 0, 'Al: ' + str(self.fecha_hasta))

        y = 4
        hoja.write(y, 0, 'Saldo extracto bancario', fmt_bold)
        hoja.write(y, 3, res['saldo_banco'], fmt_num)

        y += 2
        hoja.write(y, 0, 'MÁS: Depósitos en tránsito', fmt_bold)
        y += 1
        for col, h in enumerate(['Fecha', 'Documento', 'Concepto', 'Monto']):
            hoja.write(y, col, h, fmt_bold)
        for dep in res['depositos_transito']:
            y += 1
            hoja.write(y, 0, dep['fecha'], fmt_fecha)
            hoja.write(y, 1, dep['documento'])
            hoja.write(y, 2, dep['concepto'])
            hoja.write(y, 3, dep['monto'], fmt_num)
        y += 1
        hoja.write(y, 2, 'Total depósitos en tránsito', fmt_bold)
        hoja.write(y, 3, res['total_depositos'], fmt_num)

        y += 2
        hoja.write(y, 0, 'MENOS: Cheques pendientes', fmt_bold)
        y += 1
        for col, h in enumerate(['Fecha', 'Documento', 'Concepto', 'Monto']):
            hoja.write(y, col, h, fmt_bold)
        for chq in res['cheques_pendientes']:
            y += 1
            hoja.write(y, 0, chq['fecha'], fmt_fecha)
            hoja.write(y, 1, chq['documento'])
            hoja.write(y, 2, chq['concepto'])
            hoja.write(y, 3, chq['monto'], fmt_num)
        y += 1
        hoja.write(y, 2, 'Total cheques pendientes', fmt_bold)
        hoja.write(y, 3, res['total_cheques'], fmt_num)

        y += 2
        hoja.write(y, 0, 'SALDO AJUSTADO BANCO', fmt_bold)
        hoja.write(y, 3, res['saldo_ajustado_banco'], fmt_num)

        y += 2
        hoja.write(y, 0, 'SALDO SEGÚN LIBROS', fmt_bold)
        hoja.write(y, 3, res['saldo_libro'], fmt_num)

        y += 1
        hoja.write(y, 0, 'DIFERENCIA', fmt_bold)
        hoja.write(y, 3, res['diferencia'], fmt_num)

        libro.close()
        self.write({'archivo': base64.b64encode(f.getvalue()), 'name': 'conciliacion_bancaria.xlsx'})
        return {'type': 'ir.actions.act_window', 'res_model': self._name,
                'view_mode': 'form', 'res_id': self.id, 'target': 'new'}
