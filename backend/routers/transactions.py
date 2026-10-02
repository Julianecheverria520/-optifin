from fastapi import APIRouter, Depends, HTTPException

from backend import finanzas, usuarios
from backend.database import supabase
from backend.models import Transaccion
from backend.seguridad import usuario_actual

router = APIRouter(prefix="/transacciones", tags=["Transacciones"])


def _validar_referencias(trans: Transaccion, uid: str):
    """Las cuentas y la subcategoría deben ser del usuario, y la subcategoría debe pertenecer
    a una categoría del mismo tipo (Gasto/Ingreso)."""
    for id_cuenta, nombre in ((trans.id_cuenta_origen, "de origen"), (trans.id_cuenta_destino, "de destino")):
        if id_cuenta is not None:
            c = supabase.table("cuentas").select("id_cuenta").eq("id_cuenta", id_cuenta).eq("id_usuario", uid).execute()
            if not c.data:
                raise HTTPException(status_code=400, detail=f"La cuenta {nombre} no existe")

    if trans.id_subcategoria is None:
        return
    sub = supabase.table("subcategorias").select("id_categoria").eq("id_subcategoria", trans.id_subcategoria).eq("id_usuario", uid).execute()
    if not sub.data:
        raise HTTPException(status_code=400, detail="La subcategoría no existe")
    cat = supabase.table("categorias").select("tipo_movimiento").eq("id_categoria", sub.data[0]["id_categoria"]).execute()
    if cat.data and cat.data[0]["tipo_movimiento"] != trans.tipo_movimiento:
        raise HTTPException(status_code=400, detail=f"La subcategoría no corresponde a un {trans.tipo_movimiento.lower()}")


def _deudas_ligadas(trans: Transaccion, uid: str) -> list[dict]:
    """Deudas que genera un gasto, ligadas a la transacción y sin cuenta:
    - compartido: cada participante me debe su parte ("Me debe");
    - pagado_por: le debo mi parte a quien pagó ("Le debo").
    Si la persona es usuaria de OptiFin (por nombre o correo), la deuda se vincula a ella y la ve desde su cuenta."""
    partes = [(p.persona, p.monto, "Me debe") for p in trans.compartido]
    if trans.pagado_por:
        partes.append((trans.pagado_por, trans.monto, "Le debo"))

    deudas = []
    for nombre, monto, tipo in partes:
        usuario = usuarios.buscar(nombre)
        if usuario and usuario["id"] == uid:
            raise HTTPException(status_code=400, detail="No puedes registrarte a ti mismo como la otra persona")
        deudas.append({
            "id_usuario": uid,
            "persona": usuario["nombre"] if usuario else nombre,
            "id_usuario_contraparte": usuario["id"] if usuario else None,
            "tipo_deuda": tipo,
            "monto": monto,
            "fecha_creacion": trans.fecha.isoformat(),
            "estado": "Pendiente",
            "descripcion": trans.descripcion or None,
        })
    return deudas


def _fila(trans: Transaccion) -> dict:
    return {
        "fecha": trans.fecha.isoformat(),
        "tipo_movimiento": trans.tipo_movimiento,
        "id_subcategoria": trans.id_subcategoria,
        "id_cuenta_origen": trans.id_cuenta_origen,
        "id_cuenta_destino": trans.id_cuenta_destino,
        "monto": trans.monto,
        "descripcion": trans.descripcion,
    }


@router.get("/")
def obtener_transacciones(uid: str = Depends(usuario_actual)):
    """Mis movimientos + mi parte de los gastos que otros usuarios compartieron conmigo (solo lectura)."""
    propias = supabase.table("transacciones").select("*").eq("id_usuario", uid).order("fecha", desc=True).execute().data or []
    compartido = finanzas.compartido_por_transaccion(uid)
    pagado_por = finanzas.pagado_por_transaccion(uid)

    def al_frontend(t, **extra):
        return {
            "ID_Transaccion": t["id_transaccion"],
            "Fecha": t["fecha"],
            "Tipo_Movimiento": t["tipo_movimiento"],
            "ID_Subcategoria": t.get("id_subcategoria"),
            "ID_Cuenta_Origen": t.get("id_cuenta_origen"),
            "ID_Cuenta_Destino": t.get("id_cuenta_destino"),
            "Monto": float(t.get("monto") or 0),
            "Descripcion": t.get("descripcion") or "",
            **extra,
        }

    return ([al_frontend(t, Monto_Compartido=compartido.get(t["id_transaccion"], 0.0),
                         Pagado_Por=pagado_por.get(t["id_transaccion"]), Solo_Lectura=False) for t in propias]
            + [al_frontend(t, Monto_Compartido=0.0, Pagado_Por=None, Compartido_Por=t["compartido_por"], Solo_Lectura=True)
               for t in finanzas.gastos_compartidos_conmigo(uid)])


