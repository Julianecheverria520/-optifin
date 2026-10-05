"""Cálculos financieros por usuario sobre Supabase: saldos de cuentas, deudas y resumen mensual.

Cada cálculo usa los datos del usuario (UUID de Supabase Auth), más:
- las deudas que otro usuario de OptiFin registró con él, vistas desde su lado
  (si Julián registró "OptiCore me debe", OptiCore ve "Le debo a Julián", en solo lectura);
- su parte de los gastos que otro usuario pagó y compartió con él (cuenta como gasto suyo).

Los movimientos y deudas ANULADOS no cuentan en ningún cálculo.

Rendimiento: `Datos` carga cada tabla UNA vez por petición y en paralelo (antes el Resumen hacía
16 consultas seguidas). Las funciones aceptan el ID del usuario o un `Datos` ya cargado.
Como el backend usa la clave del servidor (sin RLS), TODA consulta filtra por usuario.
"""
import calendar
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date

from backend import usuarios
from backend.database import supabase

TIPO_PRESUPUESTO = "Gasto Variable (Presupuesto)"


def _fetch(tabla: str, id_usuario: str | None = None, **filtros) -> list[dict]:
    consulta = supabase.table(tabla).select("*")
    if id_usuario is not None:
        consulta = consulta.eq("id_usuario", id_usuario)
    for columna, valor in filtros.items():
        consulta = consulta.in_(columna, list(valor)) if isinstance(valor, (list, set, tuple)) else consulta.eq(columna, valor)
    return consulta.execute().data or []


class Datos:
    """Datos de un usuario para los cálculos de UNA petición: cada tabla se consulta una sola vez."""

    def __init__(self, id_usuario: str):
        self.uid = id_usuario
        self._cache = {}
        uid = id_usuario
        self._cargadores = {
            "cuentas": lambda: _fetch("cuentas", uid),
            "transacciones": lambda: _fetch("transacciones", uid, anulada=False),
            "deudas_propias": lambda: _fetch("deudas", uid, anulada=False),
            "deudas_ajenas": lambda: (supabase.table("deudas").select("*").eq("id_usuario_contraparte", uid)
                                      .neq("id_usuario", uid).eq("anulada", False).execute().data or []),
            "categorias": lambda: _fetch("categorias", uid),
            "subcategorias": lambda: _fetch("subcategorias", uid),
            "planificacion": lambda: _fetch("planificacion", uid),
            "ajustes": lambda: _fetch("ajustes_mes", uid),
        }

    def _cargar(self, nombre: str):
        if nombre not in self._cache:
            self._cache[nombre] = self._cargadores[nombre]()
        return self._cache[nombre]

    def precargar(self, *nombres: str) -> "Datos":
        """Consulta en paralelo las tablas indicadas (todas si no se indica ninguna)."""
        pendientes = [n for n in (nombres or self._cargadores) if n not in self._cache]
        if pendientes:
            with ThreadPoolExecutor(max_workers=len(pendientes)) as hilos:
                for nombre, filas in zip(pendientes, hilos.map(lambda n: self._cargadores[n](), pendientes)):
                    self._cache[nombre] = filas
        return self

    def __getattr__(self, nombre):
        if nombre.startswith("_") or nombre not in self._cargadores:
            raise AttributeError(nombre)
        return self._cargar(nombre)

    # Datos que dependen de otros (se calculan una vez)
    @property
    def nombres(self) -> dict:
        if "nombres" not in self._cache:
            self._cache["nombres"] = usuarios.nombres() if self.deudas_ajenas else {}
        return self._cache["nombres"]

    @property
    def abonos(self) -> list[dict]:
        """Abonos de las deudas visibles (propias y ajenas no anuladas)."""
        if "abonos" not in self._cache:
            ids = [d["id_deuda"] for d in self.deudas_propias + self.deudas_ajenas]
            self._cache["abonos"] = _fetch("abonos", id_deuda=ids) if ids else []
        return self._cache["abonos"]


def _datos(usuario_o_datos) -> Datos:
    return usuario_o_datos if isinstance(usuario_o_datos, Datos) else Datos(usuario_o_datos)


def _int(valor, defecto=0):
    try:
        return int(valor) if valor not in (None, "") else defecto
    except (TypeError, ValueError):
        return defecto


