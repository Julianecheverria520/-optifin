"""Cálculos financieros por usuario conectados directamente a Supabase."""
import calendar
from collections import defaultdict
from datetime import date

from backend.database import supabase

TIPO_PRESUPUESTO = "Gasto Variable (Presupuesto)"

def _fetch(table: str, id_usuario: str | None = None) -> list[dict]:
    """Obtiene registros de Supabase. Si se pasa id_usuario, filtra por él."""
    query = supabase.table(table).select("*")
    if id_usuario is not None:
        query = query.eq("id_usuario", id_usuario)
    res = query.execute()
    return res.data

def nombres_usuarios() -> dict:
    # Retornamos vacío por ahora para evitar consultar la tabla protegida auth.users públicamente
    return {}

def _fecha(valor):
    if not valor: return None
    try:
        return date.fromisoformat(str(valor)[:10])
    except (TypeError, ValueError):
        return None

def _monto(registro) -> float:
    return float(registro.get("monto") or 0)

# ---------- Deudas ----------

def compartido_por_transaccion(id_usuario: str) -> dict:
    total = defaultdict(float)
    for d in _fetch("deudas", id_usuario):
        if d.get("id_transaccion") and d["tipo_deuda"] == "Me debe":
            total[d["id_transaccion"]] += _monto(d)
    return dict(total)

def pagado_por_transaccion(id_usuario: str) -> dict:
    return {d["id_transaccion"]: d["persona"]
            for d in _fetch("deudas", id_usuario)
            if d.get("id_transaccion") and d["tipo_deuda"] == "Le debo"}

def deudas_visibles(id_usuario: str) -> list[dict]:
    res = supabase.table("deudas").select("*").or_(f"id_usuario.eq.{id_usuario},id_usuario_contraparte.eq.{id_usuario}").execute()
    nombres = nombres_usuarios()
    visibles = []
    for d in res.data:
        if d["id_usuario"] == id_usuario:
            visibles.append({**d, "es_propia": True})
        elif d.get("id_usuario_contraparte") == id_usuario:
            visibles.append({
                **d,
                "es_propia": False,
                "tipo_deuda": "Le debo" if d["tipo_deuda"] == "Me debe" else "Me debe",
                "persona": nombres.get(d["id_usuario"], "Usuario Compartido"),
                "id_usuario_contraparte": d["id_usuario"],
                "id_cuenta": None,
            })
    return visibles

def deudas_con_saldo(id_usuario: str) -> list[dict]:
    visibles = deudas_visibles(id_usuario)
    ids_deudas = [d["id_deuda"] for d in visibles if d.get("id_deuda")]
    
    abonado = defaultdict(float)
    if ids_deudas:
        res = supabase.table("abonos_deuda").select("*").in_("id_deuda", ids_deudas).execute()
        for a in res.data:
            abonado[a["id_deuda"]] += _monto(a)

    resultado = []
    for d in visibles:
        pagado = abonado[d["id_deuda"]]
        saldo = max(_monto(d) - pagado, 0)
        d["abonado"] = pagado
        d["saldo_pendiente"] = saldo
        d["estado"] = "Pagada" if saldo <= 0 else ("Parcial" if pagado > 0 else "Pendiente")
        resultado.append(d)
    return resultado

def deudas_por_persona(id_usuario: str) -> list[dict]:
    grupos = {}
    for d in deudas_con_saldo(id_usuario):
        if d["saldo_pendiente"] <= 0:
            continue
        clave = str(d["persona"]).strip().casefold()
        g = grupos.setdefault(clave, {"persona": str(d["persona"]).strip(), "es_usuario": False,
                                      "me_debe": 0.0, "le_debo": 0.0, "deudas": 0})
        g["es_usuario"] = g["es_usuario"] or bool(d.get("id_usuario_contraparte"))
        g["me_debe" if d["tipo_deuda"] == "Me debe" else "le_debo"] += d["saldo_pendiente"]
        g["deudas"] += 1

    for g in grupos.values():
        g["neto"] = g["me_debe"] - g["le_debo"]
    return sorted(grupos.values(), key=lambda g: abs(g["neto"]), reverse=True)

# ---------- Cuentas ----------