@router.post("/")
def crear_transaccion(trans: Transaccion, uid: str = Depends(usuario_actual)):
    _validar_referencias(trans, uid)
    deudas = _deudas_ligadas(trans, uid)  # se resuelven antes de guardar nada (puede fallar)

    nuevo_id = supabase.table("transacciones").insert({"id_usuario": uid, **_fila(trans)}).execute().data[0]["id_transaccion"]
    if deudas:
        try:
            supabase.table("deudas").insert([{**d, "id_transaccion_origen": nuevo_id} for d in deudas]).execute()
        except Exception:
            # Sin transacciones de base de datos: si fallan las deudas, se deshace el movimiento
            supabase.table("transacciones").delete().eq("id_transaccion", nuevo_id).execute()
            raise

    if trans.pagado_por:
        mensaje = f"Gasto registrado: le debes tu parte a {trans.pagado_por}"
    elif trans.compartido:
        mensaje = "Gasto compartido guardado"
    else:
        mensaje = "Transacción guardada"
    return {"mensaje": mensaje, "id_transaccion": nuevo_id}


@router.put("/{id_transaccion}")
def editar_transaccion(id_transaccion: int, trans: Transaccion, uid: str = Depends(usuario_actual)):
    """Edita los datos del movimiento. Las partes de un gasto compartido se gestionan desde Deudas."""
    existe = supabase.table("transacciones").select("id_transaccion").eq("id_transaccion", id_transaccion).eq("id_usuario", uid).execute()
    if not existe.data:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    _validar_referencias(trans, uid)

    ligadas = supabase.table("deudas").select("*").eq("id_transaccion_origen", id_transaccion).eq("id_usuario", uid).execute().data or []
    if any(d["tipo_deuda"] == "Le debo" for d in ligadas):
        raise HTTPException(status_code=400, detail="Este gasto lo pagó otra persona: para cambiarlo, elimínalo y regístralo de nuevo")
    compartido = sum(float(d["monto"]) for d in ligadas)
    if compartido and trans.tipo_movimiento != "Gasto":
        raise HTTPException(status_code=400, detail="Este gasto es compartido: no puede cambiar de tipo")
    if trans.monto < compartido:
        raise HTTPException(status_code=400, detail="El monto no puede ser menor a lo que te deben por este gasto")

    supabase.table("transacciones").update(_fila(trans)).eq("id_transaccion", id_transaccion).eq("id_usuario", uid).execute()
    return {"mensaje": "Transacción actualizada"}


@router.delete("/{id_transaccion}")
def eliminar_transaccion(id_transaccion: int, uid: str = Depends(usuario_actual)):
    """Elimina el movimiento y, si era compartido, las deudas que generó con sus abonos."""
    existe = supabase.table("transacciones").select("id_transaccion").eq("id_transaccion", id_transaccion).eq("id_usuario", uid).execute()
    if not existe.data:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    ids_deudas = [d["id_deuda"] for d in supabase.table("deudas").select("id_deuda")
                  .eq("id_transaccion_origen", id_transaccion).eq("id_usuario", uid).execute().data or []]
    if ids_deudas:
        supabase.table("abonos").delete().in_("id_deuda", ids_deudas).execute()
        supabase.table("deudas").delete().in_("id_deuda", ids_deudas).execute()
    supabase.table("transacciones").delete().eq("id_transaccion", id_transaccion).eq("id_usuario", uid).execute()
    return {"mensaje": "Transacción eliminada"}
