# -*- encoding: utf-8 -*-

from odoo import api, models, fields


class ReporteEstadoResultados(models.AbstractModel):
    _name = 'report.l10n_gt_extra.reporte_estado_resultados'
    _description = 'Estado de Resultados'

    TIPOS_INGRESOS = ['income', 'income_other']
    TIPOS_COSTOS = ['expense_direct_cost']
    TIPOS_GASTOS = ['expense', 'expense_depreciation']

    def _movimientos_cuentas(self, tipos, fecha_desde, fecha_hasta):
        tipos_str = ','.join(["'{}'".format(t) for t in tipos])
        # ✅ Odoo 18: sin a.code en SQL — se obtiene via ORM después
        self.env.cr.execute(
            "SELECT a.id, a.name, a.account_type, "
            "COALESCE(SUM(l.debit),0) AS debe, COALESCE(SUM(l.credit),0) AS haber "
            "FROM account_move_line l "
            "JOIN account_account a ON l.account_id = a.id "
            "WHERE l.parent_state = 'posted' "
            "AND l.date >= %s AND l.date <= %s "
            "AND l.company_id = %s "
            "AND a.account_type IN (" + tipos_str + ") "
            "GROUP BY a.id, a.name, a.account_type",
            (fecha_desde, fecha_hasta, self.env.company.id)
        )
        rows = self.env.cr.dictfetchall()

        account_ids = [r['id'] for r in rows]
        cuentas = {a.id: a for a in self.env['account.account'].browse(account_ids)}

        lineas = []
        total = 0
        for r in rows:
            cuenta = cuentas.get(r['id'])
            codigo = cuenta.code if cuenta and hasattr(cuenta, 'code') and cuenta.code else ''
            if r['account_type'] in self.TIPOS_INGRESOS:
                saldo = r['haber'] - r['debe']
            else:
                saldo = r['debe'] - r['haber']
            total += saldo
            lineas.append({'codigo': codigo, 'nombre': r['name'], 'saldo': saldo})

        lineas = sorted(lineas, key=lambda l: l['codigo'] or l['nombre'])
        return lineas, total

    def datos(self, datos_form):
        fecha_desde = datos_form['fecha_desde']
        fecha_hasta = datos_form['fecha_hasta']

        ingresos, total_ingresos = self._movimientos_cuentas(
            self.TIPOS_INGRESOS, fecha_desde, fecha_hasta)
        costos, total_costos = self._movimientos_cuentas(
            self.TIPOS_COSTOS, fecha_desde, fecha_hasta)
        gastos, total_gastos = self._movimientos_cuentas(
            self.TIPOS_GASTOS, fecha_desde, fecha_hasta)

        utilidad_bruta = total_ingresos - total_costos
        utilidad_neta = utilidad_bruta - total_gastos

        return {
            'ingresos': ingresos,
            'total_ingresos': total_ingresos,
            'costos': costos,
            'total_costos': total_costos,
            'gastos': gastos,
            'total_gastos': total_gastos,
            'utilidad_bruta': utilidad_bruta,
            'utilidad_neta': utilidad_neta,
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


class ReporteBalanceGeneral(models.AbstractModel):
    _name = 'report.l10n_gt_extra.reporte_balance_general'
    _description = 'Balance General'

    TIPOS_ACTIVO = [
        'asset_receivable', 'asset_cash', 'asset_current',
        'asset_non_current', 'asset_prepayments', 'asset_fixed',
    ]
    TIPOS_PASIVO = [
        'liability_payable', 'liability_credit_card',
        'liability_current', 'liability_non_current',
    ]
    TIPOS_CAPITAL = ['equity', 'equity_unaffected']

    def _saldo_cuenta(self, account_id, fecha_hasta):
        self.env.cr.execute(
            "SELECT COALESCE(SUM(debit) - SUM(credit), 0) AS saldo "
            "FROM account_move_line "
            "WHERE account_id = %s AND parent_state = 'posted' AND date <= %s",
            (account_id, fecha_hasta)
        )
        row = self.env.cr.dictfetchall()
        return row[0]['saldo'] if row else 0

    def _cuentas_con_saldo(self, tipos, fecha_hasta):
        tipos_str = ','.join(["'{}'".format(t) for t in tipos])
        # ✅ Odoo 18: sin a.code en SQL
        self.env.cr.execute(
            "SELECT DISTINCT a.id, a.name, a.account_type "
            "FROM account_move_line l "
            "JOIN account_account a ON l.account_id = a.id "
            "WHERE l.parent_state = 'posted' AND l.date <= %s "
            "AND l.company_id = %s "
            "AND a.account_type IN (" + tipos_str + ")",
            (fecha_hasta, self.env.company.id)
        )
        rows = self.env.cr.dictfetchall()

        account_ids = [r['id'] for r in rows]
        cuentas = {a.id: a for a in self.env['account.account'].browse(account_ids)}

        lineas = []
        total = 0
        for r in rows:
            cuenta = cuentas.get(r['id'])
            codigo = cuenta.code if cuenta and hasattr(cuenta, 'code') and cuenta.code else ''
            saldo_raw = self._saldo_cuenta(r['id'], fecha_hasta)
            saldo = saldo_raw if r['account_type'] in self.TIPOS_ACTIVO else -saldo_raw
            if saldo != 0:
                lineas.append({'codigo': codigo, 'nombre': r['name'], 'saldo': saldo})
                total += saldo

        lineas = sorted(lineas, key=lambda l: l['codigo'] or l['nombre'])
        return lineas, total

    def datos(self, datos_form):
        fecha_hasta = datos_form['fecha_hasta']

        activos, total_activo = self._cuentas_con_saldo(self.TIPOS_ACTIVO, fecha_hasta)
        pasivos, total_pasivo = self._cuentas_con_saldo(self.TIPOS_PASIVO, fecha_hasta)
        capital, total_capital = self._cuentas_con_saldo(self.TIPOS_CAPITAL, fecha_hasta)

        er = self.env['report.l10n_gt_extra.reporte_estado_resultados']
        er_datos = er.datos({
            'fecha_desde': datos_form.get('fecha_desde_er',
                                          datos_form['fecha_hasta'][:4] + '-01-01'),
            'fecha_hasta': fecha_hasta,
        })
        utilidad_periodo = er_datos['utilidad_neta']
        total_capital_mas_utilidad = total_capital + utilidad_periodo

        return {
            'activos': activos,
            'total_activo': total_activo,
            'pasivos': pasivos,
            'total_pasivo': total_pasivo,
            'capital': capital,
            'total_capital': total_capital,
            'utilidad_periodo': utilidad_periodo,
            'total_capital_mas_utilidad': total_capital_mas_utilidad,
            'total_pasivo_capital': total_pasivo + total_capital_mas_utilidad,
            'cuadre': total_activo - (total_pasivo + total_capital_mas_utilidad),
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
