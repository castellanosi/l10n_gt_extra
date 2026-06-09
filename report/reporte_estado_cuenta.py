# -*- encoding: utf-8 -*-
import re
from odoo import api, models


def _strip_html(val):
    """Limpia etiquetas HTML del campo narration (Html field en Odoo 18)."""
    if not val:
        return ''
    if isinstance(val, dict):
        val = val.get('en_US') or val.get('es_GT') or next(iter(val.values()), '')
    return re.sub(r'<[^>]+>', '', str(val)).strip()


def _jsonb_str(val):
    if not val:
        return ''
    if isinstance(val, dict):
        return val.get('en_US') or val.get('es_GT') or next(iter(val.values()), '')
    return str(val)


class ReporteEstadoCuenta(models.AbstractModel):
    _name = 'report.l10n_gt_extra.reporte_estado_cuenta'
    _description = 'Estado de Cuenta por Cliente / Proveedor'

    def saldo_anterior(self, datos):
        partner_id = datos['partner_id'][0]
        self.env.cr.execute(
            "SELECT COALESCE(SUM(l.debit) - SUM(l.credit), 0) AS saldo "
            "FROM account_move_line l "
            "JOIN account_account a ON l.account_id = a.id "
            "WHERE l.partner_id = %s AND l.parent_state = 'posted' "
            "AND l.date < %s AND l.company_id = %s "
            "AND a.account_type IN ('asset_receivable','liability_payable')",
            (partner_id, datos['fecha_desde'], self.env.company.id)
        )
        row = self.env.cr.dictfetchone()
        return row['saldo'] if row else 0

    def _retenciones_de_factura(self, move_id, numero_retencion):
        self.env.cr.execute("""
            SELECT ml.name AS linea_nombre,
                   ml.debit, ml.credit,
                   a.name  AS cuenta_nombre
            FROM account_move_line ml
            JOIN account_account a ON ml.account_id = a.id
            WHERE ml.move_id = %s
              AND a.account_type NOT IN ('asset_receivable','liability_payable')
              AND (LOWER(a.name::text)  LIKE '%%retenci%%'
                   OR LOWER(ml.name::text) LIKE '%%retenci%%')
              AND (ml.debit > 0 OR ml.credit > 0)
            ORDER BY ml.id
        """, (move_id,))
        rows = self.env.cr.dictfetchall()
        result = []
        for r in rows:
            nombre = _jsonb_str(r['linea_nombre']) or _jsonb_str(r['cuenta_nombre'])
            result.append({
                'nombre':    nombre,
                'debe':      r['debit'],
                'haber':     r['credit'],
                'monto':     r['debit'] + r['credit'],
                'numero':    numero_retencion or '',
                'sub_saldo': 0,
            })
        return result

    def _pagos_de_linea(self, line_id):
        self.env.cr.execute("""
            SELECT
                pr.amount,
                CASE WHEN pr.debit_move_id = %(lid)s
                     THEN ml_c.date ELSE ml_d.date END AS fecha_pago,
                CASE WHEN pr.debit_move_id = %(lid)s
                     THEN m_c.name  ELSE m_d.name  END AS doc_pago,
                CASE WHEN pr.debit_move_id = %(lid)s
                     THEN COALESCE(m_c.payment_reference, m_c.ref,
                                   ml_c.name::text, m_c.name::text)
                     ELSE COALESCE(m_d.payment_reference, m_d.ref,
                                   ml_d.name::text, m_d.name::text)
                END AS concepto_pago,
                CASE WHEN pr.debit_move_id = %(lid)s
                     THEN 'haber' ELSE 'debe' END AS lado
            FROM account_partial_reconcile pr
            LEFT JOIN account_move_line ml_c ON pr.credit_move_id = ml_c.id
            LEFT JOIN account_move      m_c  ON ml_c.move_id = m_c.id
            LEFT JOIN account_move_line ml_d ON pr.debit_move_id  = ml_d.id
            LEFT JOIN account_move      m_d  ON ml_d.move_id = m_d.id
            WHERE pr.debit_move_id  = %(lid)s
               OR pr.credit_move_id = %(lid)s
            ORDER BY fecha_pago
        """, {'lid': line_id})
        rows = self.env.cr.dictfetchall()
        result = []
        for r in rows:
            result.append({
                'fecha':     r['fecha_pago'],
                'documento': _jsonb_str(r['doc_pago']),
                'concepto':  _jsonb_str(r['concepto_pago']),
                'monto':     r['amount'],
                'lado':      r['lado'],
                'sub_saldo': 0,
            })
        return result

    def lineas(self, datos):
        partner_id = datos['partner_id'][0]
        company_id = self.env.company.id

        TIPOS_DEBE    = ('out_invoice', 'in_refund')
        TIPOS_HABER   = ('in_invoice',  'out_refund')
        INVOICE_TYPES = TIPOS_DEBE + TIPOS_HABER

        self.env.cr.execute("""
            SELECT l.id, l.date, l.debit, l.credit,
                   m.name AS documento, m.move_type,
                   l.ref, l.name AS linea_name,
                   m.payment_reference, m.id AS move_id,
                   COALESCE(m.numero_retencion, '') AS numero_retencion,
                   COALESCE(m.ref, '') AS move_ref,
                   COALESCE(bsl.payment_ref, '') AS bank_ref,
                   COALESCE(m.narration, '') AS move_narration
            FROM account_move_line l
            JOIN account_account a ON l.account_id = a.id
            JOIN account_move    m ON l.move_id = m.id
            LEFT JOIN account_bank_statement_line bsl ON bsl.move_id = m.id
            WHERE l.partner_id   = %s
              AND l.parent_state = 'posted'
              AND l.date        >= %s
              AND l.date        <= %s
              AND l.company_id  = %s
              AND a.account_type IN ('asset_receivable','liability_payable')
            ORDER BY l.date, m.name
        """, (partner_id, datos['fecha_desde'], datos['fecha_hasta'], company_id))

        rows    = self.env.cr.dictfetchall()
        sal_ant = self.saldo_anterior(datos)
        saldo   = sal_ant

        # Totales acumula columnas visibles (incluyendo retenciones sub-filas)
        # Las retenciones NO aparecen como filas principales (van a cuentas distintas
        # a CxC/CxP), por eso se suman aquí.
        # Los pagos SÍ aparecen como filas principales, así que NO se suman en sub-filas.
        tot_debe  = 0
        tot_haber = 0
        lineas    = []

        for r in rows:
            move_type  = r['move_type']
            es_factura = move_type in INVOICE_TYPES
            es_haber   = move_type in TIPOS_HABER
            retenciones, pagos = [], []

            if es_factura:
                # Obtener retenciones primero para calcular importe bruto
                retenciones = self._retenciones_de_factura(
                    r['move_id'], r['numero_retencion']
                )
                pagos = []  # los pagos ya aparecen como filas principales

                # Importe bruto = neto CxC/CxP + retenciones
                neto      = r['debit'] + r['credit']
                total_ret = sum(ret['monto'] for ret in retenciones)
                original  = neto + total_ret

                if es_haber:
                    saldo -= original
                    disp_debe, disp_haber = 0, original
                else:
                    saldo += original
                    disp_debe, disp_haber = original, 0

                tot_debe  += disp_debe
                tot_haber += disp_haber

                # Sumar retenciones a los totales de columna
                # El template invierte ret: ret['haber'] va a Debe, ret['debe'] va a Haber
                for ret in retenciones:
                    tot_debe  += ret['haber']   # columna Debe del reporte
                    tot_haber += ret['debe']    # columna Haber del reporte

                # Calcular sub_saldo: empieza en bruto, descuenta cada documento
                sub = -original if es_haber else original
                for ret in retenciones:
                    sub = sub + ret['monto'] if es_haber else sub - ret['monto']
                    ret['sub_saldo'] = sub
                for pago in pagos:
                    sub = sub + pago['monto'] if es_haber else sub - pago['monto']
                    pago['sub_saldo'] = sub

            else:
                # Pagos y asientos varios
                saldo += r['debit'] - r['credit']
                disp_debe, disp_haber = r['debit'], r['credit']
                tot_debe  += r['debit']
                tot_haber += r['credit']

            if es_factura:
                # Facturas: referencia externa FEL o número de factura proveedor
                documento_ext = (
                    _jsonb_str(r['move_ref']) or           # m.ref: UUID FEL o # factura proveedor
                    _jsonb_str(r['payment_reference']) or
                    _jsonb_str(r['documento'])             # fallback: correlativo Odoo
                )
                concepto = (
                    _jsonb_str(r['linea_name']) or
                    _jsonb_str(r['ref']) or
                    ''
                )
            else:
                # Pagos / banco:
                # Documento = m.ref (número de referencia bancaria: 25252525, DEP-001, etc.)
                documento_ext = (
                    _jsonb_str(r['move_ref']) or           # m.ref: número ref. banco (PRIMERO)
                    _jsonb_str(r['bank_ref']) or           # bsl.payment_ref: descripción banco
                    _jsonb_str(r['payment_reference']) or
                    _jsonb_str(r['documento'])             # fallback: correlativo Odoo
                )
                # Concepto = descripción banco + referencia de línea combinadas
                bank_desc = _jsonb_str(r['bank_ref']) or _strip_html(r['move_narration']) or ''
                line_desc = _jsonb_str(r['linea_name']) or _jsonb_str(r['ref']) or ''
                partes = [p for p in [bank_desc, line_desc] if p]
                concepto = ' — '.join(partes) if partes else ''

            lineas.append({
                'fecha':       r['date'],
                'documento':   documento_ext,
                'concepto':    concepto,
                'debe':        disp_debe,
                'haber':       disp_haber,
                'saldo':       saldo,
                'tipo':        'factura' if es_factura else 'pago',
                'retenciones': retenciones,
                'pagos':       pagos,
            })

        # Saldo total = saldo_anterior + Debe - Haber  (lógica contable)
        totales = {
            'debe':  tot_debe,
            'haber': tot_haber,
            'saldo': sal_ant + tot_debe - tot_haber,
        }
        return {'lineas': lineas, 'totales': totales}

    @api.model
    def _get_report_values(self, docids, data=None):
        model   = self.env.context.get('active_model')
        docs    = self.env[model].browse(self.env.context.get('active_ids', []))
        partner = self.env['res.partner'].browse(data['form']['partner_id'][0])
        return {
            'doc_ids':            self.ids,
            'doc_model':          model,
            'data':               data['form'],
            'docs':               docs,
            'partner':            partner,
            'lineas':             self.lineas,
            'saldo_anterior':     self.saldo_anterior,
            'current_company_id': self.env.company,
        }
