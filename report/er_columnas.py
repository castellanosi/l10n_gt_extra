# -*- encoding: utf-8 -*-
"""Estado de resultados: columnas, secciones y agrupación por segmento.

Funciones puras (sin base de datos) para poder probarlas.

Modos:
- normal:      una columna con el período completo.
- por_mes:     una columna por mes del rango y el Total.
- acumulativo: Acumulado (meses anteriores) | Mes | % | Total | %.

Detalle: por sección (INGRESOS, COSTO DE VENTAS, GASTOS), cada una con
sus cuentas ordenadas por código y su total. Sin niveles intermedios
(decisión del usuario, 5.56).
"""

from datetime import date, timedelta

MESES = ['ENE', 'FEB', 'MAR', 'ABR', 'MAY', 'JUN',
         'JUL', 'AGO', 'SEP', 'OCT', 'NOV', 'DIC']
MAX_MESES = 12

TIPOS_INGRESOS = ('income', 'income_other')
TIPOS_GASTOS = ('expense', 'expense_depreciation', 'expense_direct_cost')
TIPOS_RESULTADOS = TIPOS_INGRESOS + TIPOS_GASTOS

SECCIONES = [
    ('ingresos', 'INGRESOS'),
    ('costos', 'COSTO DE VENTAS'),
    ('gastos', 'GASTOS'),
]


def a_fecha(valor):
    if not valor:
        return False
    if isinstance(valor, str):
        return date.fromisoformat(valor[:10])
    return valor


def inicio_mes(f):
    return f.replace(day=1)


def fin_mes(f):
    return (f.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)


def meses_entre(desde, hasta):
    """Lista de primeros de mes desde el mes de `desde` hasta el de `hasta`."""
    meses = []
    m = inicio_mes(desde)
    while m <= hasta:
        meses.append(m)
        m = fin_mes(m) + timedelta(days=1)
    return meses


def titulo_mes(m):
    return '{}-{}'.format(MESES[m.month - 1], m.year)


def columnas(modo, desde, hasta):
    """
    Columnas de valores (sin las de %). Cada una: titulo, meses que suma
    (primeros de mes) y si lleva columna % a la derecha.
    La última siempre es el Total del rango.
    """
    desde, hasta = a_fecha(desde), a_fecha(hasta)
    todos = meses_entre(desde, hasta)
    total = {'titulo': 'Total', 'meses': todos, 'pct': False}
    if modo == 'por_mes':
        cols = [{'titulo': titulo_mes(m), 'meses': [m], 'pct': False} for m in todos]
        return cols + [total]
    if modo == 'acumulativo':
        total['pct'] = True
        return [
            {'titulo': 'Acumulado', 'meses': todos[:-1], 'pct': False},
            {'titulo': 'Mes', 'meses': todos[-1:], 'pct': True},
            total,
        ]
    total['titulo'] = 'Saldo'
    return [total]


def encabezados(cols):
    res = []
    for c in cols:
        res.append(c['titulo'])
        if c['pct']:
            res.append('%')
    return res


def seccion(account_type, codigo):
    """ingresos, costos o gastos. Las cuentas que empiezan en 5 son costo
    aunque su tipo sea 'expense' (así están los catálogos de SOLUCONTA)."""
    if account_type in TIPOS_INGRESOS:
        return 'ingresos'
    if account_type == 'expense_direct_cost' or (codigo or '').startswith('5'):
        return 'costos'
    if account_type in TIPOS_GASTOS:
        return 'gastos'
    return False


def llave_orden(codigo):
    """'6.2.01.12' -> ['6', '2', '01', '12']; así 6.x va antes que 611510."""
    return (codigo or '').split('.')


def construir(cuentas, movimientos, modo, desde, hasta):
    """
    cuentas:     {account_id: {'codigo', 'nombre', 'account_type'}}
    movimientos: [{'account_id', 'mes' (primero de mes), 'debe', 'haber'}]

    Devuelve columnas, resumen, secciones (con filas agrupadas) y los
    totales del período completo (para el Balance General).
    """
    cols = columnas(modo, desde, hasta)
    n = len(cols)
    indice_mes = {}
    for i, c in enumerate(cols):
        for m in c['meses']:
            indice_mes.setdefault(m, []).append(i)

    # Saldo por cuenta y columna, con el signo natural de su sección
    saldos = {}
    for mv in movimientos:
        cta = cuentas.get(mv['account_id'])
        if not cta:
            continue
        sec = seccion(cta['account_type'], cta['codigo'])
        if not sec:
            continue
        neto = float(mv['debe'] or 0) - float(mv['haber'] or 0)
        if sec == 'ingresos':
            neto = -neto
        fila = saldos.setdefault(mv['account_id'], [0.0] * n)
        for i in indice_mes.get(a_fecha(mv['mes']), []):
            fila[i] += neto

    totales = {s: [0.0] * n for s, _t in SECCIONES}
    secciones = []
    for sec, titulo in SECCIONES:
        hojas = [(aid, cuentas[aid]) for aid in saldos
                 if seccion(cuentas[aid]['account_type'], cuentas[aid]['codigo']) == sec]
        filas = []
        for aid, cta in hojas:
            vals = saldos[aid]
            for k in range(n):
                totales[sec][k] += vals[k]
            filas.append({'codigo': cta['codigo'], 'nombre': cta['nombre'],
                          'valores': list(vals)})
        filas.sort(key=lambda f: llave_orden(f['codigo']))
        secciones.append({'clave': sec, 'titulo': titulo, 'filas': filas,
                          'total': totales[sec]})

    ing, cos, gas = totales['ingresos'], totales['costos'], totales['gastos']
    bruta = [ing[k] - cos[k] for k in range(n)]
    neta = [bruta[k] - gas[k] for k in range(n)]
    resumen = [
        {'etiqueta': 'Ingresos', 'valores': ing, 'negrita': False},
        {'etiqueta': '(-) Costo de ventas', 'valores': cos, 'negrita': False},
        {'etiqueta': 'Utilidad bruta', 'valores': bruta, 'negrita': True},
        {'etiqueta': '(-) Gastos', 'valores': gas, 'negrita': False},
        {'etiqueta': 'Utilidad neta', 'valores': neta, 'negrita': True},
    ]

    return {
        'columnas': cols,
        'encabezados': encabezados(cols),
        'resumen': resumen,
        'secciones': secciones,
        'ingresos_col': ing,
        'total_ingresos': ing[-1],
        'total_costos': cos[-1],
        'total_gastos': gas[-1],
        'utilidad_bruta': bruta[-1],
        'utilidad_neta': neta[-1],
    }


def celdas(valores, cols, ingresos_col):
    """Valores intercalados con su % (sobre los ingresos de esa columna)."""
    res = []
    for k, c in enumerate(cols):
        res.append({'v': valores[k], 'pct': False})
        if c['pct']:
            base = ingresos_col[k]
            res.append({'v': (valores[k] / base * 100.0) if base else 0.0, 'pct': True})
    return res


def formato(valor, pct=False):
    """1,234.56 / (1,234.56) / 12.3"""
    if pct:
        return '{:,.1f}'.format(valor)
    if valor < -0.005:
        return '({:,.2f})'.format(-valor)
    return '{:,.2f}'.format(abs(valor) if abs(valor) < 0.005 else valor)
