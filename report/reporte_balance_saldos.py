# -*- encoding: utf-8 -*-

from odoo import api, models, fields


def _to_str(val, lang='en_US'):
    """Odoo 18: campos traducibles desde SQL raw pueden ser dict (JSONB)."""
    if isinstance(val, dict):
        return val.get(lang) or val.get('en_US') or next(iter(val.values()), '')
    return val or ''


class ReporteBalanceSaldos(models.AbstractModel):
    _name = 'report.l10n_gt_extra.reporte_balance_saldos'
    _description = 'Balance de Saldos (Balanza de Comprobación)'

    def _saldo_anterior(self, account_id, fecha_desde):
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
            "SELECT a.id, a.name, "
            "COALESCE(SUM(l.debit),0) AS debe, COALESCE(SUM(l.credit),0) AS haber "
            "FROM account_move_line l "
            "JOIN account_account a ON l.account_id = a.id "
            "WHERE l.parent_state = 'posted' "
            "AND l.date >= %s AND l.date <= %s "
            "AND l.company_id = %s "
            + where_tipo +
            " GROUP BY a.id, a.name",
            (datos['fecha_desde'], datos['fecha_hasta'], self.env.company.id)
        )
        rows = self.env.cr.dictfetchall()

        lang = self.env.lang or 'en_US'
        account_ids = [r['id'] for r in rows]
        cuentas = {a.id: a for a in self.env['account.account'].browse(account_ids)}

        lineas = []
        for r in rows:
            cuenta = cuentas.get(r['id'])
            codigo = cuenta.code if cuenta and hasattr(cuenta, 'code') and cuenta.code else ''
            nombre = _to_str(r['name'], lang)
            saldo_ant = self._saldo_anterior(r['id'], datos['fecha_desde'])
            saldo_final = saldo_ant + r['debe'] - r['haber']
            lineas.append({
                'codigo': codigo,
                'cuenta': nombre,
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

        lineas = sorted(lineas, key=lambda l: l['codigo'] or l['cuenta'])
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
