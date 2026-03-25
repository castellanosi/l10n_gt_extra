# -*- encoding: utf-8 -*-

from odoo import api, models
from odoo.exceptions import UserError


class ReportePequenoContribuyente(models.AbstractModel):
    _name = 'report.l10n_gt_extra.reporte_pequeno'
    _description = 'Libro Compras/Ventas Pequeño Contribuyente'

    def lineas(self, datos):
        totales = {
            'num_facturas': 0,
            'base': 0,
            'cuota': 0,
            'total': 0,
        }

        journal_ids = datos.get('diarios_id', [])
        tipo = datos.get('tipo', 'compra')

        filtro = [
            ('state', 'in', ['posted']),
            ('date', '>=', datos['fecha_desde']),
            ('date', '<=', datos['fecha_hasta']),
        ]
        if journal_ids:
            filtro.append(('journal_id', 'in', journal_ids))

        if tipo == 'compra':
            filtro.append(('move_type', 'in', ['in_invoice', 'in_refund']))
        else:
            filtro.append(('move_type', 'in', ['out_invoice', 'out_refund']))

        facturas = self.env['account.move'].search(filtro)

        # Para pequeño contribuyente: cuota = 5% sobre el total (sin IVA separado)
        tasa_cuota = datos.get('tasa_cuota', 5.0) / 100.0

        lineas = []
        for f in facturas:
            # Filtrar solo pequeños si se pide
            solo_pequenos = datos.get('solo_pequenos', False)
            if solo_pequenos:
                if tipo == 'compra' and not f.partner_id.pequenio_contribuyente:
                    continue
                if tipo == 'venta' and not f.company_id.partner_id.pequenio_contribuyente:
                    continue

            tipo_doc = 'NC' if 'refund' in (f.move_type or '') else 'FACT'
            if hasattr(f, 'nota_debito') and f.nota_debito:
                tipo_doc = 'ND'

            numero = f.ref or f.name or '-'
            if 'firma_fel' in f.fields_get() and f.firma_fel:
                numero = '{}-{}'.format(
                    getattr(f, 'serie_fel', '') or '',
                    getattr(f, 'numero_fel', '') or ''
                )

            # Para pequeño contribuyente: la cuota se aplica sobre el total
            base = f.amount_untaxed
            # Buscar cuota pequeño contribuyente en los impuestos
            cuota = 0
            for linea in f.invoice_line_ids:
                r = linea.tax_ids.compute_all(
                    linea.price_unit * (1 - (linea.discount or 0.0) / 100.0),
                    currency=f.currency_id, quantity=linea.quantity,
                )
                for t in r['taxes']:
                    if 0 < t['amount']:
                        cuota += t['amount']

            totales['num_facturas'] += 1
            totales['base'] += base
            totales['cuota'] += cuota
            totales['total'] += f.amount_total

            lineas.append({
                'fecha': f.invoice_date or f.date,
                'tipo': tipo_doc,
                'numero': numero,
                'partner': f.partner_id.name or '',
                'nit': f.partner_id.vat or 'CF',
                'base': base,
                'cuota': cuota,
                'total': f.amount_total,
                'pequeno': f.partner_id.pequenio_contribuyente,
            })

        lineas = sorted(lineas, key=lambda l: str(l['fecha']) + str(l['numero']))
        return {'lineas': lineas, 'totales': totales}

    @api.model
    def _get_report_values(self, docids, data=None):
        model = self.env.context.get('active_model')
        docs = self.env[model].browse(self.env.context.get('active_ids', []))
        diario = None
        if data['form'].get('diarios_id'):
            diario = self.env['account.journal'].browse(data['form']['diarios_id'][0])
        return {
            'doc_ids': self.ids,
            'doc_model': model,
            'data': data['form'],
            'docs': docs,
            'lineas': self.lineas,
            'direccion_diario': diario.direccion if diario else None,
            'current_company_id': self.env.company,
        }
