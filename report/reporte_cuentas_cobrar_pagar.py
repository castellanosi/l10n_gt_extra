# -*- encoding: utf-8 -*-

from odoo import api, models


def _to_str(val, lang='en_US'):
    """Odoo 18: campos traducibles desde SQL raw retornan dict (JSONB)."""
    if isinstance(val, dict):
        return val.get(lang) or val.get('en_US') or next(iter(val.values()), '')
    return val or ''


class ReporteCuentasCobrar(models.AbstractModel):
    _name = 'report.l10n_gt_extra.reporte_cuentas_cobrar'
    _description = 'Reporte Consolidado Cuentas por Cobrar'

    def lineas(self, datos):
        """
        Retorna lista consolidada de clientes con saldo acumulado al corte.
        Incluye antigüedad de saldos: corriente, 30, 60, 90, +90 días.
        """
        fecha_corte = datos['fecha_corte']
        solo_con_saldo = datos.get('solo_con_saldo', True)
        lang = datos.get('lang', 'en_US')

        self.env.cr.execute(
            "SELECT p.id, p.name AS nombre, p.vat AS nit, "
            "COALESCE(SUM(l.debit) - SUM(l.credit), 0) AS saldo "
            "FROM account_move_line l "
            "JOIN res_partner p ON l.partner_id = p.id "
            "JOIN account_account a ON l.account_id = a.id "
            "WHERE l.parent_state = 'posted' "
            "AND l.date <= %s "
            "AND l.company_id = %s "
            "AND a.account_type = 'asset_receivable' "
            "GROUP BY p.id, p.name, p.vat "
            "ORDER BY p.name",
            (fecha_corte, self.env.company.id)
        )
        rows = self.env.cr.dictfetchall()

        totales = {
            'saldo': 0, 'corriente': 0,
            'd30': 0, 'd60': 0, 'd90': 0, 'd90mas': 0,
            'num_clientes': 0,
        }

        lineas = []
        for r in rows:
            saldo = float(r['saldo'])
            if solo_con_saldo and abs(saldo) < 0.01:
                continue

            # Calcular antigüedad consultando facturas pendientes del partner
            corriente, d30, d60, d90, d90mas = self._antiguedad(
                r['id'], fecha_corte, 'asset_receivable')

            nombre = _to_str(r['nombre'], lang)
            lineas.append({
                'partner_id': r['id'],
                'nombre': nombre,
                'nit': r['nit'] or 'CF',
                'saldo': saldo,
                'corriente': corriente,
                'd30': d30,
                'd60': d60,
                'd90': d90,
                'd90mas': d90mas,
            })
            totales['saldo'] += saldo
            totales['corriente'] += corriente
            totales['d30'] += d30
            totales['d60'] += d60
            totales['d90'] += d90
            totales['d90mas'] += d90mas
            totales['num_clientes'] += 1

        return {'lineas': lineas, 'totales': totales}

    def _antiguedad(self, partner_id, fecha_corte, account_type):
        """Calcula antigüedad de saldo por tramos de días vencidos."""
        self.env.cr.execute(
            "SELECT l.date_maturity, l.date, "
            "COALESCE(l.debit - l.credit, 0) AS saldo "
            "FROM account_move_line l "
            "JOIN account_account a ON l.account_id = a.id "
            "WHERE l.partner_id = %s AND l.parent_state = 'posted' "
            "AND l.date <= %s AND l.company_id = %s "
            "AND a.account_type = %s "
            "AND (l.debit - l.credit) != 0",
            (partner_id, fecha_corte, self.env.company.id, account_type)
        )
        rows = self.env.cr.dictfetchall()

        from datetime import date
        if isinstance(fecha_corte, str):
            from odoo import fields
            corte = fields.Date.from_string(fecha_corte)
        else:
            corte = fecha_corte

        corriente = d30 = d60 = d90 = d90mas = 0.0
        for r in rows:
            saldo = float(r['saldo'])
            vence = r['date_maturity'] or r['date']
            if isinstance(vence, str):
                from odoo import fields
                vence = fields.Date.from_string(vence)
            dias = (corte - vence).days if vence <= corte else 0

            if dias <= 0:
                corriente += saldo
            elif dias <= 30:
                d30 += saldo
            elif dias <= 60:
                d60 += saldo
            elif dias <= 90:
                d90 += saldo
            else:
                d90mas += saldo

        return corriente, d30, d60, d90, d90mas

    @api.model
    def _get_report_values(self, docids, data=None):
        model = self.env.context.get('active_model')
        docs = self.env[model].browse(self.env.context.get('active_ids', []))
        data['form']['lang'] = self.env.lang or 'en_US'
        return {
            'doc_ids': self.ids,
            'doc_model': model,
            'data': data['form'],
            'docs': docs,
            'lineas': self.lineas,
            'current_company_id': self.env.company,
        }


