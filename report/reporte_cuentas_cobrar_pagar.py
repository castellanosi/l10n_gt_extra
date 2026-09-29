# -*- encoding: utf-8 -*-

import re

from odoo import api, fields, models


def _to_str(val, lang='en_US'):
    """Odoo 18: campos traducibles desde SQL raw retornan dict (JSONB)."""
    if isinstance(val, dict):
        return val.get(lang) or val.get('en_US') or next(iter(val.values()), '')
    return val or ''


# NIT que NO identifican a una persona: nunca se agrupan entre sí.
NIT_NO_AGRUPABLES = ('', 'CF', 'CONSUMIDORFINAL')


def nit_normalizado(nit):
    """'7136301-7', ' 71363017 ' y '71363017' dan la misma llave: '71363017'."""
    return re.sub(r'[^0-9A-Z]', '', (nit or '').upper())


def _a_fecha(valor):
    if not valor:
        return False
    if isinstance(valor, str):
        return fields.Date.from_string(valor)
    return valor


class ReporteCuentasCobrar(models.AbstractModel):
    _name = 'report.l10n_gt_extra.reporte_cuentas_cobrar'
    _description = 'Reporte Consolidado Cuentas por Cobrar'

    def _documentos_abiertos(self, datos, account_type):
        """
        Documentos (líneas de CxC o CxP) con saldo pendiente AL CORTE.

        El saldo de cada documento se calcula a la fecha de corte:
        importe original menos lo conciliado (pagos, notas de crédito)
        con fecha menor o igual al corte. Un pago posterior al corte
        no reduce el saldo. Así funciona también el reporte de
        antigüedad estándar de Odoo.

        Si hay fecha inicial, solo entran documentos con fecha dentro
        del rango.
        """
        corte = _a_fecha(datos['fecha_corte'])
        inicio = _a_fecha(datos.get('fecha_inicio'))
        filtro_inicio = "AND l.date >= %(inicio)s " if inicio else ""
        self.env.cr.execute(
            "SELECT l.id, l.date, l.date_maturity, "
            "p.id AS partner_id, cp.id AS comercial_id, "
            "cp.name AS nombre, COALESCE(NULLIF(cp.vat, ''), p.vat) AS nit, "
            "l.balance "
            "- COALESCE((SELECT SUM(pr.amount) FROM account_partial_reconcile pr "
            "            WHERE pr.debit_move_id = l.id AND pr.max_date <= %(corte)s), 0) "
            "+ COALESCE((SELECT SUM(pr.amount) FROM account_partial_reconcile pr "
            "            WHERE pr.credit_move_id = l.id AND pr.max_date <= %(corte)s), 0) "
            "AS pendiente "
            "FROM account_move_line l "
            "JOIN res_partner p ON l.partner_id = p.id "
            "JOIN res_partner cp ON cp.id = COALESCE(p.commercial_partner_id, p.id) "
            "JOIN account_account a ON l.account_id = a.id "
            "WHERE l.parent_state = 'posted' "
            "AND l.company_id = %(cia)s "
            "AND a.account_type = %(tipo)s "
            "AND l.date <= %(corte)s " + filtro_inicio,
            {'corte': corte, 'inicio': inicio, 'cia': self.env.company.id, 'tipo': account_type},
        )
        return self.env.cr.dictfetchall(), corte

    def _consolidar(self, datos, account_type, signo):
        """
        Agrupa los documentos pendientes por NIT (o por contacto si no hay NIT
        o es CF) y reparte el saldo de CADA documento en su tramo de antigüedad
        según su fecha de vencimiento.

        signo = 1 para CxC (saldo deudor), -1 para CxP (saldo acreedor).
        """
        solo_con_saldo = datos.get('solo_con_saldo', True)
        lang = datos.get('lang', 'en_US')
        documentos, corte = self._documentos_abiertos(datos, account_type)

        grupos = {}
        for d in documentos:
            pendiente = float(d['pendiente'] or 0) * signo
            if abs(pendiente) < 0.005:
                continue
            nit = nit_normalizado(d['nit'])
            llave = ('nit', nit) if nit not in NIT_NO_AGRUPABLES else ('contacto', d['comercial_id'])
            g = grupos.get(llave)
            if not g:
                g = grupos[llave] = {
                    'partner_id': d['comercial_id'],
                    'nombre': _to_str(d['nombre'], lang),
                    'nit': d['nit'] or 'CF',
                    'saldo': 0.0, 'corriente': 0.0,
                    'd30': 0.0, 'd60': 0.0, 'd90': 0.0, 'd90mas': 0.0,
                }
            vence = _a_fecha(d['date_maturity'] or d['date'])
            dias = (corte - vence).days
            if dias <= 0:
                g['corriente'] += pendiente
            elif dias <= 30:
                g['d30'] += pendiente
            elif dias <= 60:
                g['d60'] += pendiente
            elif dias <= 90:
                g['d90'] += pendiente
            else:
                g['d90mas'] += pendiente
            g['saldo'] += pendiente

        lineas = sorted(grupos.values(), key=lambda g: (g['nombre'] or '').lower())
        if solo_con_saldo:
            lineas = [g for g in lineas if abs(g['saldo']) >= 0.01]

        totales = {'saldo': 0, 'corriente': 0, 'd30': 0, 'd60': 0, 'd90': 0, 'd90mas': 0}
        for g in lineas:
            for k in totales:
                totales[k] += g[k]
        return lineas, totales

    def lineas(self, datos):
        """
        Clientes con saldo pendiente al corte, agrupados por NIT, con
        antigüedad por documento: corriente, 1-30, 31-60, 61-90, +90 días.
        """
        lineas, totales = self._consolidar(datos, 'asset_receivable', 1)
        totales['num_clientes'] = len(lineas)
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


class ReporteCuentasPagar(models.AbstractModel):
    _name = 'report.l10n_gt_extra.reporte_cuentas_pagar'
    _description = 'Reporte Consolidado Cuentas por Pagar'

    def lineas(self, datos):
        """
        Proveedores con saldo pendiente al corte, agrupados por NIT, con
        antigüedad por documento: corriente, 1-30, 31-60, 61-90, +90 días.
        """
        cobrar = self.env['report.l10n_gt_extra.reporte_cuentas_cobrar']
        lineas, totales = cobrar._consolidar(datos, 'liability_payable', -1)
        totales['num_proveedores'] = len(lineas)
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
