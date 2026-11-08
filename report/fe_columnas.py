# -*- encoding: utf-8 -*-
"""Estado de flujo de efectivo, método indirecto (NIIF para PYMES, Secc. 7).

Funciones puras (sin base de datos) para poder probarlas.

Idea: por partida doble, el aumento del efectivo es igual a la suma del
movimiento (haber - debe) de todas las demás cuentas. Así:

- Utilidad neta = haber - debe de las cuentas de resultados.
- Cada cuenta de balance que no es efectivo aporta (haber - debe) de su
  movimiento en la columna: un aumento de activo es salida (negativo) y
  un aumento de pasivo o capital es entrada (positivo).
- Comprobación = movimiento real de las cuentas de efectivo. Si la
  Diferencia no es 0.00, hay una cuenta mal clasificada (o una cuenta
  marcada «excluir» con movimiento, p. ej. el asiento de cierre).

Columnas (mismas que el Estado de Resultados):
- normal:      una columna.
- por_mes:     una por mes y Total. En el Total, «efectivo al inicio» es
               el del primer mes y «al final» el del último (no se suman).
- acumulativo: Acumulado | Mes | Total.
"""

from . import er_columnas

TIPOS_RESULTADOS = er_columnas.TIPOS_RESULTADOS

CLASES = [
    ('efectivo', 'Efectivo y equivalentes'),
    ('op_cobrar', 'Operación – cuentas por cobrar'),
    ('op_inventario', 'Operación – inventarios'),
    ('op_activo', 'Operación – otros activos corrientes'),
    ('op_pagar', 'Operación – cuentas por pagar'),
    ('op_pasivo', 'Operación – impuestos y otros pasivos'),
    ('depreciacion', 'Depreciación / amortización acumulada'),
    ('inversion', 'Inversión'),
    ('fin_pasivo', 'Financiamiento – préstamos y obligaciones'),
    ('fin_capital', 'Financiamiento – aportes, retiros y dividendos'),
    ('excluir', 'Excluir (resultados acumulados)'),
]

# Regla por omisión: solo por tipo de cuenta (regla 0 del CLAUDE.md).
POR_TIPO = {
    'asset_cash': 'efectivo',
    'asset_receivable': 'op_cobrar',
    'asset_current': 'op_activo',
    'asset_prepayments': 'op_activo',
    'liability_payable': 'op_pagar',
    'liability_current': 'op_pasivo',
    'liability_credit_card': 'op_pasivo',
    'asset_fixed': 'inversion',
    'asset_non_current': 'inversion',
    'liability_non_current': 'fin_pasivo',
    'equity': 'fin_capital',
    'equity_unaffected': 'excluir',
}

# (clave, etiqueta, clases que suma). El orden es el del estado.
OPERACION = [
    ('ajustes', 'Ajustes que no son efectivo:', None),
    ('depreciacion', '(+) Depreciaciones y amortizaciones', ('depreciacion',)),
    ('capital_trabajo', 'Cambios en capital de trabajo:', None),
    ('op_cobrar', '(Aumento) disminución en cuentas por cobrar', ('op_cobrar',)),
    ('op_inventario', '(Aumento) disminución en inventarios', ('op_inventario',)),
    ('op_activo', '(Aumento) disminución en otros activos corrientes', ('op_activo',)),
    ('op_pagar', 'Aumento (disminución) en cuentas por pagar', ('op_pagar',)),
    ('op_pasivo', 'Aumento (disminución) en impuestos y otros pasivos', ('op_pasivo',)),
]
INVERSION = [
    ('inversion', 'Propiedad, planta y equipo y otros activos no corrientes', ('inversion',)),
]
FINANCIAMIENTO = [
    ('fin_pasivo', 'Préstamos y otras obligaciones', ('fin_pasivo',)),
    ('fin_capital', 'Aportes, retiros y dividendos', ('fin_capital',)),
]