def _float(valor, defecto=0.0):
    try:
        return float(valor) if valor not in (None, "") else defecto
    except (TypeError, ValueError):
        return defecto


def _fecha(valor):
    try:
        return date.fromisoformat(str(valor)[:10]) if valor else None
    except ValueError:
        return None


def _monto(registro) -> float:
    return _float(registro.get("monto"))


def _invertir(tipo: str) -> str:
    return "Le debo" if tipo == "Me debe" else "Me debe"


# ---------- Deudas ----------

def compartido_por_transaccion(usuario) -> dict:
    """{id_transaccion: total que otros me deben de ese gasto compartido} (gastos del usuario)."""
    total = defaultdict(float)
    for d in _datos(usuario).deudas_propias:
        if d["tipo_deuda"] == "Me debe" and d.get("id_transaccion_origen"):
            total[d["id_transaccion_origen"]] += _monto(d)
    return dict(total)


def pagado_por_transaccion(usuario) -> dict:
    """{id_transaccion: persona que pagó ese gasto por mí}."""
    return {d["id_transaccion_origen"]: d["persona"] for d in _datos(usuario).deudas_propias
            if d["tipo_deuda"] == "Le debo" and d.get("id_transaccion_origen")}


def deudas_visibles(usuario) -> list[dict]:
    """Mis deudas (es_propia=True) + las que otro usuario registró conmigo, vistas desde mi lado."""
    datos = _datos(usuario)
    propias = [{**d, "es_propia": True} for d in datos.deudas_propias]
    ajenas = [{
        **d,
        "es_propia": False,
        "tipo_deuda": _invertir(d["tipo_deuda"]),
        "persona": datos.nombres.get(d["id_usuario"], "Otro usuario"),
        "id_usuario_contraparte": d["id_usuario"],
        "id_cuenta": None,  # la cuenta es del otro usuario
    } for d in datos.deudas_ajenas]
    return propias + ajenas


def deudas_con_saldo(usuario) -> list[dict]:
    """Deudas visibles con lo abonado, el saldo pendiente y el estado calculado."""
    datos = _datos(usuario)
    abonado = defaultdict(float)
    for a in datos.abonos:
        abonado[a["id_deuda"]] += _monto(a)
    visibles = deudas_visibles(datos)
    for d in visibles:
        pagado = abonado[d["id_deuda"]]
        saldo = max(_monto(d) - pagado, 0.0)
        d["abonado"] = pagado
        d["saldo_pendiente"] = saldo
        d["estado"] = "Pagada" if saldo <= 0.005 else ("Parcial" if pagado > 0 else "Pendiente")
    return visibles


def deudas_por_persona(usuario) -> list[dict]:
    """Saldo pendiente agrupado por persona (neto positivo = me debe)."""
    grupos = {}
    for d in deudas_con_saldo(usuario):
        if d["saldo_pendiente"] <= 0.005:
            continue
        clave = str(d.get("persona")).strip().casefold()
        g = grupos.setdefault(clave, {"persona": str(d.get("persona")).strip(), "es_usuario": False,
                                      "me_debe": 0.0, "le_debo": 0.0, "deudas": 0})
        g["es_usuario"] = g["es_usuario"] or bool(d.get("id_usuario_contraparte"))
        g["me_debe" if d.get("tipo_deuda") == "Me debe" else "le_debo"] += d["saldo_pendiente"]
        g["deudas"] += 1
    for g in grupos.values():
        g["neto"] = g["me_debe"] - g["le_debo"]
    return sorted(grupos.values(), key=lambda g: abs(g["neto"]), reverse=True)


# ---------- Gastos que otro usuario compartió conmigo ----------

