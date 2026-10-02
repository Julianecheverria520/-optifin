"""Cruce de cuentas (liquidación) con una persona.

Se compensa lo que la persona me debe con lo que yo le debo: el monto menor se cancela en
ambos lados con abonos sin cuenta ("Cruce de cuentas #N") y solo queda pendiente el neto.
Si la persona es usuaria de OptiFin, el cruce incluye también las deudas que ella registró
conmigo, y queda pendiente hasta que ella lo apruebe desde su sesión.
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from backend import finanzas, usuarios
from backend.database import supabase
from backend.models import LiquidacionNueva
from backend.routers.debts import actualizar_estado
from backend.seguridad import usuario_actual

router = APIRouter(prefix="/liquidaciones", tags=["Liquidaciones"])
TOLERANCIA = 0.5  # pesos


def _pendientes(uid: str, persona: str | None = None, ids: set | None = None) -> list[dict]:
    """Deudas con saldo pendiente vistas desde `uid` (las suyas y las que otro registró con él),
    filtradas por persona (sin mayúsculas) o por lista de IDs. Primero las más antiguas."""
    resultado = []
    for d in finanzas.deudas_con_saldo(uid):
        if ids is not None and d["id_deuda"] not in ids:
            continue
        if persona is not None and str(d["persona"]).strip().casefold() != persona.strip().casefold():
            continue
        if d["saldo_pendiente"] > TOLERANCIA:
            resultado.append({
                "id_deuda": d["id_deuda"],
                "dueno": d["id_usuario"],
                "tipo": d["tipo_deuda"],
                "persona": d["persona"],
                "id_usuario_contraparte": d.get("id_usuario_contraparte"),
                "fecha": str(d["fecha_creacion"])[:10],
                "descripcion": d.get("descripcion"),
                "saldo": d["saldo_pendiente"],
            })
    return sorted(resultado, key=lambda d: (d["fecha"], d["id_deuda"]))


def _calculo(pendientes: list[dict]) -> dict:
    me_deben = sum(d["saldo"] for d in pendientes if d["tipo"] == "Me debe")
    debo = sum(d["saldo"] for d in pendientes if d["tipo"] == "Le debo")
    return {"total_me_deben": me_deben, "total_debo": debo,
            "monto_cruzado": min(me_deben, debo), "neto": me_deben - debo}


def _contraparte(persona: str, pendientes: list[dict]):
    """ID de usuario de OptiFin de la persona (por sus deudas o por nombre/correo), o None si es externa."""
    for d in pendientes:
        if d["id_usuario_contraparte"]:
            return d["id_usuario_contraparte"]
    usuario = usuarios.buscar(persona)
    return usuario["id"] if usuario else None


def _aplicar(id_liquidacion: int, pendientes: list[dict], monto_cruzado: float):
    """Cancela `monto_cruzado` en cada lado (primero las deudas más antiguas) con abonos sin cuenta.
    Cada abono queda a nombre del dueño de la deuda."""
    hoy = date.today().isoformat()
    for tipo in ("Me debe", "Le debo"):
        restante = monto_cruzado
        for d in (d for d in pendientes if d["tipo"] == tipo):
            if restante <= TOLERANCIA:
                break
            abono = min(d["saldo"], restante)
            supabase.table("abonos").insert({
                "id_usuario": d["dueno"], "id_deuda": d["id_deuda"], "fecha": hoy,
                "monto": round(abono, 2), "id_cuenta": None, "descripcion": f"Cruce de cuentas #{id_liquidacion}",
            }).execute()
            actualizar_estado(d["id_deuda"])
            restante -= abono


def _liquidacion_visible(id_liquidacion: int, uid: str) -> dict:
    """La liquidación solo existe para quien la propuso y para la otra persona."""
    res = supabase.table("liquidaciones").select("*").eq("id_liquidacion", id_liquidacion).execute().data
    if not res or uid not in (res[0]["id_usuario"], res[0]["id_usuario_contraparte"]):
        raise HTTPException(status_code=404, detail="Liquidación no encontrada")
    if res[0]["estado"] != "Pendiente":
        raise HTTPException(status_code=409, detail=f"Esta liquidación ya está {res[0]['estado'].lower()}")
    return res[0]


def _resolver(id_liquidacion: int, estado: str):
    supabase.table("liquidaciones").update({"estado": estado, "fecha_resolucion": date.today().isoformat()}).eq("id_liquidacion", id_liquidacion).execute()


# ---------- Endpoints ----------

@router.get("/")
def obtener_liquidaciones(uid: str = Depends(usuario_actual)):
    """Cruces que propuse y los que me propusieron (estos, vistos desde mi lado)."""
    res = (supabase.table("liquidaciones").select("*").or_(f"id_usuario.eq.{uid},id_usuario_contraparte.eq.{uid}")
           .order("id_liquidacion", desc=True).execute().data or [])
    nombres = usuarios.nombres() if res else {}
    resultado = []
    for l in res:
        propia = l["id_usuario"] == uid
        me_deben, debo, neto = float(l["total_me_deben"] or 0), float(l["total_debo"] or 0), float(l["neto"] or 0)
        resultado.append({
            "ID_Liquidacion": l["id_liquidacion"],
            "Persona": l["persona"] if propia else nombres.get(l["id_usuario"], "Otro usuario"),
            "Fecha": l["fecha"],
            "Monto_Cruzado": float(l["monto_cruzado"]),
            "Total_Me_Deben": me_deben if propia else debo,
            "Total_Debo": debo if propia else me_deben,
            "Neto": neto if propia else -neto,
            "Estado": l["estado"],
            "Soy_Proponente": propia,
            "ID_Usuario": l["id_usuario"],
            "ID_Usuario_Contraparte": l["id_usuario_contraparte"],
        })
    return resultado


@router.get("/vista-previa")
def vista_previa(persona: str, uid: str = Depends(usuario_actual)):
    """Qué se cruzaría hoy con esa persona, sin guardar nada."""
    pendientes = _pendientes(uid, persona=persona)
    contraparte = _contraparte(persona, pendientes)
    return {
        "persona": persona,
        "id_usuario_contraparte": contraparte,
        "requiere_aprobacion": contraparte is not None,
        "me_deben": [d for d in pendientes if d["tipo"] == "Me debe"],
        "debo": [d for d in pendientes if d["tipo"] == "Le debo"],
        **_calculo(pendientes),
    }


@router.post("/")
def proponer_liquidacion(datos: LiquidacionNueva, uid: str = Depends(usuario_actual)):
    """Con una persona externa se aplica de inmediato; con un usuario de OptiFin queda pendiente de su aprobación."""
    pendientes = _pendientes(uid, persona=datos.persona)
    calculo = _calculo(pendientes)
    if calculo["monto_cruzado"] <= TOLERANCIA:
        raise HTTPException(status_code=400, detail="No hay nada que cruzar: solo hay deudas en un sentido. Registra el pago con Abonar.")
    contraparte = _contraparte(datos.persona, pendientes)
    if contraparte == uid:
        raise HTTPException(status_code=400, detail="No puedes cruzar cuentas contigo mismo")

    # Un solo cruce pendiente por persona (o por par de usuarios)
    abiertas = (supabase.table("liquidaciones").select("*").eq("estado", "Pendiente")
                .or_(f"id_usuario.eq.{uid},id_usuario_contraparte.eq.{uid}").execute().data or [])
    for l in abiertas:
        mismo_par = contraparte and {l["id_usuario"], l["id_usuario_contraparte"]} == {uid, contraparte}
        misma_persona = l["id_usuario"] == uid and str(l["persona"]).strip().casefold() == datos.persona.strip().casefold()
        if mismo_par or misma_persona:
            raise HTTPException(status_code=409, detail="Ya hay un cruce pendiente con esta persona: apruébalo o anúlalo primero")

    hoy = date.today().isoformat()
    nuevo_id = supabase.table("liquidaciones").insert({
        "id_usuario": uid,
        "persona": pendientes[0]["persona"],
        "id_usuario_contraparte": contraparte,
        "fecha": hoy,
        "total_me_deben": calculo["total_me_deben"],
        "total_debo": calculo["total_debo"],
        "monto_cruzado": calculo["monto_cruzado"],
        "neto": calculo["neto"],
        "estado": "Pendiente" if contraparte else "Aplicada",
        "deudas": ",".join(str(d["id_deuda"]) for d in pendientes),
        "fecha_resolucion": None if contraparte else hoy,
    }).execute().data[0]["id_liquidacion"]

    if not contraparte:
        _aplicar(nuevo_id, pendientes, calculo["monto_cruzado"])
        return {"mensaje": "Cruce de cuentas aplicado", "id_liquidacion": nuevo_id}
    return {"mensaje": f"Cruce propuesto. Queda pendiente de que {pendientes[0]['persona']} lo apruebe.", "id_liquidacion": nuevo_id}


@router.post("/{id_liquidacion}/aprobar")
def aprobar_liquidacion(id_liquidacion: int, uid: str = Depends(usuario_actual)):
    """La otra persona aprueba: se verifica que los saldos no hayan cambiado y se aplica el cruce."""
    liq = _liquidacion_visible(id_liquidacion, uid)
    if uid != liq["id_usuario_contraparte"]:
        raise HTTPException(status_code=403, detail="Solo la otra persona puede aprobar este cruce")
    # Se recalcula desde el punto de vista de quien lo propuso, con las mismas deudas
    ids = {int(i) for i in str(liq["deudas"] or "").split(",") if i.strip()}
    pendientes = _pendientes(liq["id_usuario"], ids=ids)
    calculo = _calculo(pendientes)
    if (abs(calculo["total_me_deben"] - float(liq["total_me_deben"] or 0)) > TOLERANCIA
            or abs(calculo["total_debo"] - float(liq["total_debo"] or 0)) > TOLERANCIA):
        raise HTTPException(status_code=409, detail="Los saldos cambiaron desde que se propuso el cruce. Pide que lo anulen y propongan uno nuevo.")
    _aplicar(id_liquidacion, pendientes, calculo["monto_cruzado"])
    _resolver(id_liquidacion, "Aplicada")
    return {"mensaje": "Cruce aprobado y aplicado"}


@router.post("/{id_liquidacion}/rechazar")
def rechazar_liquidacion(id_liquidacion: int, uid: str = Depends(usuario_actual)):
    liq = _liquidacion_visible(id_liquidacion, uid)
    if uid != liq["id_usuario_contraparte"]:
        raise HTTPException(status_code=403, detail="Solo la otra persona puede rechazar este cruce")
    _resolver(id_liquidacion, "Rechazada")
    return {"mensaje": "Cruce rechazado"}


@router.post("/{id_liquidacion}/anular")
def anular_liquidacion(id_liquidacion: int, uid: str = Depends(usuario_actual)):
    liq = _liquidacion_visible(id_liquidacion, uid)
    if uid != liq["id_usuario"]:
        raise HTTPException(status_code=403, detail="Solo quien propuso el cruce puede anularlo")
    _resolver(id_liquidacion, "Anulada")
    return {"mensaje": "Cruce anulado"}
