# -*- encoding: utf-8 -*-

from odoo import api, models, fields


class ReporteBalanceSaldos(models.AbstractModel):
    _name = 'report.l10n_gt_extra.reporte_balance_saldos'
    _description = 'Balance de Saldos (Balanza de Comprobación)'

    def _saldo_anterior(self, account_id, fecha_desde):
        """Saldo acumulado antes de fecha_desde."""
        cuenta = self.env['account.account'].browse(account_id)
        if not cuenta.include_initial_balance:
            fecha = fields.Date.from_string(fecha_desde)
            inicio_anio = fecha.strftime('%Y-01-01')
            self.env.cr.execute(
                "SELECT COALESCE(SUM(debit) - SUM(credit), 0) AS saldo "
                "FROM account_move_line "
                "WHERE account_id = %s AND parent_state = 'posted' "
                "AND date >= %s AND date < %s",
                (account_id, inicio_anio, fecha_desde)
            )
        else:
            self.env.cr.execute(
                "SELECT COALESCE(SUM(debit) - SUM(credit), 0) AS saldo "
                "FROM account_move_line "
                "WHERE account_id = %s AND parent_state = 'posted' AND date < %s",
                (account_id, fecha_desde)
            )
        row = self.env.cr.dictfetchall()
        return row[0]['saldo'] if row else 0

    def lineas(self, datos):
        totales = {
            'saldo_anterior': 0, 'debe': 0, 'haber': 0,
            'saldo_deudor': 0, 'saldo_acreedor': 0,
        }

        # Obtener cuentas con movimientos en el período
        filtro_tipo = datos.get('filtro_tipo', 'todas')
        tipos_mapa = {
            'balance': ['asset_receivable', 'asset_cash', 'asset_current', 'asset_non_current',
                        'asset_prepayments', 'asset_fixed', 'liability_payable',
                        'liability_credit_card', 'liability_current', 'liability_non_current',
                        'equity', 'equity_unaffected'],
            'resultados': ['income', 'income_other', 'expense', 'expense_depreciation',
                           'expense_direct_cost'],
        }

        where_tipo = ''
        if filtro_tipo in tipos_mapa:
            tipos_str = ','.join(["'{}'".format(t) for t in tipos_mapa[filtro_tipo]])
            where_tipo = "AND a.account_type IN ({})".format(tipos_str)

        self.env.cr.execute(
            "SELECT a.id, a.code, a.name, "
            "COALESCE(SUM(l.debit),0) AS debe, COALESCE(SUM(l.credit),0) AS haber "
            "FROM account_move_line l "
            "JOIN account_account a ON l.account_id = a.id "
            "WHERE l.parent_state = 'posted' "
            "AND l.date >= %s AND l.date <= %s "
            "AND l.company_id = %s "
            + where_tipo +
            " GROUP BY a.id, a.code, a.name ORDER BY a.code",
            (datos['fecha_desde'], datos['fecha_hasta'], self.env.company.id)
        )
        rows = self.env.cr.dictfetchall()

        lineas = []
        for r in rows:
            saldo_ant = self._saldo_anterior(r['id'], datos['fecha_desde'])
            saldo_final = saldo_ant + r['debe'] - r['haber']
            lineas.append({
                'codigo': r['code'],
                'cuenta': r['name'],
                'saldo_anterior': saldo_ant,
                'debe': r['debe'],
                'haber': r['haber'],
                'saldo_deudor': saldo_final if saldo_final > 0 else 0,
                'saldo_acreedor': -saldo_final if saldo_final < 0 else 0,
            })
            totales['saldo_anterior'] += saldo_ant
            totales['debe'] += r['debe']
            totales['haber'] += r['haber']
            totales['saldo_deudor'] += saldo_final if saldo_final > 0 else 0
            totales['saldo_acreedor'] += -saldo_final if saldo_final < 0 else 0

        return {'lineas': lineas, 'totales': totales}

    @api.model
    def _get_report_values(self, docids, data=None):
        model = self.env.context.get('active_model')
        docs = self.env[model].browse(self.env.context.get('active_ids', []))
        return {
            'doc_ids': self.ids,
            'doc_model': model,
            'data': data['form'],
            'docs': docs,
            'lineas': self.lineas,
            'current_company_id': self.env.company,
        }
