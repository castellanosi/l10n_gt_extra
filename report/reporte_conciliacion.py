# -*- encoding: utf-8 -*-

from odoo import api, models

from . import conciliacion_logica, er_columnas


class ReporteConciliacion(models.AbstractModel):
    _name = 'report.l10n_gt_extra.reporte_conciliacion'
    _description = 'Conciliación Bancaria'

    def _saldo_libro(self, cuenta_id, fecha_hasta):
        """Saldo contable de la cuenta bancaria al corte, de la compañía activa."""
        self.env.cr.execute(
            "SELECT COALESCE(SUM(debit) - SUM(credit), 0) AS saldo "
            "FROM account_move_line "
            "WHERE account_id = %s AND company_id = %s "
            "AND parent_state = 'posted' AND date <= %s",
            (cuenta_id, self.env.company.id, fecha_hasta),
        )
        row = self.env.cr.dictfetchall()
        return row[0]['saldo'] if row else 0

    def _en_transito(self, cuenta_id, fecha_hasta):
        """Líneas marcadas «En tránsito» hasta el corte (pocas: solo las
        marcadas). La regla de pendiente se aplica en conciliacion_logica,
        sin filtro de fecha inicial: un cheque de meses anteriores aún no
        cobrado debe seguir apareciendo."""
        self.env.cr.execute(
            """
            SELECT l.date, l.debit, l.credit, l.l10n_gt_en_transito AS en_transito,
                   l.l10n_gt_fecha_cobro AS fecha_cobro,
                   m.name AS documento,
                   COALESCE(NULLIF(m.ref, ''), NULLIF(l.name, ''), '') AS concepto
            FROM account_move_line l
            JOIN account_move m ON m.id = l.move_id
            WHERE l.account_id = %s AND l.company_id = %s
              AND l.parent_state = 'posted' AND l.date <= %s
              AND l.l10n_gt_en_transito
            """,
            (cuenta_id, self.env.company.id, fecha_hasta),
        )
        return self.env.cr.dictfetchall()

    def datos(self, datos_form):
        cuenta_id = datos_form['cuenta_id'][0]
        fecha_hasta = datos_form['fecha_hasta']
        lineas = self._en_transito(cuenta_id, fecha_hasta)
        return conciliacion_logica.construir(
            lineas, self._saldo_libro(cuenta_id, fecha_hasta),
            datos_form.get('saldo_banco'), fecha_hasta)

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
            'formato': er_columnas.formato,
            'current_company_id': self.env.company,
        }
