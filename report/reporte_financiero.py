# -*- encoding: utf-8 -*-

from odoo import api, models

from . import bg_columnas, er_columnas, fe_columnas


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


class ReporteFlujoEfectivo(models.AbstractModel):
    _name = 'report.l10n_gt_extra.reporte_flujo_efectivo'
    _description = 'Estado de Flujo de Efectivo'

    def _cuentas_transitorias(self):
        """Cuentas que Odoo usa como puente del efectivo: recibos y pagos
        pendientes, suspenso de extractos y transferencia de liquidez.
        Se leen de la compañía y de los diarios; cada campo solo si existe."""
        cia = self.env.company
        ids = set()
        for campo in ('transfer_account_id', 'account_journal_suspense_account_id',
                      'account_journal_payment_debit_account_id',
                      'account_journal_payment_credit_account_id'):
            if campo in cia._fields and cia[campo]:
                ids.add(cia[campo].id)
        diarios = self.env['account.journal'].search([
            ('company_id', '=', cia.id), ('type', 'in', ('bank', 'cash', 'credit'))])
        for d in diarios:
            if 'suspense_account_id' in d._fields and d.suspense_account_id:
                ids.add(d.suspense_account_id.id)
            for campo in ('inbound_payment_method_line_ids', 'outbound_payment_method_line_ids'):
                if campo in d._fields:
                    ids.update(d[campo].mapped('payment_account_id').ids)
        return ids

    def _datos_cuentas(self, ids):
        transitorias = self._cuentas_transitorias()
        cuentas = {}
        for c in self.env['account.account'].with_company(self.env.company).browse(list(ids)):
            cuentas[c.id] = {
                'codigo': c.code or '',
                'nombre': c.name or '',
                'account_type': c.account_type,
                'clase': c.l10n_gt_flujo_clase or False,
                'transitoria': c.id in transitorias,
            }
        return cuentas

    def datos(self, datos_form):
        desde = er_columnas.a_fecha(datos_form['fecha_desde'])
        hasta = er_columnas.a_fecha(datos_form['fecha_hasta'])
        modo = datos_form.get('modo') or 'normal'
        cia = self.env.company.id
        cr = self.env.cr

        cr.execute(
            "SELECT l.account_id, date_trunc('month', l.date)::date AS mes, "
            "COALESCE(SUM(l.debit), 0) AS debe, COALESCE(SUM(l.credit), 0) AS haber "
            "FROM account_move_line l "
            "WHERE l.parent_state = 'posted' AND l.company_id = %s "
            "AND l.date >= %s AND l.date <= %s "
            "GROUP BY l.account_id, date_trunc('month', l.date)",
            (cia, desde, hasta),
        )
        movimientos = cr.dictfetchall()

        # Saldos anteriores al rango, para el efectivo al inicio
        cr.execute(
            "SELECT l.account_id, COALESCE(SUM(l.debit - l.credit), 0) AS saldo "
            "FROM account_move_line l "
            "WHERE l.parent_state = 'posted' AND l.company_id = %s AND l.date < %s "
            "GROUP BY l.account_id",
            (cia, desde),
        )
        anteriores = cr.dictfetchall()

        ids = {m['account_id'] for m in movimientos} | {a['account_id'] for a in anteriores}
        cuentas = self._datos_cuentas(ids)
        efectivo_inicial = 0.0
        for a in anteriores:
            cta = cuentas.get(a['account_id'])
            if cta and fe_columnas.clase_cuenta(cta['account_type'], cta['clase'],
                                                cta['transitoria']) == 'efectivo':
                efectivo_inicial += float(a['saldo'] or 0)

        return fe_columnas.construir(cuentas, movimientos, efectivo_inicial, modo, desde, hasta)

    def filas(self, datos_form):
        res = self.datos(datos_form)
        return res, fe_columnas.filas_planas(res, datos_form.get('detalle', True))

    @api.model
    def _get_report_values(self, docids, data=None):
        model = self.env.context.get('active_model')
        docs = self.env[model].browse(self.env.context.get('active_ids', []))
        return {
            'doc_ids': self.ids,
            'doc_model': model,
            'data': data['form'],
            'docs': docs,
            'filas': self.filas,
            'formato': er_columnas.formato,
            'current_company_id': self.env.company,
        }