class ReporteCuentasPagar(models.AbstractModel):
    _name = 'report.l10n_gt_extra.reporte_cuentas_pagar'
    _description = 'Reporte Consolidado Cuentas por Pagar'

    def lineas(self, datos):
        """
        Retorna lista consolidada de proveedores con saldo acumulado al corte.
        Incluye antigüedad de saldos: corriente, 30, 60, 90, +90 días.
        """
        fecha_corte = datos['fecha_corte']
        solo_con_saldo = datos.get('solo_con_saldo', True)
        lang = datos.get('lang', 'en_US')

        self.env.cr.execute(
            "SELECT p.id, p.name AS nombre, p.vat AS nit, "
            "COALESCE(SUM(l.credit) - SUM(l.debit), 0) AS saldo "
            "FROM account_move_line l "
            "JOIN res_partner p ON l.partner_id = p.id "
            "JOIN account_account a ON l.account_id = a.id "
            "WHERE l.parent_state = 'posted' "
            "AND l.date <= %s "
            "AND l.company_id = %s "
            "AND a.account_type = 'liability_payable' "
            "GROUP BY p.id, p.name, p.vat "
            "ORDER BY p.name",
            (fecha_corte, self.env.company.id)
        )
        rows = self.env.cr.dictfetchall()

        cobrar_report = self.env['report.l10n_gt_extra.reporte_cuentas_cobrar']

        totales = {
            'saldo': 0, 'corriente': 0,
            'd30': 0, 'd60': 0, 'd90': 0, 'd90mas': 0,
            'num_proveedores': 0,
        }

        lineas = []
        for r in rows:
            saldo = float(r['saldo'])
            if solo_con_saldo and abs(saldo) < 0.01:
                continue

            corriente, d30, d60, d90, d90mas = cobrar_report._antiguedad(
                r['id'], fecha_corte, 'liability_payable')
            # Para cuentas por pagar, el saldo es acreedor (positivo = deuda)
            corriente = abs(corriente)
            d30 = abs(d30)
            d60 = abs(d60)
            d90 = abs(d90)
            d90mas = abs(d90mas)

            nombre = _to_str(r['nombre'], lang)
            lineas.append({
                'partner_id': r['id'],
                'nombre': nombre,
                'nit': r['nit'] or 'CF',
                'saldo': saldo,
                'corriente': corriente,
                'd30': d30,
                'd60': d60,
                'd90': d90,
                'd90mas': d90mas,
            })
            totales['saldo'] += saldo
            totales['corriente'] += corriente
            totales['d30'] += d30
            totales['d60'] += d60
            totales['d90'] += d90
            totales['d90mas'] += d90mas
            totales['num_proveedores'] += 1

        return {'lineas': lineas, 'totales': totales}

    @api.model
    def _get_report_values(self, docids, data=None):
        model = self.env.context.get('active_model')
        docs = self.env[model].browse(self.env.context.get('active_ids', []))
        data['form']['lang'] = self.env.lang or 'en_US'
        return {
            'doc_ids': self.ids,
            'doc_model': model,
            'data': data['form'],
            'docs': docs,
            'lineas': self.lineas,
            'current_company_id': self.env.company,
        }
