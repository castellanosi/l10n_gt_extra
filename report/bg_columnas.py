# -*- encoding: utf-8 -*-
"""Balance general por modo, con la misma idea que er_columnas.

Modos:
- normal:      Saldo al corte.
- por_mes:     Saldo al cierre de cada mes, desde el mes de inicio del
               período de resultados hasta el corte (máximo 12). Sin
               Total: los saldos no se suman entre meses.
- acumulativo: Saldo anterior (cierre del mes anterior al corte) |
               Mes (movimiento del mes del corte) | Saldo al corte.

En cada columna, la utilidad del período es la del Estado de Resultados
desde la fecha de inicio de resultados hasta el cierre de esa columna
(en «Mes», la utilidad de ese mes).

Funciones puras (sin base de datos) para poder probarlas.
"""

from .er_columnas import (
    a_fecha, fin_mes, inicio_mes, llave_orden, meses_entre, titulo_mes,
)

TIPOS_ACTIVO = (
    'asset_receivable', 'asset_cash', 'asset_current',
    'asset_non_current', 'asset_prepayments', 'asset_fixed',
)
TIPOS_PASIVO = (
    'liability_payable', 'liability_credit_card',
    'liability_current', 'liability_non_current',
)
TIPOS_CAPITAL = ('equity', 'equity_unaffected')
TIPOS_BALANCE = TIPOS_ACTIVO + TIPOS_PASIVO + TIPOS_CAPITAL

SECCIONES = [
    ('activo', 'ACTIVO'),
    ('pasivo', 'PASIVO'),
    ('capital', 'CAPITAL'),
]


def seccion(account_type):
    if account_type in TIPOS_ACTIVO:
        return 'activo'
    if account_type in TIPOS_PASIVO:
        return 'pasivo'
    if account_type in TIPOS_CAPITAL:
        return 'capital'
    return False


def columnas(modo, desde_er, hasta):
    """
    Cada columna: titulo, 'corte' (fecha hasta la que se suma) y
    'desde' (False = desde el inicio de los tiempos; una fecha = solo el
    movimiento desde ese día, para la columna «Mes»).
    """
    desde_er, hasta = a_fecha(desde_er), a_fecha(hasta)
    if modo == 'por_mes':
        cols = []
        for m in meses_entre(desde_er, hasta):
            cols.append({'titulo': titulo_mes(m), 'corte': min(fin_mes(m), hasta),
                         'desde': False, 'pct': False})
        return cols
    if modo == 'acumulativo':
        ini = inicio_mes(hasta)
        anterior = ini.fromordinal(ini.toordinal() - 1)
        return [
            {'titulo': 'Saldo anterior', 'corte': anterior, 'desde': False, 'pct': False},
            {'titulo': 'Mes', 'corte': hasta, 'desde': ini, 'pct': False},
            {'titulo': 'Saldo al corte', 'corte': hasta, 'desde': False, 'pct': False},
        ]
    return [{'titulo': 'Saldo', 'corte': hasta, 'desde': False, 'pct': False}]


def construir(cuentas, movimientos, utilidades, modo, desde_er, hasta):
    """
    cuentas:     {account_id: {'codigo', 'nombre', 'account_type'}}
    movimientos: [{'account_id', 'fecha', 'debe', 'haber'}] hasta el corte
                 (la fecha puede venir agrupada por mes o por día).
    utilidades:  utilidad del período para cada columna (misma longitud).
    """
    cols = columnas(modo, desde_er, hasta)
    n = len(cols)
    saldos = {}
    for mv in movimientos:
        cta = cuentas.get(mv['account_id'])
        sec = cta and seccion(cta['account_type'])
        if not sec:
            continue
        neto = float(mv['debe'] or 0) - float(mv['haber'] or 0)
        if sec != 'activo':
            neto = -neto
        f = a_fecha(mv['fecha'])
        fila = saldos.setdefault(mv['account_id'], [0.0] * n)
        for k, c in enumerate(cols):
            if f <= c['corte'] and (not c['desde'] or f >= c['desde']):
                fila[k] += neto

    totales = {s: [0.0] * n for s, _t in SECCIONES}
    secciones = []
    for sec, titulo in SECCIONES:
        filas = []
        for aid, vals in saldos.items():
            cta = cuentas[aid]
            if seccion(cta['account_type']) != sec or all(abs(v) < 0.005 for v in vals):
                continue
            for k in range(n):
                totales[sec][k] += vals[k]
            filas.append({'codigo': cta['codigo'], 'nombre': cta['nombre'],
                          'valores': list(vals)})
        filas.sort(key=lambda f: llave_orden(f['codigo']))
        if sec == 'capital':
            filas.append({'codigo': '', 'nombre': 'Utilidad (pérdida) del período',
                          'valores': list(utilidades)})
            for k in range(n):
                totales[sec][k] += utilidades[k]
        secciones.append({'clave': sec, 'titulo': titulo, 'filas': filas,
                          'total': totales[sec]})

    act, pas, cap = totales['activo'], totales['pasivo'], totales['capital']
    pas_cap = [pas[k] + cap[k] for k in range(n)]
    resumen = [
        {'etiqueta': 'Total activo', 'valores': act, 'negrita': True},
        {'etiqueta': 'Total pasivo', 'valores': pas, 'negrita': False},
        {'etiqueta': 'Total capital (incluye utilidad)', 'valores': cap, 'negrita': False},
        {'etiqueta': 'Total pasivo + capital', 'valores': pas_cap, 'negrita': True},
        {'etiqueta': 'Diferencia', 'valores': [round(act[k] - pas_cap[k], 2) + 0.0 for k in range(n)],
         'negrita': False},
    ]
    return {
        'columnas': cols,
        'encabezados': [c['titulo'] for c in cols],
        'resumen': resumen,
        'secciones': secciones,
        'ingresos_col': [0.0] * n,
        'total_activo': act[-1],
        'total_pasivo': pas[-1],
        'total_capital_mas_utilidad': cap[-1],
        'utilidad_periodo': utilidades[-1],
        'total_pasivo_capital': pas_cap[-1],
        'cuadre': act[-1] - pas_cap[-1],
    }


def utilidades_por_columna(modo, er_res):
    """Utilidad de cada columna del balance a partir del ER del mismo modo.

    normal: total. por_mes: suma corrida de los meses (sin la col. Total).
    acumulativo: Acumulado, Mes, Total del ER = anterior, mes, al corte.
    """
    neta = er_res['resumen'][4]['valores']
    if modo == 'por_mes':
        corrida, acum = [], 0.0
        for v in neta[:-1]:
            acum += v
            corrida.append(acum)
        return corrida
    return list(neta)
