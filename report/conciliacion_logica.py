# -*- encoding: utf-8 -*-
"""Conciliación bancaria: reglas puras (sin base de datos) para probarlas.

Decisión del usuario (07/11/2026): todo movimiento de una cuenta de banco
se considera cobrado, salvo los marcados «En tránsito». Un movimiento en
tránsito deja de estar pendiente desde su «Fecha de cobro en banco».

Pendiente al corte = en tránsito, fecha <= corte y (sin fecha de cobro o
fecha de cobro > corte). Así, un cheque de octubre cobrado en noviembre
sale pendiente en la conciliación de octubre y no en la de noviembre.

Presentación:
    Saldo según libros
    (+) Cheques y débitos en tránsito
    (−) Depósitos y créditos en tránsito
    Saldo según banco (calculado)
    Saldo según estado de cuenta (lo escribe el contador)
    Diferencia (debe ser 0.00)
"""

from .er_columnas import a_fecha


def es_pendiente(linea, corte):
    """linea: dict con 'date', 'en_transito', 'fecha_cobro'."""
    corte = a_fecha(corte)
    if not linea.get('en_transito'):
        return False
    if a_fecha(linea['date']) > corte:
        return False
    cobro = a_fecha(linea.get('fecha_cobro'))
    return not cobro or cobro > corte


def construir(lineas, saldo_libro, saldo_banco, corte):
    """
    lineas: [{'date', 'debit', 'credit', 'en_transito', 'fecha_cobro',
              'documento', 'concepto'}] de la cuenta de banco.
    """
    depositos, cheques = [], []
    for ln in sorted(lineas, key=lambda x: (a_fecha(x['date']), x.get('documento') or '')):
        if not es_pendiente(ln, corte):
            continue
        neto = float(ln['debit'] or 0) - float(ln['credit'] or 0)
        entrada = {
            'fecha': a_fecha(ln['date']),
            'documento': ln.get('documento') or '',
            'concepto': ln.get('concepto') or '',
            'monto': abs(neto),
        }
        (depositos if neto > 0 else cheques).append(entrada)

    total_depositos = sum(d['monto'] for d in depositos)
    total_cheques = sum(c['monto'] for c in cheques)
    saldo_libro = float(saldo_libro or 0)
    saldo_banco = float(saldo_banco or 0)
    calculado = saldo_libro + total_cheques - total_depositos
    return {
        'saldo_libro': saldo_libro,
        'cheques_pendientes': cheques,
        'total_cheques': total_cheques,
        'depositos_transito': depositos,
        'total_depositos': total_depositos,
        'saldo_banco_calculado': calculado,
        'saldo_banco': saldo_banco,
        'diferencia': round(saldo_banco - calculado, 2) + 0.0,
    }
