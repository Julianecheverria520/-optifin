"""Cálculos financieros por usuario conectados directamente a Supabase (Versión Blindada)."""
import calendar
from collections import defaultdict
from datetime import date
from backend.database import supabase

TIPO_PRESUPUESTO = "Gasto Variable (Presupuesto)"

def _fetch(table: str, id_usuario: str | None = None) -> list[dict]:
    query = supabase.table(table).select("*")
    if id_usuario is not None:
        query = query.eq("id_usuario", id_usuario)
    res = query.execute()
    return res.data or []

def _int(val, default=0):
    if val is None or val == "": return default
    try: return int(val)
    except: return default

def _float(val, default=0.0):
    if val is None or val == "": return default
    try: return float(val)
    except: return default

def _fecha(valor):
    if not valor: return None
    try: return date.fromisoformat(str(valor)[:10])
    except: return None

def _monto(registro) -> float:
    return _float(registro.get("monto"))

# ---------- Deudas ----------

def compartido_por_transaccion(id_usuario: str) -> dict:
    total = defaultdict(float)
    for d in _fetch("deudas", id_usuario):
        id_tx = _int(d.get("id_transaccion") or d.get("id_transaccion_origen"))
        if id_tx and d.get("tipo_deuda") == "Me debe":
            total[id_tx] += _monto(d)
    return dict(total)

def pagado_por_transaccion(id_usuario: str) -> dict:
    res = {}
    for d in _fetch("deudas", id_usuario):
        id_tx = _int(d.get("id_transaccion") or d.get("id_transaccion_origen"))
        if id_tx and d.get("tipo_deuda") == "Le debo":
            res[id_tx] = d.get("persona")
    return res

def deudas_visibles(id_usuario: str) -> list[dict]:
    res = supabase.table("deudas").select("*").eq("id_usuario", id_usuario).execute()
    visibles = []
    for d in (res.data or []):
        d["es_propia"] = True
        visibles.append(d)
    return visibles

def deudas_con_saldo(id_usuario: str) -> list[dict]:
    visibles = deudas_visibles(id_usuario)
    ids_deudas = [_int(d.get("id_deuda") or d.get("id")) for d in visibles if _int(d.get("id_deuda") or d.get("id"))]
    
    abonado = defaultdict(float)
    if ids_deudas:
        res = supabase.table("abonos_deuda").select("*").in_("id_deuda", ids_deudas).execute()
        for a in (res.data or []):
            id_d = _int(a.get("id_deuda") or a.get("id"))
            if id_d: abonado[id_d] += _monto(a)

    resultado = []
    for d in visibles:
        id_d = _int(d.get("id_deuda") or d.get("id"))
        pagado = abonado[id_d]
        saldo = max(_monto(d) - pagado, 0)
        d["abonado"] = pagado
        d["saldo_pendiente"] = saldo
        d["estado"] = "Pagada" if saldo <= 0 else ("Parcial" if pagado > 0 else "Pendiente")
        resultado.append(d)
    return resultado

def deudas_por_persona(id_usuario: str) -> list[dict]:
    grupos = {}
    for d in deudas_con_saldo(id_usuario):
        if d["saldo_pendiente"] <= 0: continue
        clave = str(d.get("persona")).strip().casefold()
        g = grupos.setdefault(clave, {"persona": str(d.get("persona")).strip(), "es_usuario": False,
                                      "me_debe": 0.0, "le_debo": 0.0, "deudas": 0})
        g["me_debe" if d.get("tipo_deuda") == "Me debe" else "le_debo"] += d["saldo_pendiente"]
        g["deudas"] += 1

    for g in grupos.values():
        g["neto"] = g["me_debe"] - g["le_debo"]
    return sorted(grupos.values(), key=lambda g: abs(g["neto"]), reverse=True)

# ---------- Cuentas ----------

