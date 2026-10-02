from fastapi import APIRouter, Depends, HTTPException

from backend import finanzas, usuarios
from backend.database import supabase
from backend.models import Abono, Deuda
from backend.seguridad import usuario_actual

router = APIRouter(prefix="/deudas", tags=["Deudas"])


def total_abonado(id_deuda: int) -> float:
    return sum(float(a["monto"]) for a in supabase.table("abonos").select("monto").eq("id_deuda", id_deuda).execute().data or [])


def actualizar_estado(id_deuda: int):
    """Deja la columna estado coherente con los abonos (informativa: el estado real se calcula al leer)."""
    d = supabase.table("deudas").select("monto").eq("id_deuda", id_deuda).execute().data
    if not d:
        return
    monto, abonado = float(d[0]["monto"]), total_abonado(id_deuda)
    estado = "Pagada" if abonado >= monto - 0.005 else ("Parcial" if abonado > 0.005 else "Pendiente")
    supabase.table("deudas").update({"estado": estado}).eq("id_deuda", id_deuda).execute()


def _deuda_propia(id_deuda: int, uid: str) -> dict:
    """La deuda si la registró este usuario; si no (o si la registró la otra persona), 404."""
    d = supabase.table("deudas").select("*").eq("id_deuda", id_deuda).eq("id_usuario", uid).execute().data
    if not d:
        raise HTTPException(status_code=404, detail="Deuda no encontrada")
    return d[0]


def _validar_cuenta(id_cuenta, uid: str):
    if id_cuenta is not None:
        if not supabase.table("cuentas").select("id_cuenta").eq("id_cuenta", id_cuenta).eq("id_usuario", uid).execute().data:
            raise HTTPException(status_code=400, detail="La cuenta no existe")


def _persona(nombre: str, uid: str) -> dict:
    """Si la persona es usuaria de OptiFin, la deuda se vincula a ella (y la ve desde su cuenta)."""
    usuario = usuarios.buscar(nombre)
    if usuario and usuario["id"] == uid:
        raise HTTPException(status_code=400, detail="No puedes registrar una deuda contigo mismo")
    return {"persona": usuario["nombre"] if usuario else nombre,
            "id_usuario_contraparte": usuario["id"] if usuario else None}


# ---------- Deudas ----------

@router.get("/")
def obtener_deudas(uid: str = Depends(usuario_actual)):
    """Mis deudas + las que otro usuario registró conmigo (Es_Propia = False, solo lectura). Incluye las pagadas."""
    return [{
        "ID_Deuda": d["id_deuda"],
        "Persona": d["persona"],
        "ID_Usuario_Contraparte": d.get("id_usuario_contraparte"),
        "Tipo_Deuda": d["tipo_deuda"],
        "Monto": float(d["monto"]),
        "Abonado": d["abonado"],
        "Saldo_Pendiente": d["saldo_pendiente"],
        "Fecha_Creacion": d["fecha_creacion"],
        "Estado": d["estado"],
        "ID_Cuenta": d.get("id_cuenta"),
        "Descripcion": d.get("descripcion") or "",
        "ID_Transaccion": d.get("id_transaccion_origen"),
        "Es_Propia": d["es_propia"],
    } for d in sorted(finanzas.deudas_con_saldo(uid), key=lambda d: str(d["fecha_creacion"]), reverse=True)]


@router.post("/")
def crear_deuda(deuda: Deuda, uid: str = Depends(usuario_actual)):
    _validar_cuenta(deuda.id_cuenta, uid)
    res = supabase.table("deudas").insert({
        "id_usuario": uid,
        **_persona(deuda.persona, uid),
        "tipo_deuda": deuda.tipo_deuda,
        "monto": deuda.monto,
        "fecha_creacion": deuda.fecha_creacion.isoformat(),
        "id_cuenta": deuda.id_cuenta,
        "estado": "Pendiente",
    }).execute()
    return {"mensaje": "Deuda registrada", "id_deuda": res.data[0]["id_deuda"]}