def gastos_compartidos_conmigo(usuario) -> list[dict]:
    """Mi parte de los gastos que otro usuario pagó y compartió conmigo, como movimientos de solo
    lectura (sin cuenta: aún no he pagado, lo debo). La subcategoría se busca por nombre entre las mías.
    El id es negativo (-id_deuda) para no confundirlo con transacciones reales."""
    datos = _datos(usuario)
    if "compartidos" in datos._cache:
        return datos._cache["compartidos"]
    deudas = [d for d in datos.deudas_ajenas if d["tipo_deuda"] == "Me debe" and d.get("id_transaccion_origen")]
    resultado = []
    if deudas:
        transacciones = {t["id_transaccion"]: t for t in _fetch("transacciones", anulada=False,
                                                                id_transaccion=[d["id_transaccion_origen"] for d in deudas])}
        ids_sub = {t["id_subcategoria"] for t in transacciones.values() if t.get("id_subcategoria")}
        nombre_sub = {s["id_subcategoria"]: s["nombre_subcategoria"] for s in _fetch("subcategorias", id_subcategoria=ids_sub)} if ids_sub else {}
        mis_subs = {str(s["nombre_subcategoria"]).strip().casefold(): s["id_subcategoria"] for s in datos.subcategorias}
        for d in deudas:
            t = transacciones.get(d["id_transaccion_origen"])
            if not t:
                continue
            resultado.append({
                "id_transaccion": -d["id_deuda"],
                "id_usuario": datos.uid,
                "fecha": t["fecha"],
                "tipo_movimiento": "Gasto",
                "id_subcategoria": mis_subs.get(str(nombre_sub.get(t.get("id_subcategoria"), "")).strip().casefold()),
                "id_cuenta_origen": None,
                "id_cuenta_destino": None,
                "monto": _monto(d),
                "descripcion": d.get("descripcion") or t.get("descripcion"),
                "compartido_por": datos.nombres.get(d["id_usuario"], "Otro usuario"),
                "solo_lectura": True,
            })
    datos._cache["compartidos"] = resultado
    return resultado


# ---------- Cuentas ----------

def _eventos_cuentas(datos: "Datos") -> list[tuple]:
    """Cada movimiento de dinero en una cuenta: (fecha, id_cuenta, +entra / -sale).
    Ingresos, gastos, traslados, préstamos con cuenta y abonos con cuenta."""
    eventos = []
    for t in datos.transacciones:
        m, tipo, f = _monto(t), t.get("tipo_movimiento"), _fecha(t.get("fecha"))
        if tipo == "Ingreso" and t.get("id_cuenta_destino"):
            eventos.append((f, t["id_cuenta_destino"], m))
        elif tipo == "Gasto" and t.get("id_cuenta_origen"):
            eventos.append((f, t["id_cuenta_origen"], -m))
        elif tipo == "Traslado":
            if t.get("id_cuenta_origen"):
                eventos.append((f, t["id_cuenta_origen"], -m))
            if t.get("id_cuenta_destino"):
                eventos.append((f, t["id_cuenta_destino"], m))

    # Préstamos con cuenta: si presté ("Me debe") salió dinero; si me prestaron ("Le debo") entró
    tipo_deuda = {d["id_deuda"]: d["tipo_deuda"] for d in datos.deudas_propias}
    for d in datos.deudas_propias:
        if d.get("id_cuenta"):
            eventos.append((_fecha(d.get("fecha_creacion")), d["id_cuenta"], -_monto(d) if d["tipo_deuda"] == "Me debe" else _monto(d)))

    # Abonos con cuenta (los registra el dueño de la deuda): si me pagan entra dinero; si yo pago sale
    for a in datos.abonos:
        if a.get("id_cuenta") and a["id_usuario"] == datos.uid:
            eventos.append((_fecha(a.get("fecha")), a["id_cuenta"], _monto(a) if tipo_deuda.get(a["id_deuda"]) == "Me debe" else -_monto(a)))
    return eventos


def saldos_cuentas(usuario, hasta: date | None = None) -> list[dict]:
    """Saldo = saldo inicial + ingresos - gastos ± traslados ± préstamos y abonos de deudas.
    Con `hasta`, el saldo al final de ese día (solo movimientos con fecha <= hasta)."""
    datos = _datos(usuario).precargar("cuentas", "transacciones", "deudas_propias", "deudas_ajenas")
    movimiento = defaultdict(float)
    for f, cuenta, delta in _eventos_cuentas(datos):
        if hasta is None or f is None or f <= hasta:
            movimiento[cuenta] += delta

    return [{
        "id_cuenta": c["id_cuenta"],
        "nombre": str(c.get("nombre_cuenta", "")),
        "tipo": str(c.get("tipo_cuenta", "")),
        "saldo_inicial": _float(c.get("saldo_inicial")),
        "saldo_actual": _float(c.get("saldo_inicial")) + movimiento[c["id_cuenta"]],
    } for c in sorted(datos.cuentas, key=lambda c: c["id_cuenta"])]


