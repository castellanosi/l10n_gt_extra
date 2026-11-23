# -*- encoding: utf-8 -*-
"""Pie «Control» de los libros de compras y ventas (desde 5.66).

Solo sale si el contador marca «Incluir control» en el asistente: el libro
oficial se imprime sin él. Es informativo: no cambia ningún monto del libro.

Desde el 20/11/2026 NO hay póliza de ajuste: el redondeo del IVA de los DTE
(centavos) se absorbe al liquidar IVA débito contra crédito. Cualquier otra
diferencia entre el IVA del libro y el del asiento se lista para revisar.

Todo se filtra por fecha del documento (invoice_date), igual que el libro.
"""

from decimal import Decimal

from .libro_montos import CERO, HALLAZGOS, a_float, dec, r2

# Diferencia por documento entre el IVA que calcula el libro (antes del IVA del
# DTE) y el IVA del asiento a partir de la cual el documento se lista. Por
# debajo es redondeo de Odoo (por línea o global) y no se lista.
TOLERANCIA_DOCUMENTO = Decimal('0.05')


def _ids_validos(ids):
    return [i for i in ids if i]


def control_libro(env, info):
    """Calcula el pie de control.

    info:
      'ventas': bool (IVA débito: saldo acreedor)
      'iva_libro': Decimal (suma del IVA de las filas)
      'con_iva': {move_id: tasa_compania} documentos cuyo IVA cuenta en el libro
      'vigentes': [move_id] documentos no anulados del libro
      'hallazgos': [(numero, clave)]
      'dte_usados': int
      'iva_calculado': {move_id: Decimal} IVA de la fila antes del IVA del DTE
      'iva_fila': {move_id: Decimal} IVA de la fila en el libro
      'numeros': {move_id: str}
      'impuestos_ids': [tax_id]
      'diarios_ids', 'tipos', 'fecha_desde', 'fecha_hasta'
    """
    Move = env['account.move']
    campos = Move._fields
    cr = env.cr
    env.flush_all()

    con_iva = info['con_iva']
    iva_calculado = info.get('iva_calculado', {})
    iva_fila = info.get('iva_fila', {})
    numeros = info.get('numeros', {})

    # IVA contable de esas mismas facturas (líneas de impuesto del IVA elegido)
    contable_por_move = {}
    impuestos = _ids_validos(info['impuestos_ids'])
    if con_iva and impuestos:
        cr.execute(
            "SELECT move_id, coalesce(sum(balance), 0) FROM account_move_line "
            "WHERE move_id = ANY(%s) AND tax_line_id = ANY(%s) GROUP BY move_id",
            (list(con_iva), impuestos),
        )
        signo = -1 if info['ventas'] else 1
        for move_id, saldo in cr.fetchall():
            contable_por_move[move_id] = r2(dec(saldo) * dec(con_iva.get(move_id, 1))) * signo
    iva_contable = sum(contable_por_move.values(), CERO)
    iva_libro = info['iva_libro']
    diferencia = iva_libro - iva_contable

    # La diferencia se separa en dos: el redondeo del IVA de los DTE (centavos,
    # se ajusta en la liquidación de IVA) y todo lo demás (revisar).
    redondeo_dte = sum((iva_fila[m] - iva_calculado.get(m, CERO) for m in iva_fila), CERO)
    otras = diferencia - redondeo_dte
    documentos = []
    for move_id in con_iva:
        calculado = iva_calculado.get(move_id, CERO)
        contable = contable_por_move.get(move_id, CERO)
        if abs(calculado - contable) > TOLERANCIA_DOCUMENTO:
            documentos.append(
                {
                    'numero': numeros.get(move_id, str(move_id)),
                    'iva_libro': a_float(iva_fila.get(move_id, calculado)),
                    'iva_contable': a_float(contable),
                }
            )
    documentos.sort(key=lambda d: str(d['numero']))

    # Facturas importadas sin datos del DTE: solo las que llevan IVA en el
    # libro (en pequeño contribuyente, exentos y documentos sin crédito
    # fiscal el dato del DTE no cambia nada).
    sin_dte = 0
    if con_iva and 'gt_dte_total' in campos and 'firma_fel' in campos:
        cr.execute(
            "SELECT count(*) FROM account_move WHERE id = ANY(%s) "
            "AND gt_dte_total IS NULL AND coalesce(firma_fel, '') <> ''",
            (list(con_iva),),
        )
        sin_dte = cr.fetchone()[0]

    vigentes = info['vigentes']
    decimales = 0
    diferencia_decimales = CERO
    if vigentes and 'gt_dte_iva_origen' in campos and 'gt_dte_iva' in campos:
        cr.execute(
            "SELECT count(*), coalesce(sum(CASE WHEN move_type IN ('out_refund', 'in_refund') "
            "THEN -(gt_dte_iva - gt_dte_iva_origen::numeric) "
            "ELSE gt_dte_iva - gt_dte_iva_origen::numeric END), 0) "
            "FROM account_move WHERE id = ANY(%s) AND gt_dte_iva_origen IS NOT NULL "
            "AND round(gt_dte_iva_origen::numeric, 2) <> gt_dte_iva_origen::numeric",
            (vigentes,),
        )
        decimales, diferencia_decimales = cr.fetchone()

    borradores = Move.search_count(
        [
            ('state', '=', 'draft'),
            ('journal_id', 'in', info['diarios_ids']),
            ('move_type', 'in', info['tipos']),
            ('invoice_date', '>=', info['fecha_desde']),
            ('invoice_date', '<=', info['fecha_hasta']),
        ]
    )

    hallazgos = [
        {'numero': numero, 'motivo': HALLAZGOS.get(clave, clave)}
        for numero, clave in info['hallazgos']
    ]
    return {
        'iva_libro': a_float(iva_libro),
        'iva_contable': a_float(iva_contable),
        'diferencia': a_float(diferencia),
        'redondeo_dte': a_float(redondeo_dte),
        'otras_diferencias': a_float(otras),
        'documentos': documentos,
        'dte_usados': info['dte_usados'],
        'sin_dte': sin_dte,
        'decimales': decimales,
        'diferencia_decimales': a_float(diferencia_decimales),
        'borradores': borradores,
        'hallazgos': hallazgos,
    }


def mensajes_control(control):
    """Avisos en texto, iguales en PDF y Excel."""
    mensajes = []
    if control['redondeo_dte']:
        mensajes.append(
            'Redondeo del IVA de los DTE: Q %.2f. Se ajusta en la liquidación de IVA.'
            % control['redondeo_dte']
        )
    if control['otras_diferencias'] or control['documentos']:
        mensajes.append(
            'Otras diferencias: Q %.2f en %s documentos cuyo IVA en el libro no es '
            'igual al de su asiento. Revisar antes de declarar.'
            % (control['otras_diferencias'], len(control['documentos']))
        )
    if control['sin_dte']:
        mensajes.append(
            '%s facturas importadas sin datos del DTE (se calcularon como antes): '
            'vuelva a subir la hoja SAT o los XML del mes.' % control['sin_dte']
        )
    if control['decimales']:
        mensajes.append(
            '%s DTE con IVA de más de 2 decimales en la SAT; diferencia por '
            'redondeo: Q %.2f.' % (control['decimales'], control['diferencia_decimales'])
        )
    if control['borradores']:
        mensajes.append(
            '%s documentos del periodo están en borrador y no aparecen en el libro.'
            % control['borradores']
        )
    if control['hallazgos']:
        mensajes.append(
            '%s documentos con datos del DTE que no cuadran: se dejaron como se '
            'calcularon (ver detalle).' % len(control['hallazgos'])
        )
    return mensajes
