# -*- encoding: utf-8 -*-

from odoo import api, models


class ReporteConciliacion(models.AbstractModel):
    _name = 'report.l10n_gt_extra.reporte_conciliacion'
    _description = 'Conciliación Bancaria Cuadrática'

    def _saldo_libro(self, cuenta_id, fecha_hasta):
        """Saldo contable de la cuenta al cierre del período."""
        self.env.cr.execute(
            "SELECT COALESCE(SUM(debit) - SUM(credit), 0) AS saldo "
            "FROM account_move_line "
            "WHERE account_id = %s AND parent_state = 'posted' AND date <= %s",
            (cuenta_id, fecha_hasta)
        )
        row = self.env.cr.dictfetchall()
        return row[0]['saldo'] if row else 0

    def datos(self, datos_form):
        cuenta_id = datos_form['cuenta_id'][0]
        fecha_hasta = datos_form['fecha_hasta']
        saldo_banco = datos_form.get('saldo_banco', 0.0)

        # Movimientos del libro contable SIN conciliar al corte
        self.env.cr.execute(
            "SELECT l.id, l.date, l.debit, l.credit, l.name, l.ref, "
            "m.name AS documento "
            "FROM account_move_line l "
            "JOIN account_move m ON l.move_id = m.id "
            "WHERE l.account_id = %s AND l.parent_state = 'posted' "
            "AND l.date <= %s AND l.reconciled = false "
            "ORDER BY l.date",
            (cuenta_id, fecha_hasta)
        )
        no_conciliados = self.env.cr.dictfetchall()

        depositos_transito = []
        cheques_pendientes = []
        for r in no_conciliados:
            entrada = {
                'fecha': r['date'],
                'documento': r['documento'] or '',
                'concepto': r['ref'] or r['name'] or '',
                'monto': r['debit'] - r['credit'],
            }
            if r['debit'] > r['credit']:
                depositos_transito.append(entrada)
            else:
                entrada['monto'] = abs(entrada['monto'])
                cheques_pendientes.append(entrada)

        total_depositos = sum(d['monto'] for d in depositos_transito)
        total_cheques = sum(c['monto'] for c in cheques_pendientes)

        saldo_libro = self._saldo_libro(cuenta_id, fecha_hasta)

        # Cuadre:
        # Saldo banco + depósitos en tránsito - cheques pendientes = saldo libro
        saldo_ajustado_banco = saldo_banco + total_depositos - total_cheques
        diferencia = saldo_ajustado_banco - saldo_libro

        return {
            'saldo_banco': saldo_banco,
            'depositos_transito': depositos_transito,
            'total_depositos': total_depositos,
            'cheques_pendientes': cheques_pendientes,
            'total_cheques': total_cheques,
            'saldo_ajustado_banco': saldo_ajustado_banco,
            'saldo_libro': saldo_libro,
            'diferencia': diferencia,
        }

    @api.model
    def _get_report_values(self, docids, data=None):
        model = self.env.context.get('active_model')
        docs = self.env[model].browse(self.env.context.get('active_ids', []))
        return {
            'doc_ids': self.ids,
            'doc_model': model,
            'data': data['form'],
            'docs': docs,
            'datos': self.datos,
            'current_company_id': self.env.company,
        }
