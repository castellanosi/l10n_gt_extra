# -*- encoding: utf-8 -*-

from odoo import api, models
from odoo.exceptions import UserError


class ReporteFEL(models.AbstractModel):
    _name = 'report.l10n_gt_extra.reporte_fel'
    _description = 'Reporte Facturas Especiales / FEL'

    def lineas(self, datos):
        totales = {'base': 0, 'iva': 0, 'isr': 0, 'total': 0, 'num_facturas': 0}

        journal_ids = datos.get('diarios_id', [])
        filtro = [
            ('state', 'in', ['posted']),
            ('date', '>=', datos['fecha_desde']),
            ('date', '<=', datos['fecha_hasta']),
        ]
        if journal_ids:
            filtro.append(('journal_id', 'in', journal_ids))

        tipo = datos.get('tipo', 'compra')
        if tipo == 'compra':
            filtro.append(('move_type', 'in', ['in_invoice', 'in_refund']))
        else:
            filtro.append(('move_type', 'in', ['out_invoice', 'out_refund']))

        facturas = self.env['account.move'].search(filtro)
        campos = facturas.fields_get()

        lineas = []
        for f in facturas:
            # Filtrar solo facturas con datos FEL o marcadas como especiales
            tiene_fel = ('firma_fel' in campos and f.firma_fel) or \
                        ('firma_gface' in campos and f.firma_gface)
            solo_fel = datos.get('solo_fel', False)
            if solo_fel and not tiene_fel:
                continue

            serie = ''
            numero = ''
            uuid = ''
            if 'firma_fel' in campos and f.firma_fel:
                serie = getattr(f, 'serie_fel', '') or ''
                numero = getattr(f, 'numero_fel', '') or ''
                uuid = str(f.firma_fel)
            elif 'firma_gface' in campos and f.firma_gface:
                uuid = str(f.firma_gface)
                numero = f.ref or f.name or ''
            else:
                numero = f.ref or f.name or ''

            # Calcular base e IVA sumando líneas
            base = sum(l.price_subtotal for l in f.invoice_line_ids)
            iva = f.amount_tax
            isr = 0
            for linea in f.invoice_line_ids:
                r = linea.tax_ids.compute_all(
                    linea.price_unit * (1 - (linea.discount or 0.0) / 100.0),
                    currency=f.currency_id, quantity=linea.quantity,
                )
                for t in r['taxes']:
                    if t['amount'] < 0:
                        isr += abs(t['amount'])

            totales['num_facturas'] += 1
            totales['base'] += base
            totales['iva'] += iva
            totales['isr'] += isr
            totales['total'] += f.amount_total

            lineas.append({
                'fecha': f.invoice_date or f.date,
                'serie': serie,
                'numero': numero,
                'uuid': uuid[:36] if uuid else '',
                'partner': f.partner_id.name or '',
                'nit': f.partner_id.vat or 'CF',
                'base': base,
                'iva': iva,
                'isr': isr,
                'total': f.amount_total,
                'tipo': 'NC' if 'refund' in (f.move_type or '') else 'FACT',
                'tiene_fel': tiene_fel,
            })

        lineas = sorted(lineas, key=lambda l: str(l['fecha']) + str(l['numero']))
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
