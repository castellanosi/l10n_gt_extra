# -*- encoding: utf-8 -*-
# PARCHE_BALANZA_V2
from odoo import api, models, fields


def _to_str(val, lang='en_US'):
    """Odoo 18: campos traducibles desde SQL raw pueden ser dict (JSONB)."""
    if isinstance(val, dict):
        return val.get(lang) or val.get('en_US') or next(iter(val.values()), '')
    return val or ''


# Tipos de cuenta agrupados por naturaleza del estado financiero
TIPOS_BALANCE = [
    'asset_receivable', 'asset_cash', 'asset_current', 'asset_non_current',
    'asset_prepayments', 'asset_fixed', 'liability_payable',
    'liability_credit_card', 'liability_current', 'liability_non_current',
    'equity', 'equity_unaffected',
]
TIPOS_RESULTADOS = [
    'income', 'income_other', 'expense', 'expense_depreciation',
    'expense_direct_cost',
]


class ReporteBalanceSaldos(models.AbstractModel):
    _name = 'report.l10n_gt_extra.reporte_balance_saldos'
    _description = 'Balance de Saldos (Balanza de Comprobación)'

    # -----------------------------------------------------------------------
    # Saldo anterior
    # -----------------------------------------------------------------------
    def _saldo_anterior(self, account_id, fecha_desde):
        """Compatibilidad hacia atrás. Calcula el saldo anterior de UNA cuenta.

        Se conserva por si algún otro reporte o personalización lo invoca.
        La ruta interna del reporte usa _saldos_anteriores() (por lotes).
        """
        return self._saldos_anteriores([account_id], fecha_desde).get(account_id, 0.0)

    def _saldos_anteriores(self, account_ids, fecha_desde):
        """Calcula el saldo anterior de VARIAS cuentas en 2 consultas.

        Reglas contables:
          - Cuentas de balance (include_initial_balance = True):
                acumulan desde siempre hasta fecha_desde (exclusiva).
          - Cuentas de resultado (include_initial_balance = False):
                acumulan desde el 1 de enero del año de fecha_desde,
                porque el resultado se cierra cada ejercicio.
        """
        saldos = {aid: 0.0 for aid in account_ids}
        if not account_ids:
            return saldos

        company_id = self.env.company.id
        fecha = fields.Date.from_string(fecha_desde)
        inicio_anio = fecha.strftime('%Y-01-01')

        cuentas = self.env['account.account'].browse(account_ids)
        ids_acumulan = [c.id for c in cuentas if c.include_initial_balance]
        ids_anuales = [c.id for c in cuentas if not c.include_initial_balance]

        # --- Cuentas de balance: todo el histórico ---------------------------
        if ids_acumulan:
            self.env.cr.execute(
                "SELECT account_id, COALESCE(SUM(debit) - SUM(credit), 0) AS saldo "
                "FROM account_move_line "
                "WHERE account_id IN %s "
                "AND parent_state = 'posted' "
                "AND company_id = %s "
                "AND date < %s "
                "GROUP BY account_id",
                (tuple(ids_acumulan), company_id, fecha_desde)
            )
            for fila in self.env.cr.dictfetchall():
                saldos[fila['account_id']] = fila['saldo']

        # --- Cuentas de resultado: solo el ejercicio en curso ----------------
        if ids_anuales:
            self.env.cr.execute(
                "SELECT account_id, COALESCE(SUM(debit) - SUM(credit), 0) AS saldo "
                "FROM account_move_line "
                "WHERE account_id IN %s "
                "AND parent_state = 'posted' "
                "AND company_id = %s "
                "AND date >= %s AND date < %s "
                "GROUP BY account_id",
                (tuple(ids_anuales), company_id, inicio_anio, fecha_desde)
            )
            for fila in self.env.cr.dictfetchall():
                saldos[fila['account_id']] = fila['saldo']

        return saldos

    # -----------------------------------------------------------------------
    # Selección de cuentas
    # -----------------------------------------------------------------------
    def _tipos_filtrados(self, filtro_tipo):
        """Devuelve la lista de account_type según el filtro, o None si todas."""
        if filtro_tipo == 'balance':
            return TIPOS_BALANCE
        if filtro_tipo == 'resultados':
            return TIPOS_RESULTADOS
        return None

    def _cuentas_catalogo(self, filtro_tipo):
        """IDs de TODAS las cuentas activas y no obsoletas de la compañía.

        Se usa la ORM (no SQL) porque en Odoo 18 las cuentas pueden compartirse
        entre compañías y las reglas de registro resuelven eso correctamente.
        """
        dominio = [('deprecated', '=', False)]
        tipos = self._tipos_filtrados(filtro_tipo)
        if tipos:
            dominio.append(('account_type', 'in', tipos))
        return self.env['account.account'].search(dominio).ids

    # -----------------------------------------------------------------------
    # Construcción de líneas
    # -----------------------------------------------------------------------
    def lineas(self, datos):
        totales = {
            'saldo_anterior': 0, 'debe': 0, 'haber': 0,
            'saldo_deudor': 0, 'saldo_acreedor': 0,
        }

        filtro_tipo = datos.get('filtro_tipo', 'todas')
        incluir_cero = bool(datos.get('incluir_cuentas_cero', False))
        fecha_desde = datos['fecha_desde']
        fecha_hasta = datos['fecha_hasta']
        company_id = self.env.company.id

        tipos = self._tipos_filtrados(filtro_tipo)
        where_tipo = ''
        params_tipo = ()
        if tipos:
            where_tipo = 'AND a.account_type IN %s '
            params_tipo = (tuple(tipos),)

        # --- 1) Movimiento dentro del período --------------------------------
        self.env.cr.execute(
            "SELECT a.id, a.name, "
            "COALESCE(SUM(l.debit),0) AS debe, COALESCE(SUM(l.credit),0) AS haber "
            "FROM account_move_line l "
            "JOIN account_account a ON l.account_id = a.id "
            "WHERE l.parent_state = 'posted' "
            "AND l.date >= %s AND l.date <= %s "
            "AND l.company_id = %s "
            + where_tipo +
            "GROUP BY a.id, a.name",
            (fecha_desde, fecha_hasta, company_id) + params_tipo
        )
        rows = self.env.cr.dictfetchall()
        movimientos = {r['id']: r for r in rows}

        # --- 2) Cuentas SIN movimiento en el período -------------------------
        # Se agregan como candidatas con debe = haber = 0. Más abajo se
        # descartan si además su saldo anterior es cero (salvo incluir_cero).
        if incluir_cero:
            candidatas = set(self._cuentas_catalogo(filtro_tipo))
        else:
            # Solo las que tienen historial previo: pueden arrastrar saldo.
            self.env.cr.execute(
                "SELECT DISTINCT a.id "
                "FROM account_move_line l "
                "JOIN account_account a ON l.account_id = a.id "
                "WHERE l.parent_state = 'posted' "
                "AND l.date < %s "
                "AND l.company_id = %s "
                + where_tipo,
                (fecha_desde, company_id) + params_tipo
            )
            candidatas = {f['id'] for f in self.env.cr.dictfetchall()}

        ids_faltantes = [i for i in candidatas if i not in movimientos]

        # --- 3) Nombres de las cuentas faltantes ------------------------------
        if ids_faltantes:
            self.env.cr.execute(
                "SELECT id, name FROM account_account WHERE id IN %s",
                (tuple(ids_faltantes),)
            )
            for fila in self.env.cr.dictfetchall():
                movimientos[fila['id']] = {
                    'id': fila['id'], 'name': fila['name'],
                    'debe': 0.0, 'haber': 0.0,
                }

        # --- 4) Saldos anteriores en lote ------------------------------------
        ids_todas = list(movimientos.keys())
        saldos_ant = self._saldos_anteriores(ids_todas, fecha_desde)

        # --- 5) Armado final --------------------------------------------------
        lang = self.env.lang or 'en_US'
        cuentas = {a.id: a for a in self.env['account.account'].browse(ids_todas)}

        lineas = []
        for r in movimientos.values():
            saldo_ant = saldos_ant.get(r['id'], 0.0)
            debe = r['debe']
            haber = r['haber']

            # Cuenta totalmente vacía: se omite salvo que se pidan las de cero.
            if not incluir_cero and not saldo_ant and not debe and not haber:
                continue

            cuenta = cuentas.get(r['id'])
            codigo = cuenta.code if cuenta and cuenta.code else ''
            nombre = _to_str(r['name'], lang)
            saldo_final = saldo_ant + debe - haber

            lineas.append({
                'codigo': codigo,
                'cuenta': nombre,
                'saldo_anterior': saldo_ant,
                'debe': debe,
                'haber': haber,
                'saldo_deudor': saldo_final if saldo_final > 0 else 0,
                'saldo_acreedor': -saldo_final if saldo_final < 0 else 0,
            })
            totales['saldo_anterior'] += saldo_ant
            totales['debe'] += debe
            totales['haber'] += haber
            totales['saldo_deudor'] += saldo_final if saldo_final > 0 else 0
            totales['saldo_acreedor'] += -saldo_final if saldo_final < 0 else 0

        lineas = sorted(lineas, key=lambda l: l['codigo'] or l['cuenta'])
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
