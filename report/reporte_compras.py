# -*- encoding: utf-8 -*-

from odoo import api, models
from odoo.exceptions import UserError
import logging

from .tipos_dte import (
    afiliacion_emisor,
    campo_afiliacion,
    campos_tipo_dte,
    codigo_dte,
    columna_linea,
    es_pequenio,
    sin_credito_fiscal,
)
from .libro_montos import (
    CERO,
    COLUMNAS_COMPRAS,
    a_float_fila,
    a_float_totales,
    acumular_totales,
    aplicar_dte,
    dec,
    fila_vacia,
    monto_dte,
    redondear_fila,
    tipo_cambio_documento,
    totales_vacios,
)
from .libro_control import control_libro, mensajes_control


# El libro de compras va por la fecha de la factura (fecha del DTE), no por la
# fecha contable: una factura del 30/10 contabilizada el 31/10 sale el 30/10.
CAMPO_FECHA_LIBRO_COMPRAS = 'invoice_date'

class ReporteCompras(models.AbstractModel):
    _name = 'report.l10n_gt_extra.reporte_compras'
    _description = 'Libro de Compras'

    def lineas(self, datos):
        columnas = COLUMNAS_COMPRAS
        totales = totales_vacios(columnas)

        journal_ids = [x for x in datos['diarios_id']]
        filtro = [
            ('state','in',['posted','cancel']),
            ('journal_id','in',journal_ids),
            # Fecha del documento (fecha de la factura), no la contable (5.62)
            (CAMPO_FECHA_LIBRO_COMPRAS,'<=',datos['fecha_hasta']),
            (CAMPO_FECHA_LIBRO_COMPRAS,'>=',datos['fecha_desde']),
            ('amount_total','!=',0),
        ]
        
        # Campos opcionales: se revisan UNA vez (antes se llamaba fields_get() por factura)
        campos_move = self.env['account.move']._fields
        tiene_type = 'type' in campos_move
        tiene_fel_antiguo = 'firma_fel' in campos_move
        tiene_fel_nuevo = 'l10n_gt_fel_uuid' in campos_move and 'l10n_gt_fel_serie' in campos_move and 'l10n_gt_fel_numero' in campos_move
        campos_dte = campos_tipo_dte(self.env['account.move'])
        campo_afil = campo_afiliacion(self.env['account.move'])
        # Régimen de la empresa QUE COMPRA en el periodo del libro. Viene del
        # asistente (por defecto el de la compañía) para poder reimprimir un
        # periodo anterior a un cambio de régimen. Sin dato: GEN (como antes).
        regimen_comprador = datos.get('regimen_comprador') or 'GEN'
        tiene_fel_state = 'l10n_gt_fel_state' in campos_move
        # gt_bien_servicio (gt_xml_importer): B/S en líneas sin producto de un DTE mezclado
        tiene_bien_servicio = 'gt_bien_servicio' in self.env['account.move.line']._fields
        # IVA del DTE (importador >= 18.0.1.8.0) y otros impuestos (>= 18.0.1.9.0)
        tiene_dte = 'gt_dte_iva' in campos_move and 'gt_dte_total' in campos_move
        tiene_otros = 'gt_dte_otros_impuestos' in campos_move

        tipos = ['in_invoice','in_refund']
        if tiene_type:
            filtro.append(('type','in',tipos))
        else:
            filtro.append(('move_type','in',tipos))
        
        facturas = self.env['account.move'].search(filtro)
        impuestos = self.env['account.tax'].browse(datos['impuestos_id'])
        impuestos_ids = set(impuestos.ids)
        tasas_por_compania = {}

        info_control = {
            'ventas': False, 'iva_libro': CERO, 'con_iva': {}, 'vigentes': [],
            'hallazgos': [], 'dte_usados': 0,
            'iva_calculado': {}, 'iva_fila': {}, 'numeros': {},
            'impuestos_ids': list(impuestos_ids), 'diarios_ids': journal_ids,
            'tipos': tipos, 'fecha_desde': datos['fecha_desde'], 'fecha_hasta': datos['fecha_hasta'],
        }

        lineas = []
        for f in facturas:
            totales['num_facturas'] += 1

            tipo_cambio = 1
            if f.currency_id.id != f.company_id.currency_id.id:
                # Probar con impuesto inicialmente
                for l in f.invoice_line_ids:
                    if impuestos_ids.intersection(l.tax_ids.ids):
                        if l.amount_currency != 0:
                            tipo_cambio = l.balance/l.amount_currency
                
                # Si la factura no tiene impuesto, entonces usar cuenta por cobrar/pagar
                if tipo_cambio == 1:
                    total = 0
                    for l in f.line_ids:
                        if l.account_id.reconcile:
                            total += l.debit - l.credit
                    if f.amount_total != 0:
                        tipo_cambio = abs(total / f.amount_total)

            # Libro de varias compañías: tasa entre monedas de compañía. Se
            # MULTIPLICA por la de la factura (antes la reemplazaba y una
            # factura en USD de otra compañía perdía su conversión).
            tasa_compania = 1
            if f.company_id.id != self.env.company.id:
                if f.company_id.id not in tasas_por_compania:
                    tasas_por_compania[f.company_id.id] = self.env['res.currency']._get_conversion_rate(f.company_id.currency_id, self.env.company.currency_id)
                tasa_compania = tasas_por_compania[f.company_id.id]
                tipo_cambio = tipo_cambio * tasa_compania

            tipo_interno_factura = f.type if tiene_type else f.move_type

            # es_nc manda el SIGNO de la rectificativa. Antes se comparaba el
            # texto 'tipo', al que más abajo se le pegaba ' PEQ': una nota de
            # crédito de un proveedor pequeño contribuyente quedaba 'NC PEQ' y
            # nunca cambiaba de signo, por lo que SUMABA en el libro.
            # Las notas de débito no cambian de signo (comportamiento anterior).
            es_nc = tipo_interno_factura != 'in_invoice' and not f.nota_debito
            codigo = codigo_dte(f, campos_dte)
            peq = es_pequenio(f, campo_afil, codigo)
            sin_credito = sin_credito_fiscal(
                regimen_comprador, codigo, afiliacion_emisor(f, campo_afil)
            )

            tipo = 'FACT'
            if tipo_interno_factura != 'in_invoice':
                tipo = 'NC'
            if f.nota_debito:
                tipo = 'ND'
            if peq:
                tipo += ' PEQ'

            # 'tipo' se usa para la lógica (sin cambios). 'tipo_mostrar' es lo que se imprime.
            tipo_mostrar = tipo
            if codigo:
                tipo_mostrar = codigo
           
            numero = f.ref or ''
            
            # Por si usa factura electrónica
            if tiene_fel_antiguo and f.firma_fel:
                numero = str(f.serie_fel) + '-' + str(f.numero_fel)
            if tiene_fel_nuevo and f.l10n_gt_fel_uuid:
                numero = '%s-%s' % (f.l10n_gt_fel_serie or '', f.l10n_gt_fel_numero or '')

            # Anulada: cancelada en Odoo, o DTE marcado como anulado.
            # Aparece en el libro con fecha, tipo, serie y numero, pero con montos en cero.
            anulada = f.state == 'cancel' or (tiene_fel_state and f.l10n_gt_fel_state == 'anulado')
            if anulada:
                numero = '%s (ANULADA)' % (numero or '')

            linea = {
                'estado': f.state,
                'tipo': tipo_mostrar,
                'fecha': f.invoice_date,
                'numero': numero,
                'proveedor': f.partner_id,
                'move_id': f.id,
            }
            linea.update(fila_vacia(columnas))

            if anulada:
                lineas.append(linea)
                continue

            info_control['vigentes'].append(f.id)
            if not sin_credito:
                info_control['con_iva'][f.id] = tasa_compania

            for l in f.invoice_line_ids:
                precio = ( l.price_unit * (1-(l.discount or 0.0)/100.0) ) * tipo_cambio
                if es_nc:
                    precio = precio * -1

                tipo_linea = columna_linea(
                    f.tipo_gasto,
                    l.product_id.type,
                    l.gt_bien_servicio if tiene_bien_servicio else False,
                )

                if peq:
                    tipo_linea = 'pequeño'

                # Siempre enviar cantidad y precio correctos. Por qué algunos impuestos se calculan por cantidades.
                r = l.tax_ids.compute_all(precio, currency=f.currency_id, quantity=l.quantity, product=l.product_id, partner=f.partner_id)

                # Sin crédito fiscal: el monto completo pagado (con cualquier
                # impuesto que traiga la línea) va a la columna exenta, sin IVA.
                if sin_credito:
                    linea[tipo_linea+'_exento'] += dec(r['total_included'])
                    continue

                # No es exenta si trae el impuesto seleccionado en el wizard
                if impuestos_ids.intersection(l.tax_ids.ids):
                    linea[tipo_linea] += dec(r['total_excluded'])
                    for i in r['taxes']:
                        if i['id'] in impuestos_ids:
                            linea['iva_col'][tipo_linea] += dec(i['amount'])
                        elif (i['amount'] > 0 and not es_nc) or (i['amount'] < 0 and es_nc):
                            # Impuesto distinto del IVA: «Impuestos y contribuciones» (5.66)
                            linea['otros'] += dec(i['amount'])
                else:
                    linea[tipo_linea+'_exento'] += dec(r['total_excluded'])

            redondear_fila(linea, columnas)
            iva_calculado = linea['iva']
            # En el control va también el número de Odoo: la búsqueda de
            # facturas no encuentra la serie del DTE.
            numero_control = numero
            if f.name and f.name != '/' and f.name not in str(numero):
                numero_control = '%s (%s)' % (numero, f.name)

            # IVA del DTE: solo con crédito fiscal y si el importador lo llenó
            # (vigente con total 0 = vacío). Sin crédito fiscal (PEQ, EXE,
            # RECI...) todo sigue en exento, como siempre.
            if tiene_dte and f.gt_dte_total and not sin_credito:
                tc_dte = tipo_cambio_documento(f.amount_total_signed, f.amount_total) if f.currency_id.id != f.company_id.currency_id.id else 1
                tc_dte = dec(tc_dte) * dec(tasa_compania)
                signo = -1 if es_nc else 1
                otros_dte = monto_dte(f.gt_dte_otros_impuestos, tc_dte, signo) if tiene_otros else None
                hallazgo = aplicar_dte(
                    linea, columnas,
                    monto_dte(f.gt_dte_total, tc_dte, signo),
                    monto_dte(f.gt_dte_iva, tc_dte, signo),
                    otros_dte,
                )
                if hallazgo:
                    redondear_fila(linea, columnas)
                    info_control['hallazgos'].append((numero_control, hallazgo))
                else:
                    info_control['dte_usados'] += 1

            if f.id in info_control['con_iva']:
                info_control['iva_calculado'][f.id] = iva_calculado
                info_control['iva_fila'][f.id] = linea['iva']
                info_control['numeros'][f.id] = numero_control
            acumular_totales(totales, linea, columnas)
            info_control['iva_libro'] += linea['iva']
            lineas.append(linea)

        lineas = sorted(lineas, key = lambda i: str(i['fecha']) + str(i['numero']))

        for l in lineas:
            a_float_fila(l, columnas)
        # Pie «Control» solo si el contador lo pide (casilla del asistente):
        # el libro oficial se imprime sin él.
        control = None
        if datos.get('incluir_control'):
            control = control_libro(self.env, info_control)
            control['mensajes'] = mensajes_control(control)

        return { 'lineas': lineas, 'totales': a_float_totales(totales), 'control': control }

    @api.model
    def _get_report_values(self, docids, data=None):
        model = self.env.context.get('active_model')
        docs = self.env[model].browse(self.env.context.get('active_ids', []))

        if len(data['form']['diarios_id']) == 0:
            raise UserError("Por favor ingrese al menos un diario.")

        diario = self.env['account.journal'].browse(data['form']['diarios_id'][0])

        return {
            'doc_ids': self.ids,
            'doc_model': model,
            'data': data['form'],
            'docs': docs,
            'lineas': self.lineas,
            'direccion_diario': diario.direccion,
            'current_company_id': self.env.company,
        }