def clase_cuenta(account_type, clase=False, es_transitoria=False):
    """La clasificación elegida en la cuenta manda; si está vacía, las
    cuentas transitorias de Odoo (pendientes, suspenso, liquidez) son
    efectivo, y el resto se decide por tipo. Cuentas de resultados y
    fuera de balance: False."""
    if account_type in TIPOS_RESULTADOS or account_type == 'off_balance':
        return False
    if clase:
        return clase
    if es_transitoria:
        return 'efectivo'
    return POR_TIPO.get(account_type, False)


def columnas(modo, desde, hasta):
    """Las del ER, sin %; en normal el título es «Período»."""
    cols = []
    for c in er_columnas.columnas(modo, desde, hasta):
        c = dict(c, pct=False)
        if modo not in ('por_mes', 'acumulativo'):
            c['titulo'] = 'Período'
        cols.append(c)
    return cols


def construir(cuentas, movimientos, efectivo_inicial, modo, desde, hasta):
    """
    cuentas:          {account_id: {'codigo', 'nombre', 'account_type',
                       'clase' (campo o False), 'transitoria' (bool)}}
    movimientos:      [{'account_id', 'mes', 'debe', 'haber'}] en el rango.
    efectivo_inicial: saldo de las cuentas de efectivo antes de `desde`.
    """
    desde, hasta = er_columnas.a_fecha(desde), er_columnas.a_fecha(hasta)
    cols = columnas(modo, desde, hasta)
    n = len(cols)
    meses = er_columnas.meses_entre(desde, hasta)
    indice_mes = {}
    for i, c in enumerate(cols):
        for m in c['meses']:
            indice_mes.setdefault(m, []).append(i)

    utilidad = [0.0] * n
    por_cuenta = {}           # aid -> valores (haber - debe)
    efectivo_mes = {m: 0.0 for m in meses}   # movimiento real (debe - haber)
    for mv in movimientos:
        cta = cuentas.get(mv['account_id'])
        if not cta:
            continue
        mes = er_columnas.a_fecha(mv['mes'])
        flujo = float(mv['haber'] or 0) - float(mv['debe'] or 0)
        if cta['account_type'] in TIPOS_RESULTADOS:
            for i in indice_mes.get(mes, []):
                utilidad[i] += flujo
            continue
        clase = clase_cuenta(cta['account_type'], cta.get('clase'), cta.get('transitoria'))
        if clase == 'efectivo':
            efectivo_mes[mes] = efectivo_mes.get(mes, 0.0) - flujo
            continue
        if not clase or clase == 'excluir':
            continue
        fila = por_cuenta.setdefault(mv['account_id'], [0.0] * n)
        for i in indice_mes.get(mes, []):
            fila[i] += flujo

    def renglones(definicion):
        res, total = [], [0.0] * n
        for clave, etiqueta, clases in definicion:
            if clases is None:
                res.append({'clave': clave, 'etiqueta': etiqueta, 'subtitulo': True,
                            'valores': None, 'cuentas': []})
                continue
            vals, filas = [0.0] * n, []
            for aid, v in por_cuenta.items():
                cta = cuentas[aid]
                if clase_cuenta(cta['account_type'], cta.get('clase'),
                                cta.get('transitoria')) not in clases:
                    continue
                if all(abs(x) < 0.005 for x in v):
                    continue
                for k in range(n):
                    vals[k] += v[k]
                filas.append({'codigo': cta['codigo'], 'nombre': cta['nombre'],
                              'valores': list(v)})
            filas.sort(key=lambda f: er_columnas.llave_orden(f['codigo']))
            for k in range(n):
                total[k] += vals[k]
            res.append({'clave': clave, 'etiqueta': etiqueta, 'subtitulo': False,
                        'valores': vals, 'cuentas': filas})
        return res, total

    op_reng, op_total = renglones(OPERACION)
    op_reng.insert(0, {'clave': 'utilidad', 'etiqueta': 'Utilidad (pérdida) neta del período',
                       'subtitulo': False, 'valores': list(utilidad), 'cuentas': []})
    op_total = [op_total[k] + utilidad[k] for k in range(n)]
    inv_reng, inv_total = renglones(INVERSION)
    fin_reng, fin_total = renglones(FINANCIAMIENTO)
    neto = [op_total[k] + inv_total[k] + fin_total[k] for k in range(n)]

    # Efectivo al inicio y comprobación (saldo real) por columna
    def saldo_antes(mes):
        return float(efectivo_inicial or 0) + sum(v for m, v in efectivo_mes.items() if m < mes)

    def saldo_hasta(mes):
        return float(efectivo_inicial or 0) + sum(v for m, v in efectivo_mes.items() if m <= mes)

    inicio, real = [], []
    for c in cols:
        if c['meses']:
            inicio.append(saldo_antes(c['meses'][0]))
            real.append(saldo_hasta(c['meses'][-1]))
        else:   # Acumulado vacío (el rango es de un solo mes)
            inicio.append(float(efectivo_inicial or 0))
            real.append(float(efectivo_inicial or 0))
    final = [inicio[k] + neto[k] for k in range(n)]
    diferencia = [round(final[k] - real[k], 2) + 0.0 for k in range(n)]

    secciones = [
        {'clave': 'operacion', 'titulo': 'A. ACTIVIDADES DE OPERACIÓN', 'renglones': op_reng,
         'total_etiqueta': 'Efectivo neto de actividades de operación', 'total': op_total},
        {'clave': 'inversion', 'titulo': 'B. ACTIVIDADES DE INVERSIÓN', 'renglones': inv_reng,
         'total_etiqueta': 'Efectivo neto de actividades de inversión', 'total': inv_total},
        {'clave': 'financiamiento', 'titulo': 'C. ACTIVIDADES DE FINANCIAMIENTO',
         'renglones': fin_reng,
         'total_etiqueta': 'Efectivo neto de actividades de financiamiento', 'total': fin_total},
    ]
    cierre = [
        {'etiqueta': 'AUMENTO (DISMINUCIÓN) NETO DEL EFECTIVO (A+B+C)', 'valores': neto,
         'negrita': True},
        {'etiqueta': 'Efectivo al inicio del período', 'valores': inicio, 'negrita': False},
        {'etiqueta': 'EFECTIVO AL FINAL DEL PERÍODO', 'valores': final, 'negrita': True},
        {'etiqueta': 'Comprobación: saldo de las cuentas de efectivo', 'valores': real,
         'negrita': False, 'nota': True},
        {'etiqueta': 'Diferencia (debe ser 0.00)', 'valores': diferencia, 'negrita': False,
         'nota': True},
    ]
    return {
        'columnas': cols,
        'encabezados': [c['titulo'] for c in cols],
        'secciones': secciones,
        'cierre': cierre,
        'utilidad': utilidad,
        'neto': neto,
        'inicio': inicio,
        'final': final,
        'real': real,
        'diferencia': diferencia,
    }


def filas_planas(res, detalle=True):
    """Lista de filas para el PDF y el Excel. tipo: seccion, subtitulo,
    renglon, cuenta, total, cierre, nota."""
    filas = []
    for sec in res['secciones']:
        filas.append({'tipo': 'seccion', 'etiqueta': sec['titulo'], 'valores': None})
        for r in sec['renglones']:
            if r['subtitulo']:
                filas.append({'tipo': 'subtitulo', 'etiqueta': r['etiqueta'], 'valores': None})
                continue
            filas.append({'tipo': 'renglon', 'etiqueta': r['etiqueta'], 'valores': r['valores']})
            if detalle:
                for c in r['cuentas']:
                    filas.append({'tipo': 'cuenta', 'codigo': c['codigo'],
                                  'etiqueta': c['nombre'], 'valores': c['valores']})
        filas.append({'tipo': 'total', 'etiqueta': sec['total_etiqueta'], 'valores': sec['total']})
    for c in res['cierre']:
        filas.append({'tipo': 'nota' if c.get('nota') else 'cierre', 'etiqueta': c['etiqueta'],
                      'valores': c['valores'], 'negrita': c['negrita']})
    return filas
