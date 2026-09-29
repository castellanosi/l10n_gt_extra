# -*- encoding: utf-8 -*-

from odoo import api, models, fields
from odoo.release import version_info
import logging

from .detalle_comun import lineas_contables

class ReporteMayor(models.AbstractModel):
    _name = 'report.l10n_gt_extra.reporte_mayor'
    _description = 'Libro de Mayor'

    def retornar_saldo_inicial_todos_anios(self, cuenta, fecha_desde):
        saldo_inicial = 0
        self.env.cr.execute('select a.id, sum(l.debit) as debe, sum(l.credit) as haber '\
        'from account_move_line l join account_account a on(l.account_id = a.id)'\
        'where l.parent_state = \'posted\' and a.id = %s and l.date < %s group by a.id, l.debit, l.credit', (cuenta, fecha_desde))
        for m in self.env.cr.dictfetchall():
            saldo_inicial += m['debe'] - m['haber']
        return saldo_inicial

    def retornar_saldo_inicial_inicio_anio(self, cuenta, fecha_desde):
        saldo_inicial = 0
        fecha = fields.Date.from_string(fecha_desde)
        self.env.cr.execute('select a.id, sum(l.debit) as debe, sum(l.credit) as haber '\
        'from account_move_line l join account_account a on(l.account_id = a.id)'\
        'where l.parent_state = \'posted\' and a.id = %s and l.date < %s and l.date >= %s group by a.id,l.debit,l.credit', (cuenta, fecha_desde, fecha.strftime('%Y-1-1')))
        for m in self.env.cr.dictfetchall():
            saldo_inicial += m['debe'] - m['haber']
        return saldo_inicial

    def lineas_detalladas(self, datos):
        """Por cuenta: saldo inicial, cada movimiento con su saldo acumulado y saldo final."""
        cuentas = {}
        totales = {'debe': 0, 'haber': 0, 'saldo_inicial': 0, 'saldo_final': 0}
        for l in lineas_contables(self.env, datos):
            c = cuentas.get(l['cuenta_id'])
            if not c:
                cuenta = self.env['account.account'].browse(l['cuenta_id'])
                if cuenta.include_initial_balance:
                    saldo_ini = self.retornar_saldo_inicial_todos_anios(cuenta.id, datos['fecha_desde'])
                else:
                    saldo_ini = self.retornar_saldo_inicial_inicio_anio(cuenta.id, datos['fecha_desde'])
                c = cuentas[l['cuenta_id']] = {
                    'codigo': l['codigo'], 'cuenta': l['cuenta'],
                    'saldo_inicial': saldo_ini, 'saldo': saldo_ini,
                    'movimientos': [], 'total_debe': 0, 'total_haber': 0, 'saldo_final': saldo_ini,
                }
            c['saldo'] += l['debe'] - l['haber']
            l['saldo'] = c['saldo']
            c['movimientos'].append(l)
            c['total_debe'] += l['debe']
            c['total_haber'] += l['haber']
            c['saldo_final'] = c['saldo']
        lineas = sorted(cuentas.values(), key=lambda c: c['codigo'] or '')
        for c in lineas:
            totales['debe'] += c['total_debe']
            totales['haber'] += c['total_haber']
            totales['saldo_inicial'] += c['saldo_inicial']
            totales['saldo_final'] += c['saldo_final']
        return {'lineas': lineas, 'totales': totales}

    def lineas(self, datos):
        if datos.get('modo') == 'detallado':
            return self.lineas_detalladas(datos)
        totales = {}
        lineas_resumidas = {}
        lineas=[]
        totales['debe'] = 0
        totales['haber'] = 0
        totales['saldo_inicial'] = 0
        totales['saldo_final'] = 0

        account_ids = [x for x in datos['cuentas_id']]
        accounts_str = ','.join([str(x) for x in datos['cuentas_id']])
        
        if datos['agrupado_por_dia']:
            
            self.env.cr.execute('select a.id, l.date as fecha, sum(l.debit) as debe, sum(l.credit) as haber ' \
                'from account_move_line l join account_account a on(l.account_id = a.id)' \
                'where l.parent_state = \'posted\' and a.id in ('+accounts_str+') and l.date >= %s and l.date <= %s group by a.id, l.date order by l.date',
            (datos['fecha_desde'], datos['fecha_hasta']))

            for r in self.env.cr.dictfetchall():
                cuenta = self.env['account.account'].browse(r['id'])

                totales['debe'] += r['debe']
                totales['haber'] += r['haber']
                linea = {
                    'id': r['id'],
                    'fecha': r['fecha'],
                    'codigo': cuenta.code,
                    'cuenta': cuenta.name,
                    'saldo_inicial': 0,
                    'debe': r['debe'],
                    'haber': r['haber'],
                    'saldo_final': 0,
                    'balance_inicial': cuenta.include_initial_balance
                }
                lineas.append(linea)

            lineas.sort(key=lambda l: (l['fecha'], l['codigo']))

            cuentas_agrupadas = {}
            llave = 'codigo'
            for l in lineas:
                if l[llave] not in cuentas_agrupadas:
                    cuentas_agrupadas[l[llave]] = {
                        'codigo': l[llave],
                        'cuenta': l['cuenta'],
                        'saldo_inicial': 0,
                        'saldo_final': 0,
                        'fechas': [],
                        'total_debe': 0,
                        'total_haber': 0
                    }

                    if not l['balance_inicial']:
                        cuentas_agrupadas[l[llave]]['saldo_inicial'] = self.retornar_saldo_inicial_inicio_anio(l['id'], datos['fecha_desde'])
                    else:
                        cuentas_agrupadas[l[llave]]['saldo_inicial'] = saldo = self.retornar_saldo_inicial_todos_anios(l['id'], datos['fecha_desde'])
                cuentas_agrupadas[l[llave]]['fechas'].append(l)

            for cuenta in cuentas_agrupadas.values():
                for fecha in cuenta['fechas']:
                    cuenta['total_debe'] += fecha['debe']
                    cuenta['total_haber'] += fecha['haber']
                cuenta['saldo_final'] += cuenta['saldo_inicial'] + cuenta['total_debe'] - cuenta['total_haber']

            lineas = sorted(cuentas_agrupadas.values(), key=lambda l: l['codigo'])
        else:

            self.env.cr.execute('select a.id, sum(l.debit) as debe, sum(l.credit) as haber ' \
            	'from account_move_line l join account_account a on(l.account_id = a.id)' \
            	'where l.parent_state = \'posted\' and a.id in ('+accounts_str+') and l.date >= %s and l.date <= %s group by a.id',
            (datos['fecha_desde'], datos['fecha_hasta']))

            for r in self.env.cr.dictfetchall():
                cuenta = self.env['account.account'].browse(r['id'])

                totales['debe'] += r['debe']
                totales['haber'] += r['haber']
                linea = {
                    'id': r['id'],
                    'codigo': cuenta.code,
                    'cuenta': cuenta.name,
                    'saldo_inicial': 0,
                    'debe': r['debe'],
                    'haber': r['haber'],
                    'saldo_final': 0,
                    'balance_inicial': cuenta.include_initial_balance
                }
                lineas.append(linea)

                lineas.sort(key=lambda l: l['codigo'])

            for l in lineas:
                if not l['balance_inicial']:
                    l['saldo_inicial'] += self.retornar_saldo_inicial_inicio_anio(l['id'], datos['fecha_desde'])
                    l['saldo_final'] += l['saldo_inicial'] + l['debe'] - l['haber']
                    totales['saldo_inicial'] += l['saldo_inicial']
                    totales['saldo_final'] += l['saldo_final']
                else:
                    l['saldo_inicial'] += self.retornar_saldo_inicial_todos_anios(l['id'], datos['fecha_desde'])
                    l['saldo_final'] += l['saldo_inicial'] + l['debe'] - l['haber']
                    totales['saldo_inicial'] += l['saldo_inicial']
                    totales['saldo_final'] += l['saldo_final']

        return {'lineas': lineas,'totales': totales }

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

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: