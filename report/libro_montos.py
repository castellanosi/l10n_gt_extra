# -*- encoding: utf-8 -*-
"""Montos de una fila de los libros de compras y ventas (desde 5.66).

Funciones puras: no usan el ORM, se prueban sin base de datos
(tests/test_libro_montos.py).

Reglas:
- Todo se calcula con Decimal y cada monto de la fila se redondea a 2
  decimales (mitad hacia arriba). Los totales del libro son la suma de las
  filas ya redondeadas: así el Excel no trae 6579029.240000144.
- IVA del DTE (gt_xml_importer / gt_mass_importer, campos gt_dte_*): la fila
  se calcula como siempre y solo se corrige la diferencia de IVA (IVA DTE −
  IVA calculado), que se resta de la columna gravada de mayor monto. Si el
  total de la fila no queda igual al Gran Total del DTE, la fila queda como
  se calculó y se cuenta como hallazgo en el pie de control.
- «Impuestos y contribuciones» (columna 'otros'): impuestos distintos del IVA
  (IDP, Tasa Municipal, Turismo, Timbre, Bomberos...). El importador los deja
  en una línea sin impuestos, que el cálculo pone en exento; si el DTE trae
  gt_dte_otros_impuestos, ese monto se pasa de exento a 'otros'.
"""

from decimal import ROUND_HALF_UP, Decimal

CENTAVO = Decimal('0.01')
CERO = Decimal('0')

# Diferencia máxima de IVA que se corrige con el dato del DTE. El emisor
# redondea por línea: en septiembre 2026 la mayor diferencia fue Q0.06. Una
# diferencia mayor indica otra cosa (p. ej. otros impuestos dentro de la
# línea gravada, importado antes de gt_mass_importer 1.9.0): no se corrige.
DIFERENCIA_IVA_MAXIMA = Decimal('1.00')

COLUMNAS_VENTAS = ('compra', 'servicio', 'combustible', 'importacion')
COLUMNAS_COMPRAS = COLUMNAS_VENTAS + ('pequeño',)

# Motivos por los que una fila con datos del DTE se deja como se calculó.
HALLAZGOS = {
    'total_distinto': 'El total de la fila no es igual al Gran Total del DTE',
    'iva_grande': 'Diferencia de IVA con el DTE mayor a Q1.00',
    'sin_gravado': 'IVA del DTE distinto pero la fila no tiene monto gravado',
    'otros_sin_linea': 'El DTE trae otros impuestos pero la factura no tiene la línea exenta que los contiene',
}


def dec(valor):
    """Decimal exacto de un float, int, texto o None (None y False -> 0).

    Con float se usa repr(): Decimal(58.1) da 58.09999..., Decimal('58.1') no.
    """
    if valor is None or valor is False:
        return CERO
    if isinstance(valor, Decimal):
        return valor
    if isinstance(valor, float):
        return Decimal(repr(valor))
    return Decimal(str(valor).strip() or '0')


def r2(valor):
    """Redondea a 2 decimales, mitad hacia arriba. Devuelve Decimal."""
    return dec(valor).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def sumar(valores):
    """Suma exacta con Decimal, redondeada a 2 decimales."""
    total = CERO
    for v in valores:
        total += dec(v)
    return r2(total)


def a_float(valor):
    """Float de un monto ya redondeado (para QWeb y xlsxwriter)."""
    return float(r2(valor))


def fila_vacia(columnas):
    """Montos en cero de una fila del libro (las claves de siempre + 'otros')."""
    fila = {}
    for c in columnas:
        fila[c] = CERO
        fila[c + '_exento'] = CERO
    fila['otros'] = CERO
    fila['base'] = CERO
    fila['iva'] = CERO
    fila['total'] = CERO
    # IVA por columna, para los totales del resumen (Bienes, Servicios...).
    fila['iva_col'] = {c: CERO for c in columnas}
    return fila


def total_fila(fila, columnas):
    """Gravado + exento + impuestos y contribuciones + IVA."""
    total = fila['otros'] + fila['iva']
    for c in columnas:
        total += fila[c] + fila[c + '_exento']
    return total


def redondear_fila(fila, columnas):
    """Redondea cada monto a 2 decimales y recalcula IVA, base y total.

    El IVA de la fila es la suma del IVA por columna ya redondeado, para que
    el resumen por columna y el IVA de las filas sumen lo mismo.
    """
    for c in columnas:
        fila[c] = r2(fila[c])
        fila[c + '_exento'] = r2(fila[c + '_exento'])
        fila['iva_col'][c] = r2(fila['iva_col'][c])
    fila['otros'] = r2(fila['otros'])
    fila['iva'] = sum(fila['iva_col'].values(), CERO)
    fila['base'] = sum((fila[c] + fila[c + '_exento'] for c in columnas), CERO)
    fila['total'] = total_fila(fila, columnas)
    return fila


def tipo_cambio_documento(monto_moneda_compania, monto_moneda_documento):
    """Q por 1 unidad de la moneda de la factura, del propio asiento.

    abs(amount_total_signed) / amount_total. Nunca una tasa aparte.
    """
    documento = abs(dec(monto_moneda_documento))
    if documento == 0:
        return Decimal('1')
    return abs(dec(monto_moneda_compania)) / documento