@router.put("/{id_deuda}")
def editar_deuda(id_deuda: int, deuda: Deuda, uid: str = Depends(usuario_actual)):
    _deuda_propia(id_deuda, uid)
    _validar_cuenta(deuda.id_cuenta, uid)
    if deuda.monto < total_abonado(id_deuda):
        raise HTTPException(status_code=400, detail="El monto no puede ser menor a lo que ya se ha abonado")
    supabase.table("deudas").update({
        **_persona(deuda.persona, uid),
        "tipo_deuda": deuda.tipo_deuda,
        "monto": deuda.monto,
        "fecha_creacion": deuda.fecha_creacion.isoformat(),
        "id_cuenta": deuda.id_cuenta,
    }).eq("id_deuda", id_deuda).eq("id_usuario", uid).execute()
    actualizar_estado(id_deuda)
    return {"mensaje": "Deuda actualizada"}


@router.delete("/{id_deuda}")
def eliminar_deuda(id_deuda: int, uid: str = Depends(usuario_actual)):
    """Elimina la deuda y sus abonos. Si venía de un gasto compartido, ese gasto pasa a ser 100 % propio."""
    _deuda_propia(id_deuda, uid)
    supabase.table("abonos").delete().eq("id_deuda", id_deuda).execute()
    supabase.table("deudas").delete().eq("id_deuda", id_deuda).eq("id_usuario", uid).execute()
    return {"mensaje": "Deuda eliminada"}


@router.get("/personas")
def obtener_personas(uid: str = Depends(usuario_actual)):
    """Sugerencias para compartir gastos: otros usuarios de OptiFin y personas que ya usé."""
    otros = [{"id_usuario": u["id"], "nombre": u["nombre"]} for u in usuarios.listar() if u["id"] != uid]
    nombres_usuarios = {u["nombre"].casefold() for u in otros}
    mias = supabase.table("deudas").select("persona").eq("id_usuario", uid).execute().data or []
    personas = sorted({d["persona"] for d in mias if d["persona"] and d["persona"].casefold() not in nombres_usuarios})
    return {"usuarios": otros, "personas": personas}


# ---------- Abonos ----------

@router.get("/abonos")
def obtener_abonos(uid: str = Depends(usuario_actual)):
    """Abonos de las deudas que el usuario puede ver (las suyas y las que otros registraron con él)."""
    ids = [d["id_deuda"] for d in finanzas.deudas_visibles(uid)]
    if not ids:
        return []
    return [{
        "ID_Abono": a["id_abono"],
        "ID_Usuario": a["id_usuario"],
        "ID_Deuda": a["id_deuda"],
        "Fecha": a["fecha"],
        "Monto": float(a["monto"]),
        "ID_Cuenta": a["id_cuenta"] if a["id_usuario"] == uid else None,  # la cuenta del otro no se muestra
        "Descripcion": a.get("descripcion"),
    } for a in supabase.table("abonos").select("*").in_("id_deuda", ids).execute().data or []]


@router.post("/{id_deuda}/abonos")
def registrar_abono(id_deuda: int, abono: Abono, uid: str = Depends(usuario_actual)):
    """Solo quien registró la deuda puede abonarle (la otra persona la ve en solo lectura)."""
    deuda = _deuda_propia(id_deuda, uid)
    _validar_cuenta(abono.id_cuenta, uid)
    saldo = float(deuda["monto"]) - total_abonado(id_deuda)
    if abono.monto > saldo + 0.005:
        raise HTTPException(status_code=400, detail=f"El abono supera el saldo pendiente (${saldo:,.0f})")
    res = supabase.table("abonos").insert({
        "id_usuario": uid,
        "id_deuda": id_deuda,
        "fecha": abono.fecha.isoformat(),
        "monto": abono.monto,
        "id_cuenta": abono.id_cuenta,
        "descripcion": abono.descripcion or None,
    }).execute()
    actualizar_estado(id_deuda)
    return {"mensaje": "Abono registrado", "id_abono": res.data[0]["id_abono"]}


@router.delete("/abonos/{id_abono}")
def eliminar_abono(id_abono: int, uid: str = Depends(usuario_actual)):
    a = supabase.table("abonos").select("id_deuda, descripcion").eq("id_abono", id_abono).eq("id_usuario", uid).execute().data
    if not a:
        raise HTTPException(status_code=404, detail="Abono no encontrado")
    if str(a[0]["descripcion"] or "").startswith("Cruce de cuentas"):
        raise HTTPException(status_code=409, detail="Este abono es parte de un cruce de cuentas y no se puede eliminar suelto")
    supabase.table("abonos").delete().eq("id_abono", id_abono).eq("id_usuario", uid).execute()
    actualizar_estado(a[0]["id_deuda"])
    return {"mensaje": "Abono eliminado"}
