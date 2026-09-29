# -*- encoding: utf-8 -*-
"""Lectura común de líneas contables una a una (modo detallado de diario y mayor)."""


def lineas_contables(env, datos):
    """
    Devuelve las líneas publicadas de las cuentas elegidas, en el rango de
    fechas, ordenadas por fecha, asiento y línea: la misma información que
    Contabilidad > Asientos contables, sin agrupar.
    """
    cuentas = datos['cuentas_id']
    if not cuentas:
        return []
    env.cr.execute(
        "SELECT l.id, l.date, l.account_id, l.move_id, l.partner_id, l.journal_id, "
        "l.name AS etiqueta, l.debit, l.credit "
        "FROM account_move_line l "
        "JOIN account_move m ON m.id = l.move_id "
        "WHERE l.parent_state = 'posted' "
        "AND l.account_id IN %s "
        "AND l.date >= %s AND l.date <= %s "
        "ORDER BY l.date, m.name, l.id",
        (tuple(cuentas), datos['fecha_desde'], datos['fecha_hasta']),
    )
    filas = env.cr.dictfetchall()

    # Nombres por ORM, una sola vez (código de cuenta y nombres traducibles)
    Cuenta = env['account.account'].browse(list({f['account_id'] for f in filas}))
    Asiento = env['account.move'].browse(list({f['move_id'] for f in filas}))
    Tercero = env['res.partner'].browse(list({f['partner_id'] for f in filas if f['partner_id']}))
    Diario = env['account.journal'].browse(list({f['journal_id'] for f in filas}))
    cuentas_d = {c.id: c for c in Cuenta}
    asientos_d = {a.id: a for a in Asiento}
    terceros_d = {t.id: t.name for t in Tercero}
    diarios_d = {d.id: d.name for d in Diario}

    campos = env['account.move']._fields
    fel_nuevo = all(c in campos for c in ('l10n_gt_fel_uuid', 'l10n_gt_fel_serie', 'l10n_gt_fel_numero'))
    fel_antiguo = all(c in campos for c in ('firma_fel', 'serie_fel', 'numero_fel'))

    def documento(a):
        if fel_nuevo and a.l10n_gt_fel_uuid:
            return '%s-%s' % (a.l10n_gt_fel_serie or '', a.l10n_gt_fel_numero or '')
        if fel_antiguo and a.firma_fel:
            return '%s-%s' % (a.serie_fel or '', a.numero_fel or '')
        return a.ref or ''

    resultado = []
    for f in filas:
        c = cuentas_d[f['account_id']]
        a = asientos_d[f['move_id']]
        etiqueta = f['etiqueta']
        if isinstance(etiqueta, dict):
            etiqueta = etiqueta.get('es_GT') or etiqueta.get('en_US') or next(iter(etiqueta.values()), '')
        resultado.append({
            'fecha': f['date'],
            'cuenta_id': c.id,
            'codigo': c.code,
            'cuenta': c.name,
            'asiento_id': a.id,
            'asiento': a.name,
            'documento': documento(a),
            'diario': diarios_d.get(f['journal_id'], ''),
            'tercero': terceros_d.get(f['partner_id'], ''),
            'etiqueta': etiqueta or '',
            'debe': f['debit'],
            'haber': f['credit'],
        })
    return resultado
