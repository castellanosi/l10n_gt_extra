# -*- encoding: utf-8 -*-

from odoo import api, models


class ReporteConciliacion(models.AbstractModel):
    _name        = 'report.l10n_gt_extra.reporte_conciliacion'
    _description = 'Conciliación Bancaria'

    def _saldo_libro(self, cuenta_id, fecha_hasta):
        """Saldo contable acumulado de la cuenta bancaria al corte."""
        self.env.cr.execute(
            "SELECT COALESCE(SUM(debit) - SUM(credit), 0) AS saldo "
            "FROM account_move_line "
            "WHERE account_id = %s AND parent_state = 'posted' AND date <= %s",
            (cuenta_id, fecha_hasta)
        )
        row = self.env.cr.dictfetchall()
        return row[0]['saldo'] if row else 0

    def datos(self, datos_form):
        cuenta_id   = datos_form['cuenta_id'][0]
        fecha_hasta = datos_form['fecha_hasta']
        fecha_desde = datos_form.get('fecha_desde') or None
        saldo_banco = float(datos_form.get('saldo_banco') or 0.0)

        # ── Movimientos pendientes de conciliar ────────────────────────
        # En Odoo 18 CE el estado real de conciliación bancaria vive en
        # account_bank_statement_line.is_reconciled.
        # account_move_line.reconciled solo refleja la conciliación de socios
        # (facturas vs pagos) y NO el match del extracto bancario.
        # Para asientos manuales sin BSL usamos l.reconciled como fallback.

        params = [cuenta_id]
        if fecha_desde:
            date_clause = "AND l.date >= %s AND l.date <= %s"
            params += [fecha_desde, fecha_hasta]
        else:
            date_clause = "AND l.date <= %s"
            params += [fecha_hasta]

        self.env.cr.execute(
            """
            SELECT l.id, l.date, l.debit, l.credit,
                   COALESCE(bsl.payment_ref, m.ref, l.ref, l.name, '') AS concepto,
                   m.name AS documento
            FROM  account_move_line l
            JOIN  account_move m
                  ON m.id = l.move_id
            LEFT JOIN account_bank_statement_line bsl
                  ON bsl.move_id = m.id
            WHERE l.account_id   = %s
              AND l.parent_state = 'posted'
              """ + date_clause + """
              AND COALESCE(bsl.is_reconciled, l.reconciled) = FALSE
            ORDER BY l.date
            """,
            params,
        )
        pendientes = self.env.cr.dictfetchall()

        depositos_transito = []
        cheques_pendientes = []
        for r in pendientes:
            entrada = {
                'fecha':     r['date'],
                'documento': r['documento'] or '',
                'concepto':  r['concepto']  or '',
                'monto':     abs(r['debit'] - r['credit']),
            }
            if r['debit'] > r['credit']:
                depositos_transito.append(entrada)
            else:
                cheques_pendientes.append(entrada)

        total_depositos = sum(d['monto'] for d in depositos_transito)
        total_cheques   = sum(c['monto'] for c in cheques_pendientes)
        saldo_libro     = self._saldo_libro(cuenta_id, fecha_hasta)

        # Fórmula cuadrática:
        # Saldo banco + depósitos en tránsito − cheques pendientes = saldo libros
        saldo_ajustado = saldo_banco + total_depositos - total_cheques
        diferencia     = saldo_ajustado - saldo_libro

        return {
            'saldo_banco':          saldo_banco,
            'depositos_transito':   depositos_transito,
            'total_depositos':      total_depositos,
            'cheques_pendientes':   cheques_pendientes,
            'total_cheques':        total_cheques,
            'saldo_ajustado_banco': saldo_ajustado,
            'saldo_libro':          saldo_libro,
            'diferencia':           diferencia,
            'fecha_desde':          fecha_desde,
            'fecha_hasta':          fecha_hasta,
        }

    @api.model
    def _get_report_values(self, docids, data=None):
        model = self.env.context.get('active_model')
        docs  = self.env[model].browse(self.env.context.get('active_ids', []))
        return {
            'doc_ids':            self.ids,
            'doc_model':          model,
            'data':               data['form'],
            'docs':               docs,
            'datos':              self.datos,
            'current_company_id': self.env.company,
        }