# ---------- Resumen mensual ----------

def _asignar_pagos(pagos: list[float], montos_fijos: list[float]) -> tuple[list[float], float]:
    """Reparte los pagos de una subcategoría entre sus fijos (ordenados por día): primero el pago
    con el mismo monto de un fijo aún sin cubrir; el resto, en orden de día. Devuelve lo cubierto
    de cada fijo y lo que sobró (pagado de más)."""
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


def resumen_mes(mes: int, anio: int, usuario, hoy: date | None = None) -> dict:
    datos = _datos(usuario).precargar("transacciones", "deudas_propias", "deudas_ajenas",
                                      "subcategorias", "planificacion", "ajustes")
    hoy = hoy or date.today()
    ultimo_dia = calendar.monthrange(anio, mes)[1]

    subcategorias = {s["id_subcategoria"]: s["nombre_subcategoria"] for s in datos.subcategorias}
    plan = [p for p in datos.planificacion if str(p.get("activo")).lower() != "no" and vigente(p, anio, mes)]

    # 1. Movimientos del mes: los míos + mi parte de gastos que otros usuarios compartieron conmigo
    del_mes = [t for t in datos.transacciones + gastos_compartidos_conmigo(datos)
               if (f := _fecha(t.get("fecha"))) and f.month == mes and f.year == anio]
    compartido = compartido_por_transaccion(datos)

    def propio(t):
        return _monto(t) - compartido.get(t["id_transaccion"], 0.0)

    ingresos = sum(_monto(t) for t in del_mes if t.get("tipo_movimiento") == "Ingreso")
    gastos = sum(propio(t) for t in del_mes if t.get("tipo_movimiento") == "Gasto")
    pagado_por_otros = sum(compartido.get(t["id_transaccion"], 0.0) for t in del_mes if t.get("tipo_movimiento") == "Gasto")

    montos_por_clave = defaultdict(list)
    propio_por_sub = defaultdict(float)
    propio_por_quincena = defaultdict(float)
    for t in sorted(del_mes, key=lambda x: (str(x.get("fecha")), x["id_transaccion"])):
        tipo = t.get("tipo_movimiento")
        if tipo in ("Ingreso", "Gasto"):
            clave = (tipo, t.get("id_subcategoria"))
            m = propio(t) if tipo == "Gasto" else _monto(t)
            # Un fijo (factura) queda pagado con lo que salió de tu bolsillo, aunque lo compartas:
            # si pagas la luz completa y alguien te debe la mitad, la factura igual está pagada.
            # Los presupuestos, en cambio, miden solo tu parte.
            montos_por_clave[clave].append(_monto(t))
            propio_por_sub[clave] += m
            propio_por_quincena[(*clave, 1 if _fecha(t["fecha"]).day <= 15 else 2)] += m

    # 2. Fijos. Valor del mes: el ajuste de ese mes si existe; si no, el de la planificación
    ajustes = {a["id_planificacion"]: _monto(a) for a in datos.ajustes if a["anio"] == anio and a["mes"] == mes}

    def valor_mes(p):
        return ajustes.get(p["id_registro"], _monto(p))

    def clave_de(p):
        return ("Ingreso" if p.get("tipo") == "Ingreso Fijo" else "Gasto", p.get("id_subcategoria"))

    plan_fijos = sorted((p for p in plan if p.get("tipo") != TIPO_PRESUPUESTO),
                        key=lambda x: (_int(x.get("dia_mes"), 99), x["id_registro"]))
    cubierto_por_registro, disponible = {}, {}
    for clave in {clave_de(p) for p in plan_fijos}:
        grupo = [p for p in plan_fijos if clave_de(p) == clave]
        cubiertos, sobrante = _asignar_pagos(montos_por_clave.get(clave, []), [valor_mes(p) for p in grupo])
        cubierto_por_registro.update({p["id_registro"]: c for p, c in zip(grupo, cubiertos)})
        disponible[clave] = sobrante

    fijos = []
    for p in plan_fijos:
        monto, cubierto = valor_mes(p), cubierto_por_registro.get(p["id_registro"], 0.0)
        vencimiento = date(anio, mes, min(_int(p.get("dia_mes")) or ultimo_dia, ultimo_dia))
        fijos.append({
            "id_registro": p["id_registro"], "tipo": p.get("tipo"), "tipo_movimiento": clave_de(p)[0],
            "concepto": p.get("nombre_concepto"), "id_subcategoria": p.get("id_subcategoria"),
            "subcategoria": subcategorias.get(p.get("id_subcategoria"), "Desconocida"),
            "dia_mes": p.get("dia_mes"), "vencimiento": vencimiento.isoformat(),
            "monto_plan": _monto(p), "ajustado": p["id_registro"] in ajustes,
            "monto": monto, "cubierto": cubierto, "pagado": cubierto,
            "faltante": monto - cubierto, "estado": _estado_fijo(monto, cubierto, vencimiento, hoy),
        })

    # Lo pagado de más en una subcategoría se suma al último fijo de esa subcategoría
    for clave, f in {(f["tipo_movimiento"], f["id_subcategoria"]): f for f in fijos}.items():
        f["pagado"] += max(disponible.get(clave, 0), 0)
    for f in fijos:
        f["diferencia_plan"] = (f["pagado"] if f["estado"] == "pagado" else f["monto"]) - f["monto_plan"]

    # 3. Presupuestos (topes): mensuales o quincenales
    def periodo(gastado, tope, fin_periodo: date) -> dict:
        return {"gastado": gastado, "tope": tope, "restante": tope - gastado,
                "porcentaje": round(gastado / tope * 100, 1) if tope > 0 else 0,
                "excedido": gastado > tope, "cerrado": fin_periodo < hoy}

    presupuestos = []
    for p in (p for p in plan if p.get("tipo") == TIPO_PRESUPUESTO):
        valor, sub = valor_mes(p), p.get("id_subcategoria")
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
            "id_registro": p["id_registro"], "concepto": p.get("nombre_concepto"),
            "subcategoria": subcategorias.get(sub, "Desconocida"),
            "periodicidad": "Quincenal" if quincenal else "Mensual",
            "valor_periodo": valor, "tope_plan": _monto(p), "ajustado": p["id_registro"] in ajustes,
            **periodo(gastado, valor * 2 if quincenal else valor, date(anio, mes, ultimo_dia)),
            "quincenas": quincenas, "restante_abierto": restante_abierto,
        })

    # 4. Proyección
    suma = lambda lista, campo: sum(x[campo] for x in lista)
    fijos_ing = [f for f in fijos if f["tipo_movimiento"] == "Ingreso"]
    fijos_gas = [f for f in fijos if f["tipo_movimiento"] == "Gasto"]
    por_recibir, por_pagar = suma(fijos_ing, "faltante"), suma(fijos_gas, "faltante")
    presupuesto_restante = suma(presupuestos, "restante_abierto")
    return {
        "totales": {"ingresos": ingresos, "gastos": gastos, "saldo": ingresos - gastos, "pagado_por_otros": pagado_por_otros},
        "proyeccion": {
            "ingresos_plan": suma(fijos_ing, "monto"),
            "gastos_fijos_plan": suma(fijos_gas, "monto"),
            "presupuestos_plan": suma(presupuestos, "tope"),
            "disponible_plan": suma(fijos_ing, "monto") - suma(fijos_gas, "monto") - suma(presupuestos, "tope"),
            "por_recibir": por_recibir,
            "por_pagar": por_pagar,
            "presupuesto_restante": presupuesto_restante,
            "saldo_proyectado": ingresos - gastos + por_recibir - por_pagar - presupuesto_restante,
            "desvio_gastos_fijos": suma(fijos_gas, "diferencia_plan"),
            "desvio_ingresos_fijos": suma(fijos_ing, "diferencia_plan"),
        },
        "fijos": fijos,
        "presupuestos": presupuestos,
    }


