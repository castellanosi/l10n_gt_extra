# CLAUDE.md — castellanosi/l10n_gt_extra

> Contexto de este módulo para el asistente. Raíz del repo:
> `/opt/odoo-docker/addons/l10n_gt_extra/CLAUDE.md`.
> Se trabaja junto con `PROTOCOLO-ENTREGAS.md` (cómo se entregan,
> aplican, prueban y suben los cambios).

---

## 0. Qué es y regla que manda sobre todo

Extensión de la localización oficial de Guatemala (`l10n_gt`) para
Odoo 18/19 CE: reportes SAT (libros), estados financieros, CxC/CxP,
estado de cuenta, retenciones y conciliación bancaria.

- **Versión:** `18.0.5.66` (en producción desde 23/11/2026, tag `v18.0.5.66`; probada con Super Mas & Ahorro oct. 2026: IVA 37,904.74 = hoja SAT). En producción en las 4 bases de
  SOLUCONTA (`conta_exlin`, `conta_gen`, `conta_ic`, `conta_mlopez`).
- **Ramas:** `18.0` (estable), `test` (pruebas), `19.0`. Flujo:
  `feature/* → test → 18.0`, con tag de versión al llevar a `18.0`.
- **Depende de:** `l10n_gt`, `account`.

**Este módulo está instalado en varios servidores de producción, con
empresas en régimen general y en pequeño contribuyente, con y sin
integrador FEL.** Por eso:

- **No añadir dependencias** en `__manifest__.py`: ni `l10n_gt_peq`,
  ni `gt_tax_regime`, ni `solucloud-odoo`, ni `odoo_fel_integrador`,
  ni `l10n_gt_fel_*`.
- Campos de otros módulos se leen **solo si existen**:
  `'campo' in Model._fields`, calculado **una vez** antes del bucle.
  Nunca `fields_get()` dentro de un bucle (fue la causa de la lentitud).
- Sin el integrador FEL, cada reporte debe dar **el mismo resultado**
  que antes de estos cambios.

(En v5.46 se rompió la independencia con `gt_tax_regime`; no repetir.)

---

## 1. Compatibilidad con los dos integradores FEL

| Dato | Integrador antiguo | `odoo_fel_integrador` |
|---|---|---|
| Firmado | `firma_fel` | `l10n_gt_fel_uuid` |
| Serie / número | `serie_fel` / `numero_fel` | `l10n_gt_fel_serie` / `l10n_gt_fel_numero` |
| Tipo de DTE | — | `l10n_gt_fel_dte_code` |
| Estado FEL | — | `l10n_gt_fel_state` (`borrador`, `enviando`, `certificado`, `error`, `anulado`) |

Los reportes entienden los dos, sin depender de ninguno.

**Bases de SOLUCONTA (importador de XML):** usan `firma_fel`,
`serie_fel`, `numero_fel` como el integrador antiguo. **No guardan el
tipo real de cada DTE**: `fel_tipo_documento` y `fel_afiliacion_iva`
existen, pero son **calculados por `l10n_gt_peq`** desde el régimen de
la empresa (`_compute_fel_fields`), no desde el documento. En 5.51 se
leyeron y el libro de compras de una empresa PEQ salió todo `FPEQ`; se
revirtió en 5.52. **No volver a usarlos.** Las compras tampoco tienen el
XML adjunto.

El tipo de DTE se obtiene con `campos_tipo_dte()` + `codigo_dte()` de
`report/tipos_dte.py` (hoy solo `l10n_gt_fel_dte_code`). Cuando el
importador guarde el tipo real en un campo propio, agregarlo a
`CAMPOS_TIPO_DTE`.

`report/tipos_dte.py` tiene el catálogo de los 18 tipos de DTE del
manual FEL de la SAT (FACT, FCAM, FPEQ, FCAP, FESP, NABN, RDON, RECI,
NDEB, NCRE, FACA, FCCA, FAPE, FCPE, FAAE, FCAE, CIVA, CAIS). Un código
fuera de la lista se ignora y se usa la lógica anterior.

---

## 2. Estado actual de los reportes (v5.50)

### Libros de ventas y compras
- **Los dos libros van por la fecha del documento** (`invoice_date`):
  compras desde 5.62, ventas desde 5.66. **Nunca** por fecha contable
  (`date`) en ningún reporte nuevo: decisión del usuario del 20/11/2026
  (se registra el 31 una factura del 11 y por `date` el rango 1–11 salía
  vacío).
- **IVA del DTE (5.66).** Si el importador está instalado
  (`gt_dte_iva`, `gt_dte_total` en `_fields`) y la factura vigente tiene
  `gt_dte_total` ≠ 0, la fila se calcula como siempre y luego
  `aplicar_dte()` (`report/libro_montos.py`) corrige SOLO la diferencia
  de IVA (IVA DTE − IVA calculado), restándola de la columna gravada
  mayor. Si el total de la fila no queda igual al Gran Total del DTE, o la
  diferencia pasa de Q1.00, la fila queda como se calculó y sale como
  hallazgo en el pie. **Nunca** base = total − IVA: el Gran Total incluye
  otros impuestos. En compras no se aplica a documentos sin crédito fiscal
  (PEQ, EXE, RECI…): siguen todo en exento.