def saldos_cuentas(id_usuario: str) -> list[dict]:
    movimiento = defaultdict(float)
    for t in _fetch("transacciones", id_usuario):
        m = _monto(t)
        tipo = t.get("tipo_movimiento")
        if tipo == "Ingreso" and t.get("id_cuenta_destino"):
            movimiento[_int(t["id_cuenta_destino"])] += m
        elif tipo == "Gasto" and t.get("id_cuenta_origen"):
            movimiento[_int(t["id_cuenta_origen"])] -= m
        elif tipo == "Traslado":
            if t.get("id_cuenta_origen"): movimiento[_int(t["id_cuenta_origen"])] -= m
            if t.get("id_cuenta_destino"): movimiento[_int(t["id_cuenta_destino"])] += m

    deudas = _fetch("deudas", id_usuario)
    tipo_deuda = {_int(d.get("id_deuda") or d.get("id")): d.get("tipo_deuda") for d in deudas}
    for d in deudas:
        if d.get("id_cuenta"):
            movimiento[_int(d["id_cuenta"])] += -_monto(d) if d.get("tipo_deuda") == "Me debe" else _monto(d)

    for a in _fetch("abonos_deuda", id_usuario):
        if a.get("id_cuenta"):
            id_d = _int(a.get("id_deuda") or a.get("id"))
            movimiento[_int(a["id_cuenta"])] += _monto(a) if tipo_deuda.get(id_d) == "Me debe" else -_monto(a)

    resultado = []
    for c in _fetch("cuentas", id_usuario):
        id_c = _int(c.get("id_cuenta") or c.get("id"))
        if id_c == 0: continue
        inicial = _float(c.get("saldo_inicial"))
        resultado.append({
            "id_cuenta": id_c,
            "nombre": str(c.get("nombre_cuenta", "")),
            "tipo": str(c.get("tipo_cuenta", "")),
            "saldo_inicial": inicial,
            "saldo_actual": inicial + movimiento[id_c],
        })
    return resultado

# ---------- Resumen mensual ----------

def _asignar_pagos(pagos: list[float], montos_fijos: list[float]) -> tuple[list[float], float]:
    cubierto = [0.0] * len(montos_fijos)
    restantes = []
    for pago in pagos:
        exacto = next((i for i, m in enumerate(montos_fijos) if cubierto[i] == 0 and abs(m - pago) < 1), None)
        if exacto is not None: cubierto[exacto] = montos_fijos[exacto]
        else: restantes.append(pago)

    disponible = sum(restantes)
    for i, m in enumerate(montos_fijos):
        aporte = min(disponible, m - cubierto[i])
        cubierto[i] += aporte
        disponible -= aporte
    return cubierto, disponible

def _estado_fijo(monto, cubierto, vencimiento: date, hoy: date) -> str:
    if cubierto >= monto: return "pagado"
    if vencimiento < hoy: return "vencido"
    return "parcial" if cubierto > 0 else "pendiente"

def vigente(p: dict, anio: int, mes: int) -> bool:
    inicio, fin = _fecha(p.get("fecha_inicio")), _fecha(p.get("fecha_fin"))
    if inicio and (anio, mes) < (inicio.year, inicio.month): return False
    if fin and (anio, mes) > (fin.year, fin.month): return False
    return True

