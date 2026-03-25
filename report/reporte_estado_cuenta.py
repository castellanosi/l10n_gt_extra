# -*- encoding: utf-8 -*-

from odoo import api, models


class ReporteEstadoCuenta(models.AbstractModel):
    _name = 'report.l10n_gt_extra.reporte_estado_cuenta'
    _description = 'Estado de Cuenta por Cliente / Proveedor'

    def saldo_anterior(self, datos):
        partner_id = datos['partner_id'][0]
        self.env.cr.execute(
            "SELECT COALESCE(SUM(l.debit) - SUM(l.credit), 0) AS saldo "
            "FROM account_move_line l "
            "JOIN account_account a ON l.account_id = a.id "
            "WHERE l.partner_id = %s AND l.parent_state = 'posted' "
            "AND l.date < %s AND l.company_id = %s "
            "AND a.account_type IN ('asset_receivable','liability_payable')",
            (partner_id, datos['fecha_desde'], self.env.company.id)
        )
        row = self.env.cr.dictfetchall()
        return row[0]['saldo'] if row else 0

    def lineas(self, datos):
        partner_id = datos['partner_id'][0]
        totales = {'debe': 0, 'haber': 0, 'saldo': 0}

        self.env.cr.execute(
            "SELECT l.id, l.date, l.name, l.ref, "
            "l.debit, l.credit, m.name AS documento, "
            "a.account_type "
            "FROM account_move_line l "
            "JOIN account_account a ON l.account_id = a.id "
            "JOIN account_move m ON l.move_id = m.id "
            "WHERE l.partner_id = %s AND l.parent_state = 'posted' "
            "AND l.date >= %s AND l.date <= %s AND l.company_id = %s "
            "AND a.account_type IN ('asset_receivable','liability_payable') "
            "ORDER BY l.date, m.name",
            (partner_id, datos['fecha_desde'], datos['fecha_hasta'], self.env.company.id)
        )
        rows = self.env.cr.dictfetchall()

        saldo = self.saldo_anterior(datos)
        lineas = []
        for r in rows:
            saldo += r['debit'] - r['credit']
            totales['debe'] += r['debit']
            totales['haber'] += r['credit']
            lineas.append({
                'fecha': r['date'],
                'documento': r['documento'] or '',
                'concepto': r['ref'] or r['name'] or '',
                'debe': r['debit'],
                'haber': r['credit'],
                'saldo': saldo,
            })

        totales['saldo'] = saldo
        return {'lineas': lineas, 'totales': totales}

    @api.model
    def _get_report_values(self, docids, data=None):
        model = self.env.context.get('active_model')
        docs = self.env[model].browse(self.env.context.get('active_ids', []))
        partner = self.env['res.partner'].browse(data['form']['partner_id'][0])
        return {
            'doc_ids': self.ids,
            'doc_model': model,
            'data': data['form'],
            'docs': docs,
            'partner': partner,
            'lineas': self.lineas,
            'saldo_anterior': self.saldo_anterior,
            'current_company_id': self.env.company,
        }