- **Contrato con el importador** (`odoo_gt_importer`, campos en
  `account.move`, sin dependencia en el manifiesto): `gt_dte_total`,
  `gt_dte_iva`, `gt_dte_iva_origen` (≥ 18.0.1.8.0), `gt_dte_otros_impuestos`
  (≥ 18.0.1.9.0). Siempre positivos; el signo lo da `move_type`. NULL en lo
  importado antes de esas versiones (el ORM lo lee como 0 = «vacío»).
- **Impuestos y contribuciones (5.66):** columna nueva en compras y
  ventas, antes de IVA. Lleva los impuestos de Odoo distintos del IVA
  elegido (antes iban a exento) y, si el DTE trae
  `gt_dte_otros_impuestos`, ese monto pasado desde la columna exenta (la
  línea «Otros impuestos: …» que crea el importador). Fila: total =
  gravado + exento + impuestos y contribuciones + IVA. La columna «Imp.»
  de compras es **Importaciones**: su encabezado pasó a «Import.» para no
  confundirla.
- **Moneda extranjera (5.66):** los `gt_dte_*` vienen en la moneda de la
  factura y se convierten con el tipo de cambio **del propio asiento**
  (`abs(amount_total_signed) / amount_total`), redondeado a 2 decimales
  por documento. Nunca una tasa aparte. Libro de varias compañías: la tasa
  entre compañías se MULTIPLICA por la de la factura (antes la reemplazaba).
- **Decimales (5.66):** todo con `Decimal`; cada monto de la fila se
  redondea a 2 decimales y los totales son la suma de las filas
  redondeadas. El Excel (`wizard/libro_excel.py`, común a los dos libros)
  escribe cada número redondeado con `#,##0.00` y muestra todas las
  columnas (combustible en ventas).
- **Pie «Control» (5.66, solo informativo):** sale SOLO si el contador
  marca la casilla «Incluir control» del asistente (desmarcada por defecto:
  el libro oficial se imprime sin él; decisión del 23/11/2026). Muestra IVA
  del libro, IVA contable de esas mismas facturas (líneas de impuesto del
  IVA elegido, solo documentos con IVA en el libro) y la diferencia
  separada en dos: **redondeo del IVA de los DTE** (centavos, «se ajusta en
  la liquidación de IVA») y **otras diferencias** (en rojo, con la lista de
  documentos cuyo IVA calculado difiere del asiento en más de Q0.05: revisar
  antes de declarar). Avisos: facturas importadas sin datos del DTE (solo
  las que llevan IVA; no sale en PEQ/exentos), DTE con IVA de más de 2
  decimales, borradores del periodo y hallazgos. En el Excel, hoja
  «Control» con el detalle. **No hay póliza de ajuste** (decisión del
  20/11/2026).
- Cada fila lleva `move_id` (lo usan las pruebas; no se imprime).
- **Tipo:** el código de DTE (`FPEQ`, `NCRE`…) si la factura lo tiene;
  si no, la lógica anterior (`FACT`/`NC`/`ND`). Hay dos variables:
  `tipo` (interna, decide el signo de las NC) y `tipo_mostrar` (lo que
  se imprime). **No mezclarlas.**
- **Doc:** `serie-número` del DTE; si no, las ramas de siempre
  (rangos, referencia, gface, `firma_fel`, tickets con resolución).
- **Anuladas:** si `state == 'cancel'` **o** `l10n_gt_fel_state ==
  'anulado'`, la línea aparece con fecha, tipo y serie-número, montos
  en cero y `(ANULADA)` en la columna Doc. Compras ahora incluye las
  canceladas (antes las omitía).
- **Gravado/exento:** depende del impuesto elegido en el asistente. Para
  pequeño contribuyente se usa un impuesto «PEQ» de 0 %; seleccionando
  PEQ salen en «VENT.» con IVA 0. Aprobado por el usuario; no cambiar.
- **Columna Bienes/Servicios (5.63):** la decide `columna_linea()` en
  `report/tipos_dte.py`. Con `tipo_gasto` fijo manda la factura. Con
  `mixto`: si la línea tiene producto, manda el tipo del producto; si no
  tiene producto y trae `gt_bien_servicio` (`B`/`S`, de `gt_xml_importer`),
  manda ese campo; si no, Bienes (como antes). El campo se detecta una vez
  con `_fields`: sin el importador el resultado es idéntico a 5.62.
- Precálculo: campos opcionales, conjunto de ids de impuestos y tasa de
  cambio por compañía. Medido: 0.94 s → 0.05 s con 12 facturas.

### Libro diario y libro mayor
- Asistente con **Tipo de reporte** (`modo`): `resumido`, `por_dia`,
  `detallado`. `agrupado_por_dia` se conserva como campo calculado desde
  `modo` para las plantillas y el Excel anteriores.
- **Detallado:** `report/detalle_comun.py` (`lineas_contables()`) lee cada
  línea publicada de las cuentas elegidas. Diario: un bloque por asiento
  (fecha, número, documento DTE o referencia, diario) con sus líneas y
  total. Mayor: por cuenta, saldo inicial, cada movimiento con saldo
  acumulado y saldo final. Excel incluido.
- Verificado en `tienda_odoo`: con todas las cuentas, asientos, líneas,
  debe y haber idénticos a Contabilidad → Asientos contables.

### Estado de resultados y Balance General (desde 5.56)
- Asistentes con **Tipo de reporte** (`modo`, botones): `normal`,
  `por_mes`, `acumulativo`. Aviso azul en el asistente (`nota_modo`) que
  dice cuál es el «Mes» en el acumulativo.
