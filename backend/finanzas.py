"""Cálculos financieros por usuario: saldos de cuentas, estado de deudas y resumen mensual.

Trabaja sobre listas de dicts (db.a_registros), así que no depende de cómo se guarden
los datos: al migrar a Supabase solo cambia la lectura.

Cada función recibe el ID del usuario y solo usa sus datos, más las deudas que otro usuario de
OptiFin registró con él (vistas desde su lado) y su parte de los gastos que otros compartieron con él.
"""
import calendar
from collections import defaultdict
from datetime import date

from backend import excel_store as db

TIPO_PRESUPUESTO = "Gasto Variable (Presupuesto)"


def _registros(hoja: str, id_usuario: int | None = None) -> list[dict]:
    """Filas de una hoja; si se indica usuario, solo las suyas."""
    df = db.leer_hoja(hoja)
    return db.a_registros(db.solo_usuario(df, id_usuario) if id_usuario is not None else df)


def nombres_usuarios() -> dict:
    return {u["ID_Usuario"]: u["Nombre"] for u in _registros("Usuarios")}


def _fecha(valor):
    try:
        return date.fromisoformat(str(valor)[:10])
    except (TypeError, ValueError):
        return None


def _monto(registro) -> float:
    return float(registro.get("Monto") or 0)


# ---------- Deudas ----------

def compartido_por_transaccion(id_usuario: int) -> dict:
    """{ID_Transaccion: total que otros deben de ese gasto compartido} (transacciones del usuario).
    Solo cuentan las deudas "Me debe"; las "Le debo" ligadas son gastos que pagó otra persona."""
    total = defaultdict(float)
    for d in _registros("Deudas", id_usuario):
        if d.get("ID_Transaccion") and d["Tipo_Deuda"] == "Me debe":
            total[d["ID_Transaccion"]] += _monto(d)
    return dict(total)


def pagado_por_transaccion(id_usuario: int) -> dict:
    """{ID_Transaccion: persona que pagó ese gasto por mí}."""
    return {d["ID_Transaccion"]: d["Persona"]
            for d in _registros("Deudas", id_usuario)
            if d.get("ID_Transaccion") and d["Tipo_Deuda"] == "Le debo"}


def deudas_visibles(id_usuario: int) -> list[dict]:
    """Deudas del usuario más las que otro usuario de OptiFin registró con él, vistas desde su lado:
    si Julián registró "Sandy me debe", Sandy ve "Le debo a Julián" (Es_Propia = False, solo lectura)."""
    nombres = nombres_usuarios()
    visibles = []
    for d in _registros("Deudas"):
        if d["ID_Usuario"] == id_usuario:
            visibles.append({**d, "Es_Propia": True})
        elif d.get("ID_Usuario_Contraparte") == id_usuario:
            visibles.append({
                **d,
                "Es_Propia": False,
                "Tipo_Deuda": "Le debo" if d["Tipo_Deuda"] == "Me debe" else "Me debe",
                "Persona": nombres.get(d["ID_Usuario"], "Otro usuario"),
                "ID_Usuario_Contraparte": d["ID_Usuario"],
                "ID_Cuenta": None,  # la cuenta es del otro usuario
            })
    return visibles


def deudas_con_saldo(id_usuario: int) -> list[dict]:
    """Cada deuda visible con lo abonado, el saldo pendiente y el estado calculado."""
    abonado = defaultdict(float)
    for a in _registros("Abonos_Deuda"):
        abonado[a["ID_Deuda"]] += _monto(a)

    resultado = []
    for d in deudas_visibles(id_usuario):
        pagado = abonado[d["ID_Deuda"]]
        saldo = max(_monto(d) - pagado, 0)
        d["Abonado"] = pagado
        d["Saldo_Pendiente"] = saldo
        d["Estado"] = "Pagada" if saldo <= 0 else ("Parcial" if pagado > 0 else "Pendiente")
        resultado.append(d)
    return resultado


def deudas_por_persona(id_usuario: int) -> list[dict]:
    """Saldo pendiente agrupado por persona: cuánto me debe, cuánto le debo y el neto.
    Solo incluye personas con algo pendiente; primero las de mayor monto neto."""
    grupos = {}
    for d in deudas_con_saldo(id_usuario):
        if d["Saldo_Pendiente"] <= 0:
            continue
        clave = str(d["Persona"]).strip().casefold()
        g = grupos.setdefault(clave, {"persona": str(d["Persona"]).strip(), "es_usuario": False,
                                      "me_debe": 0.0, "le_debo": 0.0, "deudas": 0})
        g["es_usuario"] = g["es_usuario"] or bool(d.get("ID_Usuario_Contraparte"))
        g["me_debe" if d["Tipo_Deuda"] == "Me debe" else "le_debo"] += d["Saldo_Pendiente"]
        g["deudas"] += 1

    for g in grupos.values():
        g["neto"] = g["me_debe"] - g["le_debo"]  # positivo = me debe; negativo = le debo
    return sorted(grupos.values(), key=lambda g: abs(g["neto"]), reverse=True)