def resumen_mes(mes: int, anio: int, id_usuario: str, hoy: date | None = None) -> dict:
    hoy = hoy or date.today()
    ultimo_dia = calendar.monthrange(anio, mes)[1]

    subcategorias = {_int(s.get("id_subcategoria") or s.get("id")): s.get("nombre_subcategoria") for s in _fetch("subcategorias", id_usuario)}
    plan = [p for p in _fetch("planificacion", id_usuario) if str(p.get("activo")).lower() != "no" and vigente(p, anio, mes)]

    del_mes = [t for t in _fetch("transacciones", id_usuario) if (f := _fecha(t.get("fecha"))) and f.month == mes and f.year == anio]
    compartido = compartido_por_transaccion(id_usuario)

    def propio(t):
        id_tx = _int(t.get("id_transaccion") or t.get("id"))
        return _monto(t) - compartido.get(id_tx, 0.0)

    ingresos = sum(_monto(t) for t in del_mes if t.get("tipo_movimiento") == "Ingreso")
    gastos = sum(propio(t) for t in del_mes if t.get("tipo_movimiento") == "Gasto")
    pagado_por_otros = sum(compartido.get(_int(t.get("id_transaccion") or t.get("id")), 0.0) for t in del_mes if t.get("tipo_movimiento") == "Gasto")

    montos_por_clave = defaultdict(list)
    propio_por_sub = defaultdict(float)
    propio_por_quincena = defaultdict(float)
    
    for t in sorted(del_mes, key=lambda x: (str(x.get("fecha")), _int(x.get("id_transaccion", 0)))):
        tipo = t.get("tipo_movimiento")
        if tipo in ("Ingreso", "Gasto"):
            sub_id = _int(t.get("id_subcategoria"))
            clave = (tipo, sub_id)
            m = propio(t) if tipo == "Gasto" else _monto(t)
            montos_por_clave[clave].append(m)
            propio_por_sub[clave] += m
            f_val = _fecha(t.get("fecha"))
            propio_por_quincena[(*clave, 1 if f_val and f_val.day <= 15 else 2)] += m

    ajustes = {_int(a.get("id_registro") or a.get("id")): _monto(a) for a in _fetch("ajustes_mes", id_usuario) if _int(a.get("anio")) == anio and _int(a.get("mes")) == mes}

    def valor_mes(p):
        return ajustes.get(_int(p.get("id_registro") or p.get("id")), _monto(p))

    plan_fijos = sorted((p for p in plan if p.get("tipo") != TIPO_PRESUPUESTO), key=lambda x: (_int(x.get("dia_mes"), 99), _int(x.get("id_registro") or x.get("id"))))
    
    cubierto_por_registro, disponible = {}, {}
    claves_fijos = set()
    for p in plan_fijos:
        claves_fijos.add(("Ingreso" if p.get("tipo") == "Ingreso Fijo" else "Gasto", _int(p.get("id_subcategoria"))))
        
    for clave in claves_fijos:
        del_grupo = [p for p in plan_fijos if ("Ingreso" if p.get("tipo") == "Ingreso Fijo" else "Gasto", _int(p.get("id_subcategoria"))) == clave]
        cubiertos, sobrante = _asignar_pagos(montos_por_clave.get(clave, []), [valor_mes(p) for p in del_grupo])
        for p, c in zip(del_grupo, cubiertos): cubierto_por_registro[_int(p.get("id_registro") or p.get("id"))] = c
        disponible[clave] = sobrante

    fijos = []
    for p in plan_fijos:
        tipo_mov = "Ingreso" if p.get("tipo") == "Ingreso Fijo" else "Gasto"
        monto = valor_mes(p)
        id_r = _int(p.get("id_registro") or p.get("id"))
        cubierto = cubierto_por_registro.get(id_r, 0)
        
        dia = _int(p.get("dia_mes"), ultimo_dia)
        if dia == 0: dia = ultimo_dia
        vencimiento = date(anio, mes, min(dia, ultimo_dia))

        fijos.append({
            "id_registro": id_r, "tipo": p.get("tipo"), "tipo_movimiento": tipo_mov,
            "concepto": p.get("nombre_concepto"), "id_subcategoria": _int(p.get("id_subcategoria")),
            "subcategoria": subcategorias.get(_int(p.get("id_subcategoria")), "Desconocida"),
            "dia_mes": p.get("dia_mes"), "vencimiento": vencimiento.isoformat(),
            "monto_plan": _monto(p), "ajustado": id_r in ajustes,
            "monto": monto, "cubierto": cubierto, "pagado": cubierto,
            "faltante": monto - cubierto, "estado": _estado_fijo(monto, cubierto, vencimiento, hoy),
        })

    ultimo_por_clave = {(f["tipo_movimiento"], f["id_subcategoria"]): f for f in fijos}
    for clave, f in ultimo_por_clave.items(): f["pagado"] += max(disponible.get(clave, 0), 0)
    for f in fijos:
        f["diferencia_plan"] = (f["pagado"] if f["estado"] == "pagado" else f["monto"]) - f["monto_plan"]

    def periodo(gastado, tope, fin_periodo: date) -> dict:
        return {"gastado": gastado, "tope": tope, "restante": tope - gastado, "porcentaje": round(gastado / tope * 100, 1) if tope > 0 else 0, "excedido": gastado > tope, "cerrado": fin_periodo < hoy}

    presupuestos = []
    for p in (p for p in plan if p.get("tipo") == TIPO_PRESUPUESTO):
        valor = valor_mes(p)
        sub = _int(p.get("id_subcategoria"))
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
            "id_registro": _int(p.get("id_registro") or p.get("id")), "concepto": p.get("nombre_concepto"),
            "subcategoria": subcategorias.get(sub, "Desconocida"), "periodicidad": "Quincenal" if quincenal else "Mensual",
            "valor_periodo": valor, "tope_plan": _monto(p), "ajustado": _int(p.get("id_registro") or p.get("id")) in ajustes,
            **periodo(gastado, valor * 2 if quincenal else valor, date(anio, mes, ultimo_dia)), "quincenas": quincenas, "restante_abierto": restante_abierto,
        })

    return {
        "totales": {"ingresos": ingresos, "gastos": gastos, "saldo": ingresos - gastos, "pagado_por_otros": pagado_por_otros},
        "proyeccion": {
            "ingresos_plan": sum(f["monto"] for f in fijos if f["tipo_movimiento"] == "Ingreso"),
            "gastos_fijos_plan": sum(f["monto"] for f in fijos if f["tipo_movimiento"] == "Gasto"),
            "presupuestos_plan": sum(p["tope"] for p in presupuestos),
            "disponible_plan": sum(f["monto"] for f in fijos if f["tipo_movimiento"] == "Ingreso") - sum(f["monto"] for f in fijos if f["tipo_movimiento"] == "Gasto") - sum(p["tope"] for p in presupuestos),
            "por_recibir": sum(f["faltante"] for f in fijos if f["tipo_movimiento"] == "Ingreso"),
            "por_pagar": sum(f["faltante"] for f in fijos if f["tipo_movimiento"] == "Gasto"),
            "presupuesto_restante": sum(p["restante_abierto"] for p in presupuestos),
            "saldo_proyectado": ingresos - gastos + sum(f["faltante"] for f in fijos if f["tipo_movimiento"] == "Ingreso") - sum(f["faltante"] for f in fijos if f["tipo_movimiento"] == "Gasto") - sum(p["restante_abierto"] for p in presupuestos),
            "desvio_gastos_fijos": sum(f["diferencia_plan"] for f in fijos if f["tipo_movimiento"] == "Gasto"),
            "desvio_ingresos_fijos": sum(f["diferencia_plan"] for f in fijos if f["tipo_movimiento"] == "Ingreso"),
        },
        "fijos": fijos, "presupuestos": presupuestos,
    }

def patrimonio(id_usuario: str) -> dict:
    cuentas = saldos_cuentas(id_usuario)
    deudas = [d for d in deudas_con_saldo(id_usuario) if d["saldo_pendiente"] > 0]
    en_cuentas = sum(c["saldo_actual"] for c in cuentas if c["tipo"] != "Crédito")
    tarjetas = sum(c["saldo_actual"] for c in cuentas if c["tipo"] == "Crédito")
    return {
        "en_cuentas": en_cuentas, "deuda_tarjetas": -tarjetas if tarjetas < 0 else 0.0,
        "me_deben": sum(d["saldo_pendiente"] for d in deudas if d.get("tipo_deuda") == "Me debe"),
        "debo": sum(d["saldo_pendiente"] for d in deudas if d.get("tipo_deuda") == "Le debo"),
        "neto": en_cuentas + tarjetas + sum(d["saldo_pendiente"] for d in deudas if d.get("tipo_deuda") == "Me debe") - sum(d["saldo_pendiente"] for d in deudas if d.get("tipo_deuda") == "Le debo"),
    }