- **Estado de resultados:** normal = una columna; por_mes = una columna
  por mes (máximo 12) y Total; acumulativo = Acumulado (meses anteriores
  del rango) | Mes (mes de la **fecha final**) | % | Total | %. El % es
  sobre los ingresos de esa columna. Si la fecha final cae a mitad de mes,
  el Mes cubre solo esos días; si no hay movimiento sale en 0.00 (decidido:
  no se cambia, se avisa).
- **Balance general:** normal = saldo al corte; por_mes = saldo al cierre
  de cada mes desde «Inicio período resultados» (máximo 12, sin Total);
  acumulativo = Saldo anterior | Mes (movimiento) | Saldo al corte. La
  utilidad de cada columna sale del ER del mismo modo
  (`utilidades_por_columna()`). Fila «Diferencia» en el resumen = cuadre.
- Los dos llevan **Resumen** y **Detalle por sección** (ER: INGRESOS,
  COSTO DE VENTAS, GASTOS; BG: ACTIVO, PASIVO, CAPITAL), cuentas ordenadas
  por código y total por sección. **Sin niveles intermedios** (4, 4.1,
  4.1.01): el usuario los descartó. Las bases de SOLUCONTA no tienen
  `account.group` y sus códigos son `4.1.01.01`.
- **Resumen y Detalle en una sola tabla** (`l10n_gt_extra.cuerpo_financiero`)
  para que las columnas se alineen. **No usar anchos fijos**: el usuario
  no los quiere (montos grandes no cabrían).
- **Costo de ventas** = `expense_direct_cost` **o** código que empieza en
  `5`. En SOLUCONTA las cuentas 5.x son de tipo `expense`: hasta 5.55 el
  costo salía en 0. La utilidad neta no cambia.
- Título: solo «del dd/mm/aaaa al dd/mm/aaaa». Negativos entre paréntesis.
  Encabezado del balance: «del inicio período resultados al corte».
  Moneda en singular («Quetzal»), aceptado. PDF horizontal salvo normal.
- Lógica pura en `report/er_columnas.py` y `report/bg_columnas.py`, con
  pruebas; Excel común `excel_financiero()` en el asistente. El balance
  ya no hace una consulta por cuenta.

### Estado de flujo de efectivo (desde 5.57)
- **Método indirecto** (NIIF para PYMES, Secc. 7). Mismos modos que el ER
  (`normal`, `por_mes`, `acumulativo`, sin %). En el Total por mes,
  «efectivo al inicio» = el del primer mes y «al final» = el del último.
- Cálculo por partida doble (`report/fe_columnas.py`): utilidad neta =
  haber − debe de las cuentas de resultados (igual al ER, hay prueba);
  cada cuenta de balance aporta haber − debe de su movimiento.
  **Comprobación** = saldo real de las cuentas de efectivo y
  **Diferencia** (debe ser 0.00): si no, hay una cuenta mal clasificada.
- Campo `account.account.l10n_gt_flujo_clase` («Clasificación en flujo de
  efectivo», en el formulario de la cuenta y opcional en la lista). Valores:
  `efectivo`, `op_cobrar`, `op_inventario`, `op_activo`, `op_pagar`,
  `op_pasivo`, `depreciacion`, `inversion`, `fin_pasivo`, `fin_capital`,
  `excluir`. **Vacío = regla por omisión solo por tipo** (`POR_TIPO`),
  salvo las **cuentas transitorias de Odoo** (recibos/pagos pendientes,
  suspenso, transferencia de liquidez, leídas de la compañía y de los
  diarios con `'campo' in _fields`), que son **efectivo** (decisión del
  usuario 07/11/2026: se liquidan casi de inmediato).
- **En SOLUCONTA los tipos no sirven** para el flujo: PPE `1.2.01.x` y
  depreciación acumulada `1.2.02.x` son `asset_current`; en `conta_gen`
  `1.2.01.04 Vehiculos` es `liability_non_current` (error de datos, avisar
  al contador). Se corrige llenando el campo en cada base (script por base,
  revisado por el contador), **nunca** con reglas por código en el módulo.
- `excluir` = cuentas que reciben el cierre del ejercicio. Si el rango
  incluye el asiento de cierre, la Diferencia lo muestra (es esperado).
- Detalle por cuenta debajo de cada renglón (casilla «Detalle por
  cuenta»). PDF horizontal salvo normal; Excel con `excel_flujo()`.

### Conciliación bancaria (desde 5.58)
- Diagnóstico 07/11/2026: OCA `account_reconcile_oca` instalado en las 4
  bases; extractos solo en `conta_ic` (229 líneas, todas conciliadas) y
  `conta_gen` (8). Todos los pagos usan el método «Manual»: **no** se puede
  distinguir por método de pago.
- **Todo movimiento de una cuenta de banco se considera cobrado**, salvo
  los marcados **en tránsito**. Se trabaja sobre la cuenta del diario de
  banco, no sobre el origen (importador, COD, botón Pagar, cheques de
  impuestos o sueldos): **no** poner la marca en el asistente de Pagar.
- Campos en `account.move.line` (cuentas de banco): «En tránsito» y
  «Fecha de cobro en banco». Pendiente al corte = en tránsito, fecha <=
  corte y (sin fecha de cobro o fecha de cobro > corte). Las líneas de
  extracto nunca están en tránsito.
- Menú **«Movimientos en tránsito»**: lista de líneas de banco con filtro
  en tránsito; ahí se marcan y se pone la fecha de cobro (acción masiva).