def saldos_cuentas(id_usuario: str) -> list[dict]:
    movimiento = defaultdict(float)

    for t in _fetch("transacciones", id_usuario):
        m = _monto(t)
        if t["tipo_movimiento"] == "Ingreso" and t.get("id_cuenta_destino"):
            movimiento[t["id_cuenta_destino"]] += m
        elif t["tipo_movimiento"] == "Gasto" and t.get("id_cuenta_origen"):
            movimiento[t["id_cuenta_origen"]] -= m
        elif t["tipo_movimiento"] == "Traslado":
            if t.get("id_cuenta_origen"): movimiento[t["id_cuenta_origen"]] -= m
            if t.get("id_cuenta_destino"): movimiento[t["id_cuenta_destino"]] += m

    deudas = _fetch("deudas", id_usuario)
    tipo_deuda = {d["id_deuda"]: d["tipo_deuda"] for d in deudas}
    for d in deudas:
        if d.get("id_cuenta"):
            movimiento[d["id_cuenta"]] += -_monto(d) if d["tipo_deuda"] == "Me debe" else _monto(d)

    for a in _fetch("abonos_deuda", id_usuario):
        if a.get("id_cuenta"):
            tipo = tipo_deuda.get(a["id_deuda"])
            movimiento[a["id_cuenta"]] += _monto(a) if tipo == "Me debe" else -_monto(a)

    resultado = []
    for c in _fetch("cuentas", id_usuario):
        if c.get("id_cuenta") is None:
            continue
        inicial = float(c.get("saldo_inicial") or 0)
        resultado.append({
            "id_cuenta": int(c["id_cuenta"]),
            "nombre": str(c["nombre_cuenta"]),
            "tipo": str(c["tipo_cuenta"]),
            "saldo_inicial": inicial,
            "saldo_actual": inicial + movimiento[c["id_cuenta"]],
        })
    return resultado

# ---------- Resumen mensual ----------

def _asignar_pagos(pagos: list[float], montos_fijos: list[float]) -> tuple[list[float], float]:
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
    inicio, fin = _fecha(p.get("fecha_inicio")), _fecha(p.get("fecha_fin"))
    if inicio and (anio, mes) < (inicio.year, inicio.month):
        return False
    if fin and (anio, mes) > (fin.year, fin.month):
        return False
    return True

def gastos_compartidos_conmigo(id_usuario: str) -> list[dict]:
    nombres = nombres_usuarios()
    mis_subs = {str(s["nombre_subcategoria"]).strip().casefold(): s["id_subcategoria"]
                for s in _fetch("subcategorias", id_usuario)}
    
    resultado = []
    deudas = _fetch("deudas") 
    transacciones = {t["id_transaccion"]: t for t in _fetch("transacciones")}
    subs_todas = {s["id_subcategoria"]: s["nombre_subcategoria"] for s in _fetch("subcategorias")}

    for d in deudas:
        if (d.get("id_usuario_contraparte") != id_usuario or d["id_usuario"] == id_usuario
                or d["tipo_deuda"] != "Me debe" or not d.get("id_transaccion")):
            continue
        t = transacciones.get(d["id_transaccion"])
        if not t:
            continue
        nombre_sub = str(subs_todas.get(t["id_subcategoria"], "")).strip().casefold()
        resultado.append({
            "id_transaccion": -d["id_deuda"],
            "id_usuario": id_usuario,
            "fecha": t["fecha"],
            "tipo_movimiento": "Gasto",
            "id_subcategoria": mis_subs.get(nombre_sub),
            "id_cuenta_origen": None,
            "id_cuenta_destino": None,
            "monto": _monto(d),
            "descripcion": d.get("descripcion") or t.get("descripcion"),
            "compartido_por": nombres.get(d["id_usuario"], "Usuario Compartido"),
            "solo_lectura": True,
        })
    return resultado