# ---------- Cuentas ----------

def saldos_cuentas(id_usuario: int) -> list[dict]:
    """Saldo actual = saldo inicial + ingresos - gastos ± traslados ± préstamos y abonos de deudas."""
    movimiento = defaultdict(float)

    for t in _registros("Transacciones", id_usuario):
        m = _monto(t)
        if t["Tipo_Movimiento"] == "Ingreso":
            movimiento[t["ID_Cuenta_Destino"]] += m
        elif t["Tipo_Movimiento"] == "Gasto":
            movimiento[t["ID_Cuenta_Origen"]] -= m
        elif t["Tipo_Movimiento"] == "Traslado":
            movimiento[t["ID_Cuenta_Origen"]] -= m
            movimiento[t["ID_Cuenta_Destino"]] += m

    # Al crear una deuda con cuenta: si presté ("Me debe") sale dinero; si me prestaron ("Le debo") entra
    deudas = _registros("Deudas", id_usuario)
    tipo_deuda = {d["ID_Deuda"]: d["Tipo_Deuda"] for d in deudas}
    for d in deudas:
        if d.get("ID_Cuenta"):
            movimiento[d["ID_Cuenta"]] += -_monto(d) if d["Tipo_Deuda"] == "Me debe" else _monto(d)

    # Abonos con cuenta: si me pagan entra dinero; si yo pago sale
    for a in _registros("Abonos_Deuda", id_usuario):
        if a.get("ID_Cuenta"):
            tipo = tipo_deuda.get(a["ID_Deuda"])
            movimiento[a["ID_Cuenta"]] += _monto(a) if tipo == "Me debe" else -_monto(a)

    resultado = []
    for c in _registros("Cuentas", id_usuario):
        if c["ID_Cuenta"] is None:
            continue
        inicial = float(c["Saldo_Inicial"] or 0)
        resultado.append({
            "id_cuenta": int(c["ID_Cuenta"]),
            "nombre": str(c["Nombre_Cuenta"]),
            "tipo": str(c["Tipo_Cuenta"]),
            "saldo_inicial": inicial,
            "saldo_actual": inicial + movimiento[c["ID_Cuenta"]],
        })
    return resultado


# ---------- Resumen mensual ----------

def _asignar_pagos(pagos: list[float], montos_fijos: list[float]) -> tuple[list[float], float]:
    """Reparte los pagos de una subcategoría entre sus fijos (ordenados por día).
    1) Un pago igual al monto de un fijo aún sin cubrir se asigna a ese fijo
       (p. ej. Disney 25.900 y Netflix 29.900 en "Suscripciones", pagados en cualquier orden).
    2) El resto se reparte en orden de día (p. ej. dos quincenas de salario).
    Devuelve lo cubierto de cada fijo y lo que sobró (pagado de más)."""
    cubierto = [0.0] * len(montos_fijos)
    restantes = []
    for pago in pagos:
        exacto = next((i for i, m in enumerate(montos_fijos) if cubierto[i] == 0 and abs(m - pago) < 1), None)
        if exacto is not None:
            cubierto[exacto] = montos_fijos[exacto]
        else:
            restantes.append(pago)

    disponible = sum(restantes)
    for i, m in enumerate(montos_fijos):
        aporte = min(disponible, m - cubierto[i])
        cubierto[i] += aporte
        disponible -= aporte
    return cubierto, disponible


def _estado_fijo(monto, cubierto, vencimiento: date, hoy: date) -> str:
    if cubierto >= monto:
        return "pagado"
    if vencimiento < hoy:
        return "vencido"
    return "parcial" if cubierto > 0 else "pendiente"


def vigente(p: dict, anio: int, mes: int) -> bool:
    """¿El concepto de planificación aplica en ese mes? Sin fecha de inicio se considera siempre vigente."""
    inicio, fin = _fecha(p.get("Fecha_Inicio")), _fecha(p.get("Fecha_Fin"))
    if inicio and (anio, mes) < (inicio.year, inicio.month):
        return False
    if fin and (anio, mes) > (fin.year, fin.month):
        return False
    return True