- Reporte: Saldo según libros + cheques en tránsito − depósitos en tránsito
  = saldo según banco (calculado); el contador **escribe** el saldo del
  estado de cuenta en el asistente (**no se guarda**) y sale la Diferencia.
- Programado: campos `l10n_gt_en_transito` y `l10n_gt_fecha_cobro` en
  `account.move.line` (poner la fecha marca en tránsito, también en edición
  masiva, vía `write`; la fecha de cobro no puede ser anterior al
  movimiento). Menú Contabilidad → **Movimientos en tránsito**
  (`asset_cash`, publicados, sin línea de extracto), lista editable con
  edición masiva, filtro por omisión «En tránsito sin cobrar». Lógica pura
  en `report/conciliacion_logica.py` con pruebas.
- Se quitó el campo «Del» del asistente (los pendientes no dependen de una
  fecha inicial) y el saldo en libros filtra por compañía.
- Empresas con extractos (OCA): los pagos quedan en «Pagos/Recibos
  pendientes» hasta conciliar en el widget; la cuenta de banco ya refleja
  el extracto. Su conciliación sigue siendo la del widget.

### Depurar documentos duplicados (desde 5.59)
- Origen: en `conta_gen` (BH Inversión) la hoja de ventas de la SAT se
  importó dos veces (23/10/2026): 8,989 ventas publicadas, 4,126 pares,
  sin pagos. Evitar la doble carga es tarea del **importador** (otro repo).
- Contabilidad → Asientos → **Depurar documentos duplicados** (solo
  `group_account_manager`). Analizar → Eliminar duplicados (lotes de 500
  por clic, commit cada 100, se repite hasta 0) → **Renumerar por fecha**
  (abre el `account.resequence.wizard` nativo con `ordering = date`; exige
  un solo diario).
- Clave: compañía + `move_type` + UUID (`firma_fel` o `l10n_gt_fel_uuid`);
  sin UUID, serie + número + NIT. Se conserva la copia con pagos, si no la
  publicada de `id` más bajo. **Nunca se borra** con pagos, hash, fecha
  bloqueada, ni si las copias difieren en NIT o total (sale «a
  revisar»). La importación por hoja también llena `firma_fel`.
- Borrado: `button_draft()`, `name = '/'` (Odoo permite borrar así lo que
  no es el final de la secuencia) y `unlink()` con `force_delete`, cada uno
  en su savepoint; el fallo se informa por documento. Nota en el chatter
  de la copia conservada. Lógica pura en `wizard/duplicados_logica.py`.
- Renumerar cambia solo el correlativo interno `INV/…`; serie y número
  FEL no cambian. Avisar al contador por si anotó números `INV/…`.
- **Se compara el NIT, no el contacto** (5.60): en `conta_gen` la doble carga
  creó dos contactos con el mismo NIT y nombre; 350 pares quedaban «a
  revisar» en 5.59. Los contactos repetidos se fusionan aparte.
- La nota en el chatter va con `_message_log`, no `message_post` (5.61):
  `message_post` exige correo del remitente y en producción el usuario no
  lo tenía; la copia sí se borraba pero salía como «a revisar».

### CUI de la empresa (desde 5.59)
- `res.company.l10n_gt_cui`, opcional, debajo del NIT. Se guarda sin
  espacios ni guiones; si se llena, 13 dígitos. Lo lee `gt_xml_importer`
  con `'l10n_gt_cui' in company._fields` para aceptar DTE facturados al CUI.

### Retenciones de IVA e ISR (desde 5.62: como pago)
**Decisión del usuario (09/11/2026):** la retención es parte del pago, no
de la factura. Se quitó todo el mecanismo de impuestos de fórmula.

- Botón **«Retención»** en facturas de cliente y de proveedor publicadas
  con saldo. **Siempre visible, sin importar el régimen** (decisión del
  usuario: hay casos en que hace falta retener aunque la regla diga que no).
- Asistente `l10n_gt_extra.registrar_retencion.wizard`: **solo** diario de
  retención (salen todos los diarios marcados; si hay uno, se elige solo),
  cuenta (solo lectura), monto, fecha y número de constancia. **El monto
  lo escribe el usuario** (el de la constancia): sin tipo, cálculo ni
  porcentaje (decisión del usuario, 10/11/2026; un primer borrador con
  cálculo sugerido se descartó). El tipo IVA/ISR sale del diario
  (`l10n_gt_retencion`) y solo se usa en el texto del pago y en el aviso
  de factura menor de Q2,500. Crea un **pago parcial** con
  `account.payment.register` (`payment_difference_handling='open'`) y lo
  concilia con la factura. No pasa la factura a borrador ni toca el DTE.
- **Diarios:** campo `account.journal.l10n_gt_retencion` (`iva`/`isr`),
  pestaña Extra, solo banco/efectivo. Un diario por tipo sirve para
  ventas y compras: la cuenta sale del método de pago — **Pagos
  entrantes** = retenciones que le hacen (activo, 1.1.03.02 / 1.1.03.03),
  **Pagos salientes** = retenciones que usted hace (pasivo, p. ej.
  2.1.02.05). Sin cuenta, el asistente lo dice y no registra (Odoo 18
  registraría sin asiento). La **cuenta de efectivo** que Odoo exige al
  diario es una cuenta puente tipo «Banco y efectivo» que queda siempre en
  cero (en `tienda_odoo`: 1.0.02.02 «Puente diarios de retención»; desde
  5.65, «Cuenta transitoria retenciones (no tocar)», ver abajo).
