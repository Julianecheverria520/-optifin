from fastapi import APIRouter, Depends, HTTPException
from postgrest.exceptions import APIError

from backend import finanzas
from backend.database import supabase
from backend.models import Cuenta
from backend.seguridad import usuario_actual

router = APIRouter(prefix="/cuentas", tags=["Cuentas"])


@router.get("/")
def obtener_cuentas_con_saldos(uid: str = Depends(usuario_actual)):
    # Mismo cálculo que el Resumen: incluye préstamos y abonos con cuenta, no solo movimientos
    return finanzas.saldos_cuentas(uid)


@router.post("/")
def crear_cuenta(cuenta: Cuenta, uid: str = Depends(usuario_actual)):
    res = supabase.table("cuentas").insert({
        "id_usuario": uid,
        "nombre_cuenta": cuenta.nombre_cuenta,
        "tipo_cuenta": cuenta.tipo_cuenta,
        "saldo_inicial": cuenta.saldo_inicial,
    }).execute()
    return {"mensaje": "Cuenta creada exitosamente", "id_cuenta": res.data[0]["id_cuenta"]}


@router.put("/{id_cuenta}")
def editar_cuenta(id_cuenta: int, cuenta: Cuenta, uid: str = Depends(usuario_actual)):
    res = supabase.table("cuentas").update({
        "nombre_cuenta": cuenta.nombre_cuenta,
        "tipo_cuenta": cuenta.tipo_cuenta,
        "saldo_inicial": cuenta.saldo_inicial,
    }).eq("id_cuenta", id_cuenta).eq("id_usuario", uid).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    return {"mensaje": "Cuenta actualizada"}


@router.delete("/{id_cuenta}")
def eliminar_cuenta(id_cuenta: int, uid: str = Depends(usuario_actual)):
    try:
        res = supabase.table("cuentas").delete().eq("id_cuenta", id_cuenta).eq("id_usuario", uid).execute()
    except APIError as e:
        # 23503 = la cuenta está referenciada por movimientos, deudas o abonos (llave foránea)
        if e.code == "23503":
            raise HTTPException(status_code=409, detail="No se puede eliminar: la cuenta tiene movimientos, deudas o abonos asociados.")
        raise
    if not res.data:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    return {"mensaje": "Cuenta eliminada"}