def gastos_compartidos_conmigo(id_usuario: int) -> list[dict]:
    """Mi parte de los gastos que otro usuario de OptiFin pagó y compartió conmigo, como
    movimientos de solo lectura (sin cuenta: yo no he pagado nada todavía; lo debo).
    La subcategoría se busca por nombre entre las mías (todos parten de la misma plantilla).
    El ID es negativo (-ID_Deuda) para no confundirlo con transacciones reales."""
    nombres = nombres_usuarios()
    subs_todas = {s["ID_Subcategoria"]: s["Nombre_Subcategoria"] for s in _registros("Subcategorias")}
    mis_subs = {str(s["Nombre_Subcategoria"]).strip().casefold(): s["ID_Subcategoria"]
                for s in _registros("Subcategorias", id_usuario)}
    transacciones = {t["ID_Transaccion"]: t for t in _registros("Transacciones")}

    resultado = []
    for d in _registros("Deudas"):
        if (d.get("ID_Usuario_Contraparte") != id_usuario or d["ID_Usuario"] == id_usuario
                or d["Tipo_Deuda"] != "Me debe" or not d.get("ID_Transaccion")):
            continue
        t = transacciones.get(d["ID_Transaccion"])
        if not t:
            continue
        nombre_sub = str(subs_todas.get(t["ID_Subcategoria"], "")).strip().casefold()
        resultado.append({
            "ID_Transaccion": -d["ID_Deuda"],
            "ID_Usuario": id_usuario,
            "Fecha": t["Fecha"],
            "Tipo_Movimiento": "Gasto",
            "ID_Subcategoria": mis_subs.get(nombre_sub),
            "ID_Cuenta_Origen": None,
            "ID_Cuenta_Destino": None,
            "Monto": _monto(d),
            "Descripcion": d.get("Descripcion") or t.get("Descripcion"),
            "Compartido_Por": nombres.get(d["ID_Usuario"], "Otro usuario"),
            "Solo_Lectura": True,
        })
    return resultado