- **Diarios predeterminados (5.65):** `res.company._l10n_gt_crear_diarios_retencion()`
  crea la cuenta «Cuenta transitoria retenciones (no tocar)» (tipo Banco y
  efectivo, código 1.0.01.90 o el siguiente libre) y los diarios RETENCION
  IVA (`RIVA`) y RETENCION ISR (`RISR`), tipo efectivo, **sin cuentas de
  pagos entrantes/salientes** (las define el contador; decisión del usuario
  16/11/2026, «opción A»). Se llama al cargar el plan `gt` en una empresa
  nueva (`_load` en `models/template_gt_extra.py`) y en la migración 5.65
  para las existentes. Idempotente: si ya hay diario de ese tipo, no crea
  otro (p. ej. «Retención IVA/ISR Recibida» de Lorenzo en `conta_gen`).
- La cuenta se crea **sin** `company_ids` en los valores, con
  `allowed_company_ids = [empresa]` fijado **dentro** de la función y
  `with_company(empresa)`: sin eso Odoo 18 la rechazó («debe estar asignada
  por lo menos a una empresa», 17/11/2026), tanto con `(6, 0, ids)` como
  llamada sin la empresa activa. Empresas **sin plan contable**
  (`chart_template` vacío) se saltan: no hay dónde crear la cuenta. La
  prueba usa una empresa con plan (la empresa por omisión de la prueba en
  `tienda_odoo` no lo tiene).
- La nota del asistente va con `_message_log`, no `message_post` (5.65):
  en producción falló por falta de correo del remitente, igual que 5.61.
- La constancia se agrega a `numero_retencion` (separadas por coma).
- Factura menor de Q2,500 con diario de IVA: solo aviso, no bloquea.
- La migración 5.62 archiva los impuestos «IVA/ISR Retención Global»
  (compras y ventas) y marca los diarios llamados «Retención IVA/ISR…».
  Se quitaron de `data/template/account.tax-gt.csv`, que los volvía a
  crear con `-0.80` en cada empresa nueva (por eso la corrección de 5.44
  nunca duraba; el `hooks.py`, que además buscaba el nombre sin tilde y
  ni siquiera estaba en el manifest, se eliminó).
- **Se eliminó el reporte «Retenciones ISR»** (5.62, decisión del
  usuario). No restaurar.
- «ISR Retención» (impuesto por línea, `base / 1.12`): **fuera de la
  plantilla desde 5.64** y archivado por migración (decisión del usuario:
  nadie lo usa; las retenciones van por el botón «Retención»). Las
  facturas antiguas que lo tengan no cambian. No restaurar.

### Cuentas por cobrar y por pagar
- **Antigüedad por documento:** cada factura/NC/pago sin aplicar con su
  **saldo pendiente a la fecha de corte** (importe menos lo conciliado
  con `account_partial_reconcile.max_date <= corte`), ubicado en su
  tramo según `date_maturity`. Igual que el reporte estándar de Odoo.
- Tramos: **0-30** (incluye lo no vencido; no existe columna
  «Corriente», decisión del usuario), 31-60, 61-90, +90.
- **Fecha inicial opcional:** con ella, solo documentos emitidos en el
  rango, con saldo y antigüedad a la fecha final. Sin ella, igual que
  antes.
- Verificado: total del reporte = saldo contable de CxC/CxP.
- **Agrupación por NIT normalizado** (`nit_normalizado()`: mayúsculas,
  sin guiones ni espacios). NIT vacío o `CF` **nunca** se agrupan. Se
  agrupa por `commercial_partner_id`. El nombre mostrado es el del
  contacto con el documento más reciente.
- **Cheque «Solo con saldo pendiente»** (`agrupar_documentos()`, función
  pura con pruebas): marcado, solo documentos y contactos con saldo;
  sin marcar, todos los contactos con documentos dentro de las fechas,
  incluso pagados (saldo 0.00). Hasta 5.54 el cheque no hacía nada: los
  documentos en cero se descartaban antes de agrupar.

### Estado de cuenta
- Incluye **todos los contactos con el mismo NIT** y los contactos hijos
  (`_partner_ids()`); con NIT vacío o CF, solo el contacto y sus hijos.
- **Documento:** serie-número del DTE; si no hay, `ref` (número de
  factura del proveedor) o el correlativo. Pagos: referencia bancaria.
- **Concepto:** correlativo de Odoo primero (para buscarlo) · tipo de
  documento · descripción corta.
- **Fecha del documento (5.62):** facturas por `invoice_date`, pagos y
  asientos por `date` (`FECHA_DOCUMENTO_SQL`), también en el saldo
  anterior.
- **Retenciones desde 5.62:** son pagos del diario de retención, así que
  salen como **filas de pago** que bajan el saldo (documento = memo
  «Retención IVA · constancia N · factura»). No requirió cambios en el
  reporte.
- Facturas anteriores a 5.62 con línea de retención: siguen saliendo con
  sub-filas bajo la factura; `amount_total` ya es post-retención →
  bruto = neto CxC + Σ retenciones. No quitar esa lógica (histórico).

### Encabezado, folio y formato (13 reportes)
Ventas, compras, diario, mayor, balanza, estado de resultados, balance
general, CxC, CxP, estado de cuenta, conciliación (retenciones ISR se
eliminó en 5.62).

