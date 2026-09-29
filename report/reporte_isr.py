# -*- encoding: utf-8 -*-

from odoo import api, models
from odoo.exceptions import UserError

from .tipos_dte import campos_tipo_dte, codigo_dte


class ReporteISR(models.AbstractModel):
    _name = 'report.l10n_gt_extra.reporte_isr'
    _description = 'Reporte ISR Retenciones'

    def lineas(self, datos):
        totales = {
            'base': 0,
            'isr': 0,
            'total': 0,
            'num_documentos': 0,
        }

        filtro = [
            ('state', 'in', ['posted']),
            ('date', '>=', datos['fecha_desde']),
            ('date', '<=', datos['fecha_hasta']),
        ]

        tipo_reporte = datos.get('tipo_reporte', 'compra')
        if tipo_reporte == 'compra':
            filtro.append(('move_type', 'in', ['in_invoice', 'in_refund']))
        else:
            filtro.append(('move_type', 'in', ['out_invoice', 'out_refund']))

        impuestos_isr = self.env['account.tax'].browse(datos.get('impuestos_isr_id', []))

        facturas = self.env['account.move'].search(filtro)
        impuestos_ids = set(impuestos_isr.ids)
        campos = self.env['account.move']._fields
        fel_nuevo = all(c in campos for c in ('l10n_gt_fel_uuid', 'l10n_gt_fel_serie', 'l10n_gt_fel_numero'))
        fel_antiguo = 'firma_fel' in campos
        campos_dte = campos_tipo_dte(self.env['account.move'])

        lineas = []
        for f in facturas:
            isr_total = 0
            base_total = 0

            for linea in f.invoice_line_ids:
                r = linea.tax_ids.compute_all(
                    linea.price_unit * (1 - (linea.discount or 0.0) / 100.0),
                    currency=f.currency_id,
                    quantity=linea.quantity,
                    product=linea.product_id,
                    partner=f.partner_id,
                )
                for impuesto in r['taxes']:
                    if impuesto['id'] in impuestos_ids:
                        isr_total += impuesto['amount']
                        base_total += r['total_excluded']

            if isr_total == 0:
                continue

            totales['num_documentos'] += 1
            totales['base'] += base_total
            totales['isr'] += isr_total
            totales['total'] += f.amount_total

            numero = f.ref or f.name or '-'
            if fel_antiguo and f.firma_fel:
                numero = '{}-{}'.format(f.serie_fel, f.numero_fel)
            if fel_nuevo and f.l10n_gt_fel_uuid:
                numero = '%s-%s' % (f.l10n_gt_fel_serie or '', f.l10n_gt_fel_numero or '')
            tipo = 'NC' if 'refund' in (f.move_type or '') else 'FACT'
            tipo = codigo_dte(f, campos_dte) or tipo

            lineas.append({
                'fecha': f.invoice_date or f.date,
                'numero': numero,
                'proveedor': f.partner_id.name or '',
                'nit': f.partner_id.vat or 'CF',
                'base': base_total,
                'isr': isr_total,
                'total': f.amount_total,
                'tipo': tipo,
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