def resumen_mes(mes: int, anio: int, id_usuario: int, hoy: date | None = None) -> dict:
    hoy = hoy or date.today()
    ultimo_dia = calendar.monthrange(anio, mes)[1]

    subcategorias = {s["ID_Subcategoria"]: s["Nombre_Subcategoria"] for s in _registros("Subcategorias", id_usuario)}
    plan = [p for p in _registros("Presupuestos_y_Fijos", id_usuario)
            if p.get("Activo") != "No" and vigente(p, anio, mes)]

    # 1. Movimientos reales del mes (los míos + mi parte de gastos que otros usuarios compartieron conmigo)
    del_mes = [t for t in _registros("Transacciones", id_usuario) + gastos_compartidos_conmigo(id_usuario)
               if (f := _fecha(t["Fecha"])) and f.month == mes and f.year == anio]
    # En un gasto compartido, lo que otros deben no es gasto propio sino un préstamo
    compartido = compartido_por_transaccion(id_usuario)

    def propio(t):
        return _monto(t) - compartido.get(t["ID_Transaccion"], 0.0)

    ingresos = sum(_monto(t) for t in del_mes if t["Tipo_Movimiento"] == "Ingreso")
    gastos = sum(propio(t) for t in del_mes if t["Tipo_Movimiento"] == "Gasto")
    pagado_por_otros = sum(compartido.get(t["ID_Transaccion"], 0.0) for t in del_mes if t["Tipo_Movimiento"] == "Gasto")

    # Movimientos propios por (tipo, id_subcategoria): en gastos compartidos solo mi parte;
    # los gastos que pagó otra persona por mí ya se registran por mi parte
    montos_por_clave = defaultdict(list)       # montos en orden de fecha (para asignar a los fijos)
    propio_por_sub = defaultdict(float)        # total del mes
    propio_por_quincena = defaultdict(float)   # (tipo, sub, quincena 1|2) -> total
    for t in sorted(del_mes, key=lambda t: (str(t["Fecha"]), t["ID_Transaccion"])):
        if t["Tipo_Movimiento"] in ("Ingreso", "Gasto"):
            clave = (t["Tipo_Movimiento"], t["ID_Subcategoria"])
            m = propio(t) if t["Tipo_Movimiento"] == "Gasto" else _monto(t)
            montos_por_clave[clave].append(m)
            propio_por_sub[clave] += m
            propio_por_quincena[(*clave, 1 if _fecha(t["Fecha"]).day <= 15 else 2)] += m

    # 2. Fijos: los pagos de cada subcategoría se asignan a sus fijos (ver _asignar_pagos).
    #    Se usa la parte propia: el plan es lo que te corresponde pagar a ti. Si pagas el arriendo
    #    completo y lo compartes, tu parte cubre el fijo; si lo pagó otra persona, también.
    # Valor del mes: el ajuste de ese mes si existe (p. ej. la factura llegó por más); si no, la plantilla
    ajustes = {a["ID_Registro"]: _monto(a) for a in _registros("Ajustes_Mes", id_usuario)
               if a["Anio"] == anio and a["Mes"] == mes}

    def valor_mes(p):
        return ajustes.get(p["ID_Registro"], _monto(p))

    plan_fijos = sorted((p for p in plan if p["Tipo"] != TIPO_PRESUPUESTO),
                        key=lambda p: (p["Dia_Mes"] or 99, p["ID_Registro"]))
    cubierto_por_registro, disponible = {}, {}
    for clave in {("Ingreso" if p["Tipo"] == "Ingreso Fijo" else "Gasto", p["ID_Subcategoria"]) for p in plan_fijos}:
        del_grupo = [p for p in plan_fijos
                     if ("Ingreso" if p["Tipo"] == "Ingreso Fijo" else "Gasto", p["ID_Subcategoria"]) == clave]
        cubiertos, sobrante = _asignar_pagos(montos_por_clave.get(clave, []), [valor_mes(p) for p in del_grupo])
        cubierto_por_registro.update({p["ID_Registro"]: c for p, c in zip(del_grupo, cubiertos)})
        disponible[clave] = sobrante

    fijos = []
    for p in plan_fijos:
        tipo_mov = "Ingreso" if p["Tipo"] == "Ingreso Fijo" else "Gasto"
        monto = valor_mes(p)
        cubierto = cubierto_por_registro[p["ID_Registro"]]
        vencimiento = date(anio, mes, min(p["Dia_Mes"] or ultimo_dia, ultimo_dia))

        fijos.append({
            "id_registro": p["ID_Registro"],
            "tipo": p["Tipo"],
            "tipo_movimiento": tipo_mov,
            "concepto": p["Nombre_Concepto"],
            "id_subcategoria": p["ID_Subcategoria"],
            "subcategoria": subcategorias.get(p["ID_Subcategoria"], "Desconocida"),
            "dia_mes": p["Dia_Mes"],
            "vencimiento": vencimiento.isoformat(),
            "monto_plan": _monto(p),
            "ajustado": p["ID_Registro"] in ajustes,
            "monto": monto,  # valor de este mes (ajustado o plantilla)
            "cubierto": cubierto,
            "pagado": cubierto,  # se completa abajo con lo pagado de más
            "faltante": monto - cubierto,
            "estado": _estado_fijo(monto, cubierto, vencimiento, hoy),
        })

    # Lo que sobra en una subcategoría después de cubrir todos sus fijos se pagó de más:
    # se suma al último fijo de esa subcategoría (p. ej. luz planeada en 90.000 y pagada en 95.000)
    ultimo_por_clave = {(f["tipo_movimiento"], f["id_subcategoria"]): f for f in fijos}
    for clave, f in ultimo_por_clave.items():
        f["pagado"] += max(disponible.get(clave, 0), 0)

    for f in fijos:
        # Desvío contra la plantilla: con lo pagado si ya se pagó; si no, con el valor ajustado del mes
        real = f["pagado"] if f["estado"] == "pagado" else f["monto"]
        f["diferencia_plan"] = real - f["monto_plan"]

    # 3. Presupuestos (topes de gasto variable, "bolsas" que se van gastando con compras parciales).
    #    Mensual: un tope para todo el mes. Quincenal: el valor es por quincena (1-15 y 16-fin),
    #    cada una con su propio avance; el tope del mes es el doble.
    def periodo(gastado, tope, fin_periodo: date) -> dict:
        return {
            "gastado": gastado,
            "tope": tope,
            "restante": tope - gastado,
            "porcentaje": round(gastado / tope * 100, 1) if tope > 0 else 0,
            "excedido": gastado > tope,
            "cerrado": fin_periodo < hoy,  # ya terminó: lo que no se gastó se ahorró
        }

    presupuestos = []
    for p in (p for p in plan if p["Tipo"] == TIPO_PRESUPUESTO):
        valor = valor_mes(p)
        sub = p["ID_Subcategoria"]
        quincenal = p.get("Periodicidad") == "Quincenal"
        gastado = propio_por_sub.get(("Gasto", sub), 0.0)  # solo tu parte cuenta contra el tope

        if quincenal:
            quincenas = [
                {"numero": 1, "rango": "1–15", **periodo(propio_por_quincena[("Gasto", sub, 1)], valor, date(anio, mes, 15))},
                {"numero": 2, "rango": f"16–{ultimo_dia}", **periodo(propio_por_quincena[("Gasto", sub, 2)], valor, date(anio, mes, ultimo_dia))},
            ]
            restante_abierto = sum(max(q["restante"], 0) for q in quincenas if not q["cerrado"])
        else:
            quincenas = None
            restante_abierto = 0.0 if date(anio, mes, ultimo_dia) < hoy else max(valor - gastado, 0)

        presupuestos.append({
            "id_registro": p["ID_Registro"],
            "concepto": p["Nombre_Concepto"],
            "subcategoria": subcategorias.get(sub, "Desconocida"),
            "periodicidad": "Quincenal" if quincenal else "Mensual",
            "valor_periodo": valor,        # por quincena o por mes (el que se ajusta)
            "tope_plan": _monto(p),
            "ajustado": p["ID_Registro"] in ajustes,
            **periodo(gastado, valor * 2 if quincenal else valor, date(anio, mes, ultimo_dia)),
            "quincenas": quincenas,
            "restante_abierto": restante_abierto,  # lo que aún se puede gastar en periodos no cerrados
        })

    # 4. Proyección: cómo terminaría el mes si se cumple lo planeado
    ingresos_plan = sum(f["monto"] for f in fijos if f["tipo_movimiento"] == "Ingreso")
    gastos_fijos_plan = sum(f["monto"] for f in fijos if f["tipo_movimiento"] == "Gasto")
    presupuestos_plan = sum(p["tope"] for p in presupuestos)
    por_recibir = sum(f["faltante"] for f in fijos if f["tipo_movimiento"] == "Ingreso")
    por_pagar = sum(f["faltante"] for f in fijos if f["tipo_movimiento"] == "Gasto")
    presupuesto_restante = sum(p["restante_abierto"] for p in presupuestos)

    return {
        "totales": {"ingresos": ingresos, "gastos": gastos, "saldo": ingresos - gastos,
                    "pagado_por_otros": pagado_por_otros},
        "proyeccion": {
            "ingresos_plan": ingresos_plan,
            "gastos_fijos_plan": gastos_fijos_plan,
            "presupuestos_plan": presupuestos_plan,
            "disponible_plan": ingresos_plan - gastos_fijos_plan - presupuestos_plan,
            "por_recibir": por_recibir,
            "por_pagar": por_pagar,
            "presupuesto_restante": presupuesto_restante,
            "saldo_proyectado": ingresos - gastos + por_recibir - por_pagar - presupuesto_restante,
            # Positivo en gastos = gastaste más de lo planeado; positivo en ingresos = recibiste más
            "desvio_gastos_fijos": sum(f["diferencia_plan"] for f in fijos if f["tipo_movimiento"] == "Gasto"),
            "desvio_ingresos_fijos": sum(f["diferencia_plan"] for f in fijos if f["tipo_movimiento"] == "Ingreso"),
        },
        "fijos": fijos,
        "presupuestos": presupuestos,
    }


# ---------- Patrimonio ----------

def patrimonio(id_usuario: int) -> dict:
    """Foto actual: dinero en cuentas, deuda de tarjetas y deudas con personas."""
    cuentas = saldos_cuentas(id_usuario)
    deudas = [d for d in deudas_con_saldo(id_usuario) if d["Saldo_Pendiente"] > 0]

    en_cuentas = sum(c["saldo_actual"] for c in cuentas if c["tipo"] != "Crédito")
    tarjetas = sum(c["saldo_actual"] for c in cuentas if c["tipo"] == "Crédito")  # negativo = deuda
    me_deben = sum(d["Saldo_Pendiente"] for d in deudas if d["Tipo_Deuda"] == "Me debe")
    debo = sum(d["Saldo_Pendiente"] for d in deudas if d["Tipo_Deuda"] == "Le debo")

    return {
        "en_cuentas": en_cuentas,
        "deuda_tarjetas": -tarjetas if tarjetas < 0 else 0.0,
        "me_deben": me_deben,
        "debo": debo,
        "neto": en_cuentas + tarjetas + me_deben - debo,
    }
