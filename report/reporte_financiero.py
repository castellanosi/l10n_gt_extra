# -*- encoding: utf-8 -*-

from odoo import api, models

from . import bg_columnas, er_columnas


class ReporteEstadoResultados(models.AbstractModel):
    _name = 'report.l10n_gt_extra.reporte_estado_resultados'
    _description = 'Estado de Resultados'

    def _movimientos(self, fecha_desde, fecha_hasta):
        """Debe y haber por cuenta de resultados y por mes, en el rango."""
        self.env.cr.execute(
            "SELECT l.account_id, date_trunc('month', l.date)::date AS mes, "
            "COALESCE(SUM(l.debit), 0) AS debe, COALESCE(SUM(l.credit), 0) AS haber "
            "FROM account_move_line l "
            "JOIN account_account a ON l.account_id = a.id "
            "WHERE l.parent_state = 'posted' "
            "AND l.date >= %s AND l.date <= %s "
            "AND l.company_id = %s "
            "AND a.account_type IN %s "
            "GROUP BY l.account_id, date_trunc('month', l.date)",
            (fecha_desde, fecha_hasta, self.env.company.id, er_columnas.TIPOS_RESULTADOS),
        )
        movimientos = self.env.cr.dictfetchall()
        ids = list({m['account_id'] for m in movimientos})
        cuentas = {}
        for c in self.env['account.account'].with_company(self.env.company).browse(ids):
            cuentas[c.id] = {
                'codigo': c.code or '',
                'nombre': c.name or '',
                'account_type': c.account_type,
            }
        return cuentas, movimientos

    def datos(self, datos_form):
        fecha_desde = er_columnas.a_fecha(datos_form['fecha_desde'])
        fecha_hasta = er_columnas.a_fecha(datos_form['fecha_hasta'])
        modo = datos_form.get('modo') or 'normal'
        cuentas, movimientos = self._movimientos(fecha_desde, fecha_hasta)
        return er_columnas.construir(cuentas, movimientos, modo, fecha_desde, fecha_hasta)

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
            'celdas': er_columnas.celdas,
            'formato': er_columnas.formato,
            'current_company_id': self.env.company,
        }


class ReporteBalanceGeneral(models.AbstractModel):
    _name = 'report.l10n_gt_extra.reporte_balance_general'
    _description = 'Balance General'

    def _movimientos(self, fecha_hasta):
        """Debe y haber por cuenta de balance y por mes, hasta el corte."""
        self.env.cr.execute(
            "SELECT l.account_id, date_trunc('month', l.date)::date AS fecha, "
            "COALESCE(SUM(l.debit), 0) AS debe, COALESCE(SUM(l.credit), 0) AS haber "
            "FROM account_move_line l "
            "JOIN account_account a ON l.account_id = a.id "
            "WHERE l.parent_state = 'posted' AND l.date <= %s "
            "AND l.company_id = %s "
            "AND a.account_type IN %s "
            "GROUP BY l.account_id, date_trunc('month', l.date)",
            (fecha_hasta, self.env.company.id, bg_columnas.TIPOS_BALANCE),
        )
        movimientos = self.env.cr.dictfetchall()
        ids = list({m['account_id'] for m in movimientos})
        cuentas = {}
        for c in self.env['account.account'].with_company(self.env.company).browse(ids):
            cuentas[c.id] = {
                'codigo': c.code or '',
                'nombre': c.name or '',
                'account_type': c.account_type,
            }
        return cuentas, movimientos

    def datos(self, datos_form):
        fecha_hasta = er_columnas.a_fecha(datos_form['fecha_hasta'])
        fecha_desde_er = er_columnas.a_fecha(
            datos_form.get('fecha_desde_er') or fecha_hasta.replace(month=1, day=1))
        modo = datos_form.get('modo') or 'normal'

        er = self.env['report.l10n_gt_extra.reporte_estado_resultados']
        er_res = er.datos({'fecha_desde': fecha_desde_er, 'fecha_hasta': fecha_hasta,
                           'modo': modo})
        utilidades = bg_columnas.utilidades_por_columna(modo, er_res)

        cuentas, movimientos = self._movimientos(fecha_hasta)
        return bg_columnas.construir(cuentas, movimientos, utilidades, modo,
                                     fecha_desde_er, fecha_hasta)

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
            'celdas': er_columnas.celdas,
            'formato': er_columnas.formato,
            'current_company_id': self.env.company,
        }