- Plantillas comunes en `report/report_views.xml`:
  - `l10n_gt_extra.encabezado_folio`: `div.header` repetido en cada
    página con empresa, NIT, dirección (de la **compañía activa**),
    nombre del reporte (variable `titulo`), período y folio.
  - `l10n_gt_extra.cuerpo_reporte`: `div.article` con el estilo común
    de tablas (Arial, 11 px, líneas visibles en PDF, cabecera repetida).
- Uso en cada plantilla, **dentro** de `web.html_container`:
  ```xml
  <t t-set="data_report_margin_top" t-value="40"/>
  <t t-set="data_report_header_spacing" t-value="34"/>
  <t t-call="l10n_gt_extra.encabezado_folio">
      <t t-set="titulo" t-value="'Libro Diario'"/>
  </t>
  <t t-call="l10n_gt_extra.cuerpo_reporte">
      <div class="page"> … </div>
  </t>
  ```
- Sin logo ni URL al pie (decisión del usuario: encabezado funcional).
  El cuerpo ya no repite empresa/NIT/período; solo datos propios del
  reporte (establecimiento del diario, cuenta bancaria, cliente…).
- Columnas que **no se parten** (clase `l10n_gt_nowrap` y montos
  `text-right`/`text-end`): tipo, fecha, documento, NIT y montos. Los
  nombres largos son los que bajan de línea. Mismo papel y DPI en los dos
  servidores (Carta, 90 DPI, `wkhtmltopdf` 0.12.6.1): las diferencias de
  aspecto vienen de los datos (nombres largos), no del entorno.
- Orientación: horizontal ventas, compras, balanza, CxC, CxP, ISR;
  vertical el resto. Aprobado.
- **Folio:** el `subst()` propio (en `report_views.xml`) pone en cada
  `span.l10n_gt_folio` el valor `data-folio-inicial + sitepage - 1`. En
  la vista previa se ve el folio inicial.

---

## 3. Trampas conocidas

- **Los libros RECALCULAN el IVA de cada línea con la configuración ACTUAL
  del impuesto** (`compute_all`), no leen el asiento. Si se cambia el
  porcentaje de un impuesto ya usado en facturas publicadas, el libro y la
  contabilidad dejan de coincidir. Caso real: `tienda_odoo`, INV/2026/00012
  (DTE 5E46F7CF), publicada con «PEQ» al 12 % incluido; luego PEQ pasó a
  0 %: libro IVA 0.00, asiento 53.57. El pie «Control» (casilla) lo lista
  en «Otras diferencias», con el número del DTE y el de Odoo.
- **`data_report_page_offset` no existe en Odoo 18**: no hace nada. El
  folio va con `span.l10n_gt_folio` + `data-folio-inicial`.
- **`web.basic_layout` NO se usa dentro de `web.html_container`**: lo
  llama por dentro y produce un `<html>` anidado. Usar
  `l10n_gt_extra.cuerpo_reporte`.
- Odoo usa **un solo** `div.header` por documento: si hay dos, se ve el
  primero. Por eso el encabezado propio sustituye al de la compañía.
- Las líneas de tabla de Bootstrap no salen en el PDF sin el diseño de
  la compañía: las da el estilo de `cuerpo_reporte`.
- **`&nbsp;` en XML es inválido** → `&#160;`.
- `Char(translate=True)` se guarda como `jsonb` → en SQL `campo::text`,
  y al leer desde SQL crudo, convertir el dict (`_to_str`, `_jsonb_str`).
- Asientos publicados bloquean el ORM → `button_draft()` antes de editar.
- Reportes eliminados en v5.45 y Retenciones ISR (5.62): no restaurar.
- **Retenciones: nunca volver a impuestos de fórmula** (`amount_type='code'`
  con `quantity` = total en una línea de precio 0). Dieron montos
  equivocados (-0.80 en vez de -0.15), cuentas vacías en compras y
  modificaban facturas con DTE. Desde 5.62 son pagos.
- `ir.actions.report` → tabla `ir_act_report_xml`;
  `ir.actions.act_window` → tabla `ir_act_window`.
- Conciliación bancaria: `account_bank_statement_line.is_reconciled`
  (no `account_move_line.reconciled`); requiere OCA
  `account_reconciliation_widget` (18.0).
- La migración `migrations/19.0.0.0/` no corre en 18.0 (versión menor).
- **Servidor de producción SOLUCONTA** (4 bases, mismo código): actualizar
  con `docker compose exec -T odoo /entrypoint.sh odoo -d <base> -u
  l10n_gt_extra --no-http --stop-after-init`. El aviso «couldn't create
  the logfile directory» es inofensivo; confirmar con
  `SELECT latest_version FROM ir_module_module WHERE name='l10n_gt_extra'`.
  `/web/login` responde 303 (varias bases): es normal. Las 4 bases se
  actualizan en la misma sesión, porque comparten el código.
- **Clon superficial:** el repo se clonó con `--depth` y solo seguía
  `18.0`. Para una rama nueva del remoto:
  `git remote set-branches --add origin <rama> && git fetch origin <rama>`.
- El aviso `<string>:34: (ERROR/3) Undefined substitution referenced:
  "---------"` al actualizar viene del texto `description` del manifest
  (docutils). Cosmético.

---

- **Nunca decidir el signo comparando el texto `tipo`.** En el libro de
  compras a `tipo` se le concatena `' PEQ'`, así que `tipo == 'NC'`
  fallaba y las notas de crédito de proveedores pequeño contribuyente
  **sumaban**. Desde v5.54 el signo lo manda la bandera `es_nc`
  (`move_type != 'in_invoice' and not nota_debito`); `tipo` es solo texto
  a imprimir.