def resumen_mes(mes: int, anio: int, id_usuario: str, hoy: date | None = None) -> dict:
    hoy = hoy or date.today()
    ultimo_dia = calendar.monthrange(anio, mes)[1]

    subcategorias = {s["id_subcategoria"]: s["nombre_subcategoria"] for s in _fetch("subcategorias", id_usuario)}
    plan = [p for p in _fetch("planificacion", id_usuario)
            if p.get("activo") != "No" and vigente(p, anio, mes)]

    del_mes = [t for t in _fetch("transacciones", id_usuario) + gastos_compartidos_conmigo(id_usuario)
               if (f := _fecha(t.get("fecha"))) and f.month == mes and f.year == anio]
    compartido = compartido_por_transaccion(id_usuario)

    def propio(t):
        return _monto(t) - compartido.get(t.get("id_transaccion"), 0.0)

    ingresos = sum(_monto(t) for t in del_mes if t["tipo_movimiento"] == "Ingreso")
    gastos = sum(propio(t) for t in del_mes if t["tipo_movimiento"] == "Gasto")
    pagado_por_otros = sum(compartido.get(t.get("id_transaccion"), 0.0) for t in del_mes if t["tipo_movimiento"] == "Gasto")

    montos_por_clave = defaultdict(list)
    propio_por_sub = defaultdict(float)
    propio_por_quincena = defaultdict(float)
    for t in sorted(del_mes, key=lambda t: (str(t.get("fecha")), t.get("id_transaccion", 0))):
        if t["tipo_movimiento"] in ("Ingreso", "Gasto"):
            clave = (t["tipo_movimiento"], t["id_subcategoria"])
            m = propio(t) if t["tipo_movimiento"] == "Gasto" else _monto(t)
            montos_por_clave[clave].append(m)
            propio_por_sub[clave] += m
            propio_por_quincena[(*clave, 1 if _fecha(t.get("fecha")).day <= 15 else 2)] += m

    ajustes = {a["id_registro"]: _monto(a) for a in _fetch("ajustes_mes", id_usuario)
               if a["anio"] == anio and a["mes"] == mes}

    def valor_mes(p):
        return ajustes.get(p["id_registro"], _monto(p))

    plan_fijos = sorted((p for p in plan if p["tipo"] != TIPO_PRESUPUESTO),
                        key=lambda p: (p.get("dia_mes") or 99, p["id_registro"]))
    cubierto_por_registro, disponible = {}, {}
    for clave in {("Ingreso" if p["tipo"] == "Ingreso Fijo" else "Gasto", p["id_subcategoria"]) for p in plan_fijos}:
        del_grupo = [p for p in plan_fijos
                     if ("Ingreso" if p["tipo"] == "Ingreso Fijo" else "Gasto", p["id_subcategoria"]) == clave]
        cubiertos, sobrante = _asignar_pagos(montos_por_clave.get(clave, []), [valor_mes(p) for p in del_grupo])
        cubierto_por_registro.update({p["id_registro"]: c for p, c in zip(del_grupo, cubiertos)})
        disponible[clave] = sobrante

    fijos = []
    for p in plan_fijos:
        tipo_mov = "Ingreso" if p["tipo"] == "Ingreso Fijo" else "Gasto"
        monto = valor_mes(p)
        cubierto = cubierto_por_registro[p["id_registro"]]
        vencimiento = date(anio, mes, min(p.get("dia_mes") or ultimo_dia, ultimo_dia))

        fijos.append({
            "id_registro": p["id_registro"],
            "tipo": p["tipo"],
            "tipo_movimiento": tipo_mov,
            "concepto": p["nombre_concepto"],
            "id_subcategoria": p["id_subcategoria"],
            "subcategoria": subcategorias.get(p["id_subcategoria"], "Desconocida"),
            "dia_mes": p["dia_mes"],
            "vencimiento": vencimiento.isoformat(),
            "monto_plan": _monto(p),
            "ajustado": p["id_registro"] in ajustes,
            "monto": monto,
            "cubierto": cubierto,
            "pagado": cubierto,
            "faltante": monto - cubierto,
            "estado": _estado_fijo(monto, cubierto, vencimiento, hoy),
        })

    ultimo_por_clave = {(f["tipo_movimiento"], f["id_subcategoria"]): f for f in fijos}
    for clave, f in ultimo_por_clave.items():
        f["pagado"] += max(disponible.get(clave, 0), 0)

    for f in fijos:
        real = f["pagado"] if f["estado"] == "pagado" else f["monto"]
        f["diferencia_plan"] = real - f["monto_plan"]

    def periodo(gastado, tope, fin_periodo: date) -> dict:
        return {
            "gastado": gastado,
            "tope": tope,
            "restante": tope - gastado,
            "porcentaje": round(gastado / tope * 100, 1) if tope > 0 else 0,
            "excedido": gastado > tope,
            "cerrado": fin_periodo < hoy,
        }

    presupuestos = []
    for p in (p for p in plan if p["tipo"] == TIPO_PRESUPUESTO):
        valor = valor_mes(p)
        sub = p["id_subcategoria"]
        quincenal = p.get("periodicidad") == "Quincenal"
        gastado = propio_por_sub.get(("Gasto", sub), 0.0)

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
            "id_registro": p["id_registro"],
            "concepto": p["nombre_concepto"],
            "subcategoria": subcategorias.get(sub, "Desconocida"),
            "periodicidad": "Quincenal" if quincenal else "Mensual",
            "valor_periodo": valor,
            "tope_plan": _monto(p),
            "ajustado": p["id_registro"] in ajustes,
            **periodo(gastado, valor * 2 if quincenal else valor, date(anio, mes, ultimo_dia)),
            "quincenas": quincenas,
            "restante_abierto": restante_abierto,
        })

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
            "desvio_gastos_fijos": sum(f["diferencia_plan"] for f in fijos if f["tipo_movimiento"] == "Gasto"),
            "desvio_ingresos_fijos": sum(f["diferencia_plan"] for f in fijos if f["tipo_movimiento"] == "Ingreso"),
        },
        "fijos": fijos,
        "presupuestos": presupuestos,
    }

# ---------- Patrimonio ----------

def patrimonio(id_usuario: str) -> dict:
    cuentas = saldos_cuentas(id_usuario)
    deudas = [d for d in deudas_con_saldo(id_usuario) if d["saldo_pendiente"] > 0]

    en_cuentas = sum(c["saldo_actual"] for c in cuentas if c["tipo"] != "Crédito")
    tarjetas = sum(c["saldo_actual"] for c in cuentas if c["tipo"] == "Crédito")
    me_deben = sum(d["saldo_pendiente"] for d in deudas if d["tipo_deuda"] == "Me debe")
    debo = sum(d["saldo_pendiente"] for d in deudas if d["tipo_deuda"] == "Le debo")

    return {
        "en_cuentas": en_cuentas,
        "deuda_tarjetas": -tarjetas if tarjetas < 0 else 0.0,
        "me_deben": me_deben,
        "debo": debo,
        "neto": en_cuentas + tarjetas + me_deben - debo,
    }