# ---------- Patrimonio ----------

def patrimonio(usuario) -> dict:
    datos = _datos(usuario)
    cuentas = saldos_cuentas(datos)
    deudas = [d for d in deudas_con_saldo(datos) if d["saldo_pendiente"] > 0.005]
    en_cuentas = sum(c["saldo_actual"] for c in cuentas if c["tipo"] != "Crédito")
    tarjetas = sum(c["saldo_actual"] for c in cuentas if c["tipo"] == "Crédito")  # negativo = deuda
    me_deben = sum(d["saldo_pendiente"] for d in deudas if d["tipo_deuda"] == "Me debe")
    debo = sum(d["saldo_pendiente"] for d in deudas if d["tipo_deuda"] == "Le debo")
    return {
        "en_cuentas": en_cuentas,
        "deuda_tarjetas": -tarjetas if tarjetas < 0 else 0.0,
        "me_deben": me_deben,
        "debo": debo,
        "neto": en_cuentas + tarjetas + me_deben - debo,
    }


# ---------- Mes día a día ----------

def mes_diario(mes: int, anio: int, usuario, hoy: date | None = None) -> dict:
    """Gastos del mes día a día (fijos vs. diarios, con su categoría) y el dinero en cuentas
    (sin tarjetas de crédito) al inicio del mes y al final de cada día."""
    datos = _datos(usuario).precargar()
    hoy = hoy or date.today()
    ultimo_dia = calendar.monthrange(anio, mes)[1]
    inicio, fin = date(anio, mes, 1), date(anio, mes, ultimo_dia)

    # Gasto "fijo" = de una subcategoría que tiene un gasto fijo planeado y vigente este mes
    subs_fijas = {p.get("id_subcategoria") for p in datos.planificacion
                  if str(p.get("activo")).lower() != "no" and vigente(p, anio, mes)
                  and p.get("tipo") not in (TIPO_PRESUPUESTO, "Ingreso Fijo")}
    subcategoria = {s["id_subcategoria"]: s for s in datos.subcategorias}
    categoria = {c["id_categoria"]: c["nombre_categoria"] for c in datos.categorias}
    compartido = compartido_por_transaccion(datos)

    gastos, ingresos = [], 0.0
    for t in datos.transacciones + gastos_compartidos_conmigo(datos):
        f = _fecha(t.get("fecha"))
        if not f or not inicio <= f <= fin:
            continue
        if t.get("tipo_movimiento") == "Ingreso":
            ingresos += _monto(t)
        elif t.get("tipo_movimiento") == "Gasto":
            sub = subcategoria.get(t.get("id_subcategoria")) or {}
            gastos.append({
                "dia": f.day,
                "monto": _monto(t) - compartido.get(t["id_transaccion"], 0.0),  # solo mi parte
                "fijo": t.get("id_subcategoria") in subs_fijas,
                "id_categoria": sub.get("id_categoria"),
                "categoria": categoria.get(sub.get("id_categoria"), "Sin categoría"),
                "subcategoria": sub.get("nombre_subcategoria", "Sin subcategoría"),
                "descripcion": t.get("descripcion") or "",
            })

    # Dinero en cuentas (sin crédito): antes del día 1 y al cierre de cada día ya transcurrido
    no_credito = {c["id_cuenta"] for c in datos.cuentas if c.get("tipo_cuenta") != "Crédito"}
    base = sum(_float(c.get("saldo_inicial")) for c in datos.cuentas if c["id_cuenta"] in no_credito)
    eventos = [(f, delta) for f, cuenta, delta in _eventos_cuentas(datos) if cuenta in no_credito]
    saldo_inicial = base + sum(delta for f, delta in eventos if f is None or f < inicio)
    por_dia = defaultdict(float)
    for f, delta in eventos:
        if f and inicio <= f <= fin:
            por_dia[f.day] += delta

    ultimo_real = ultimo_dia if fin <= hoy else (hoy.day if inicio <= hoy else 0)
    saldos, acumulado = [], saldo_inicial
    for dia in range(1, ultimo_dia + 1):
        acumulado += por_dia[dia]
        saldos.append(round(acumulado, 2) if dia <= ultimo_real else None)

    return {
        "mes": mes, "anio": anio, "dias": ultimo_dia, "hoy": hoy.day if (anio, mes) == (hoy.year, hoy.month) else None,
        "saldo_inicial": saldo_inicial,
        "saldo_final": saldos[ultimo_real - 1] if ultimo_real else saldo_inicial,
        "saldo_final_es_hoy": 0 < ultimo_real < ultimo_dia,
        "ingresos": ingresos,
        "saldos": saldos,
        "gastos": sorted(gastos, key=lambda g: g["dia"]),
        "categorias": sorted({(g["id_categoria"], g["categoria"]) for g in gastos}, key=lambda c: c[1]),
    }