- `gt_dte_tipo` y `gt_emisor_afiliacion_iva` los crea `gt_xml_importer`
  (>= 18.0.1.2.0) y son **almacenados, no calculados**: traen el dato del
  propio DTE. `gt_emisor_afiliacion_iva` es el régimen de QUIEN EMITIÓ el
  documento, no el de la empresa que lleva la contabilidad. Leerlos
  siempre tras comprobar `'campo' in Model._fields`.
- **`l10n_gt_fel_dte_code` solo vale con `l10n_gt_fel_uuid`.**
  `odoo_fel_integrador` calcula ese campo también en facturas de
  proveedor, según el régimen de la EMPRESA (empresa PEQ → FPEQ,
  rectificativa → NABN), aunque nunca las certificó. En v5.54 inicial el
  libro de compras de Susely salió todo FPEQ/NABN. `CAMPOS_TIPO_DTE`
  lleva pares (campo, requisito).
- **Crédito fiscal en compras** (reglas del contador, 01/10/2026):
  comprador PEQ o EXE → nunca crédito, todo a exento; comprador GEN que
  recibe FPEQ/FCAP/FAPE/FCPE/RDON/RECI, o de un emisor PEQ/EXE → sin
  crédito; comprador GEN con FACT/NCRE/FCAM… → decide el impuesto de cada
  línea, como siempre. Sin crédito, el monto con impuestos
  (`total_included`) va a la columna exenta y el IVA queda en cero. Los
  documentos de pequeño contribuyente van a la columna **Peq.**
- **El régimen del comprador NO se guarda en este módulo.** La única
  fuente es `res.company.gt_tax_regime` de `l10n_gt_peq` (claves GEN /
  PEQ / EXE) y su historial `company.regime.history` (`regime`,
  `date_from`, `date_to`). El asistente del libro de compras propone el
  régimen vigente en la **fecha inicial** (`regimen_en_fecha()`) y se
  puede cambiar a mano. Sin `l10n_gt_peq` instalado: GEN, comportamiento
  anterior. Se lee con `'campo' in _fields`, **sin** agregar
  `l10n_gt_peq` a `depends` (regla 0). En el borrador de 5.54 se creó un
  campo propio `l10n_gt_regimen_iva` duplicando el régimen y se quitó
  antes de subir: si aparece la columna huérfana en `tienda_odoo`, es eso.
- Los documentos **ya importados antes del PR #4 del importador** no
  tienen `gt_dte_tipo`: para ellos el libro sigue mostrando la lógica
  anterior. Rellenar lo histórico es una decisión aparte.

---

## 4. Cómo trabajar (resumen; el detalle está en PROTOCOLO-ENTREGAS.md)

| Variable | Valor en el servidor de pruebas |
|---|---|
| `<REPO>` | `/opt/odoo-docker/addons/l10n_gt_extra` |
| `<BASE>` | `tienda_odoo` (compañía de prueba: 4) |
| `<DOMINIO>` | `iaguatemala.click` |
| `<MODULOS>` | `l10n_gt_extra` |

- El repo no tiene `.pre-commit-config.yaml`: se valida con `py_compile`
  y el parser XML. No introducir pre-commit en un cambio funcional.
- Desde v5.54 hay `tests/` (funciones puras de `report/tipos_dte.py` y,
  desde 5.55, `agrupar_documentos()` de CxC/CxP; desde 5.56,
  `report/er_columnas.py` y `report/bg_columnas.py`; desde 5.57,
  `report/fe_columnas.py`; desde 5.58, `report/conciliacion_logica.py`; desde 5.59, `wizard/duplicados_logica.py` y el CUI), con objetos simulados; no tocan la base). Se corren con
  `--test-enable --test-tags /l10n_gt_extra`. **No** usar
  `AccountTestInvoicingCommon`: en `tienda_odoo` falla al crear el usuario
  de prueba (algún módulo OCA rompe `res.users.create` en tests).
- **Nunca `docker compose restart`** (se cuelga): siempre
  `stop && rm -f && up -d`, en bloque aparte y solo si `-u` salió limpio.
- Actualizar desde la interfaz **no** recarga el Python.
- En el shell, `with_company()` es de los registros, no del `env`:
  `env[modelo].sudo().with_company(4)`.
- Editar en `addons/` (git), nunca en `custom_addons/` (symlinks).
- Al llevar `test` a `18.0`: subir la versión del manifest y crear el
  tag `v18.0.5.X`. En `19.0` ajustar el prefijo de versión.

---

## 5. Pendientes

- **Buscar facturas por serie, número o UUID del DTE**: la barra de búsqueda
  de facturas no los encuentra (busca nombre, referencia y cliente). Va en
  los módulos dueños de esos campos, NO aquí: `odoo_fel_integrador`
  (`l10n_gt_fel_serie`, `l10n_gt_fel_numero`, `l10n_gt_fel_uuid`) y
  `gt_mass_importer` (`firma_fel`, `serie_fel`, `numero_fel`). Mientras
  tanto: filtro personalizado «Serie DTE / Serie FEL contiene …», guardado
  en Favoritos.
- **Libro de bancos e impresión de partida** no tienen folio (su
  asistente no tiene el campo). Si se piden, agregar `folio_inicial` y
  usar el encabezado común.