def monto_dte(valor, tipo_cambio, signo):
    """Monto del DTE convertido a la moneda del libro, a 2 decimales, con signo.

    Los campos gt_dte_* vienen siempre positivos; el signo lo da el tipo de
    documento (nota de crédito: -1).
    """
    return r2(dec(valor) * dec(tipo_cambio)) * signo


def mover_otros(fila, columnas, otros_dte):
    """Pasa los otros impuestos del DTE de exento a 'otros'.

    otros_dte lleva el signo de la fila. Si la fila ya tiene impuestos en
    'otros' (impuestos de Odoo distintos del IVA), solo se mueve lo que falta.
    Devuelve True si pudo, False si las columnas exentas no alcanzan (la
    factura no tiene la línea de otros impuestos: no se toca nada).
    """
    falta = otros_dte - fila['otros']
    if falta == 0:
        return True
    if (falta > 0) != (otros_dte > 0):
        # Ya hay más en 'otros' que lo que dice el DTE: no se toca.
        return True
    exentas = sorted(
        (c + '_exento' for c in columnas if fila[c + '_exento'] != 0),
        key=lambda k: abs(fila[k]),
        reverse=True,
    )
    disponible = sum((fila[k] for k in exentas if (fila[k] > 0) == (falta > 0)), CERO)
    if abs(disponible) < abs(falta):
        return False
    for k in exentas:
        if falta == 0:
            break
        if (fila[k] > 0) != (falta > 0):
            continue
        tomar = fila[k] if abs(fila[k]) <= abs(falta) else falta
        fila[k] -= tomar
        fila['otros'] += tomar
        falta -= tomar
    return True


def ajustar_iva_dte(fila, columnas, iva_dte, total_dte):
    """Corrige el IVA de una fila ya redondeada con el IVA del DTE.

    iva_dte y total_dte ya convertidos y con el signo de la fila.
    Devuelve None si la fila quedó bien (con o sin corrección) o la clave del
    hallazgo (HALLAZGOS) si se deja como se calculó.
    """
    diferencia = iva_dte - fila['iva']
    if diferencia != 0:
        if abs(diferencia) > DIFERENCIA_IVA_MAXIMA:
            return 'iva_grande'
        gravadas = [c for c in columnas if fila[c] != 0]
        if not gravadas:
            return 'sin_gravado'
        columna = max(gravadas, key=lambda c: abs(fila[c]))
        nueva = dict(fila)
        nueva['iva_col'] = dict(fila['iva_col'])
        nueva[columna] -= diferencia
        nueva['iva_col'][columna] += diferencia
        nueva['iva'] += diferencia
        if total_fila(nueva, columnas) != total_dte:
            return 'total_distinto'
        fila.update(nueva)
    elif total_fila(fila, columnas) != total_dte:
        return 'total_distinto'
    fila['base'] = sum((fila[c] + fila[c + '_exento'] for c in columnas), CERO)
    fila['total'] = total_fila(fila, columnas)
    return None


def aplicar_dte(fila, columnas, total_dte, iva_dte, otros_dte=None):
    """Otros impuestos y luego IVA del DTE. Devuelve None o la clave del hallazgo."""
    if otros_dte:
        if not mover_otros(fila, columnas, otros_dte):
            return 'otros_sin_linea'
    return ajustar_iva_dte(fila, columnas, iva_dte, total_dte)


def totales_vacios(columnas):
    totales = {'num_facturas': 0}
    for c in columnas:
        totales[c] = {'exento': CERO, 'neto': CERO, 'iva': CERO, 'total': CERO}
    totales['otros'] = {'total': CERO}
    totales['general'] = {'exento': CERO, 'neto': CERO, 'iva': CERO, 'otros': CERO, 'total': CERO}
    return totales


def acumular_totales(totales, fila, columnas):
    """Suma una fila redondeada a los totales (por columna y generales)."""
    for c in columnas:
        neto = fila[c]
        exento = fila[c + '_exento']
        iva = fila['iva_col'][c]
        totales[c]['neto'] += neto
        totales[c]['exento'] += exento
        totales[c]['iva'] += iva
        totales[c]['total'] += neto + exento + iva
        totales['general']['neto'] += neto
        totales['general']['exento'] += exento
        totales['general']['iva'] += iva
    totales['otros']['total'] += fila['otros']
    totales['general']['otros'] += fila['otros']
    totales['general']['total'] += fila['total']


def a_float_fila(fila, columnas):
    """Pasa los montos de la fila a float (QWeb y xlsxwriter) y quita lo interno."""
    for c in columnas:
        fila[c] = a_float(fila[c])
        fila[c + '_exento'] = a_float(fila[c + '_exento'])
    for k in ('otros', 'base', 'iva', 'total'):
        fila[k] = a_float(fila[k])
    fila.pop('iva_col', None)
    return fila


def a_float_totales(totales):
    for k, v in totales.items():
        if isinstance(v, dict):
            for kk in v:
                v[kk] = a_float(v[kk])
    return totales