- **Conciliación con las hojas de la SAT: NO va en este repo** (decisión
  del 23/11/2026). La «Revisión IVA DTE» de `odoo_gt_importer` ya compara
  total e IVA del DTE contra Odoo y genera el reporte (.txt/.csv). Lo que
  falta (DTE de la hoja que no están en Odoo, facturas importadas que no
  vienen en la hoja, anulado en un lado y vigente en el otro, resumir el
  redondeo de centavos) se pide en el chat del importador. Aquí no se
  duplica.
- Texto del pie «Control»: dice «en 1 documentos» (falta singular).
  Corregir en la próxima entrega de código; no amerita versión propia.
- Regla de trabajo: producción se actualiza solo cuando haya un cambio de
  código que lo requiera. Cambios solo de documentación quedan en `test` y
  `18.0` sin actualizar las bases.
- **Cruce con la SAT de compras** (propuesto, no iniciado): asistente que lea el
  Excel de DTE emitidos/recibidos del portal SAT y marque en Odoo los
  anulados. Hace falta un Excel de ejemplo y saber qué módulo importa
  los XML de compras (el importador actual no detecta anulaciones: el
  XML del DTE no cambia al anularse).
- En `tienda_odoo`, facturas 2–11 llevan IVA 12 % incluido en vez de PEQ
  (datos de prueba). En producción, revisar el impuesto de los productos.
- `INV/2026/00006` (tienda_odoo): publicada con estado FEL `error`, sin
  UUID. Dato de prueba a cancelar.

## 6. Historial

| Versión | Cambio principal |
|---|---|
| 5.66 | Libros de compras y ventas: IVA del DTE (`gt_dte_*` del importador) corrigiendo solo la diferencia de IVA; columna «Impuestos y contribuciones»; montos del DTE en USD con el tipo de cambio del asiento; ventas por `invoice_date`; 2 decimales con `Decimal`; Excel con todas las columnas; pie «Control» opcional (casilla, redondeo DTE separado de otras diferencias); «Imp.» → «Import.» |
| 5.65 | Diarios RETENCION IVA/ISR y «Cuenta transitoria retenciones (no tocar)» predeterminados en cada empresa (nueva y existentes, sin cuentas de pagos); nota del asistente con `_message_log` |
| 5.64 | Fuera de la plantilla el impuesto «ISR Retención» (fórmula por línea); migración lo archiva en todas las empresas |
| 5.63 | Libros de compras y ventas: en facturas `mixto`, las líneas sin producto usan `gt_bien_servicio` (B/S) del importador XML para ir a Bienes o Servicios |
| 5.62 | Retenciones IVA/ISR como pago parcial (botón «Retención» + asistente con diario y monto manual, cuenta del método de pago); libro de compras y estado de cuenta por fecha de la factura; fuera impuestos de fórmula «Retención Global», `hooks.py` y reporte Retenciones ISR |
| 5.61 | Depurar duplicados: nota con `_message_log` (no exige correo del remitente) |
| 5.60 | Depurar duplicados: compara el NIT y no el contacto (contactos repetidos por la doble carga) |
| 5.59 | Asistente «Depurar documentos duplicados» (UUID / serie-número, por lotes, excepciones, enlace a renumerar por fecha); CUI de la empresa; lista de movimientos en tránsito: «Cobro en banco», Referencia oculta |
| 5.58 | Conciliación bancaria: todo cobrado salvo lo marcado en tránsito; menú «Movimientos en tránsito» con fecha de cobro; reporte libros → banco calculado → estado de cuenta → diferencia |
| 5.57 | Estado de flujo de efectivo (método indirecto, normal / por mes / acumulativo) con comprobación; campo «Clasificación en flujo de efectivo» en la cuenta; transitorias de Odoo = efectivo |
| 5.56 | Estado de resultados y Balance General: modos normal / por mes / acumulativo, resumen y detalle por sección; costo = cuentas 5.x |
| 5.55 | CxC/CxP: el cheque «Solo con saldo pendiente» funciona; sin él salen también los contactos pagados (saldo 0.00) |
| 5.54 | Tipo real de DTE desde `gt_dte_tipo` (importador); `l10n_gt_fel_dte_code` solo si el documento tiene UUID; columna Peq. por tipo y afiliación del emisor; crédito fiscal según régimen del comprador (de `l10n_gt_peq`, con historial, elegible en el asistente) y tipo de documento; corregido el signo de las NC de proveedor PEQ; primeras pruebas automáticas |
| 5.53 | Montos, fecha, tipo, documento y NIT sin cortes de línea en el PDF (`l10n_gt_nowrap`) |
| 5.52 | Revertido: no leer `fel_tipo_documento` (calculado por régimen de la empresa) |
| 5.51 | Tipo de DTE también desde `fel_tipo_documento` (importador de XML); diario y mayor detallados; ISR con serie-número (PR #6 y siguiente) |
| 5.50 | Tipos DTE SAT, serie-número FEL, anuladas en cero, rendimiento; CxC/CxP por documento, fecha inicial, agrupación por NIT; estado de cuenta consolidado con documentos DTE; encabezado único con folio por página y estilo común (PR #3 y #4) |
| 5.49 | Balanza: cuentas con saldo arrastrado sin movimiento |
| 5.46–5.48 | Conciliación bancaria; quitar dependencia `gt_tax_regime` |
| 5.45 | Eliminación de 3 reportes obsoletos; botón Preview |
| 5.44 | `numero_retencion`; estado de cuenta con sub-filas |
