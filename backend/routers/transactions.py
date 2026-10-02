from fastapi import APIRouter, Depends, HTTPException
from backend.models import Transaccion
from backend.seguridad import usuario_actual
from backend.database import supabase

router = APIRouter(prefix="/transacciones", tags=["Transacciones"])

def _validar_referencias(trans: Transaccion, uid: str):
    """Verifica directamente en la nube que las cuentas y subcategorías existan de forma segura."""
    if trans.id_cuenta_origen:
        c = supabase.table("cuentas").select("id_cuenta").eq("id_cuenta", trans.id_cuenta_origen).eq("id_usuario", uid).execute()
        if not c.data: raise HTTPException(status_code=400, detail="La cuenta de origen no existe")
    if trans.id_cuenta_destino:
        c = supabase.table("cuentas").select("id_cuenta").eq("id_cuenta", trans.id_cuenta_destino).eq("id_usuario", uid).execute()
        if not c.data: raise HTTPException(status_code=400, detail="La cuenta de destino no existe")
    
    if trans.id_subcategoria:
        # Hacemos dos consultas simples para evitar bloqueos por Foreign Keys en Supabase
        sub = supabase.table("subcategorias").select("id_categoria").eq("id_subcategoria", trans.id_subcategoria).execute()
        if not sub.data:
            raise HTTPException(status_code=400, detail="La subcategoría no existe")
        
        cat_id = sub.data[0].get("id_categoria")
        if cat_id:
            cat = supabase.table("categorias").select("tipo_movimiento").eq("id_categoria", cat_id).execute()
            if cat.data:
                tipo_cat = cat.data[0].get("tipo_movimiento")
                if tipo_cat != trans.tipo_movimiento:
                    raise HTTPException(status_code=400, detail=f"La subcategoría no corresponde a un {trans.tipo_movimiento.lower()}")

@router.get("/")
def obtener_transacciones(uid: str = Depends(usuario_actual)):
    # Traer transacciones
    res = supabase.table("transacciones").select("*").eq("id_usuario", uid).order("fecha", desc=True).execute()
    transacciones = res.data or []
    
    # Traer todas las deudas del usuario (más seguro que el join automático)
    deudas_res = supabase.table("deudas").select("*").eq("id_usuario", uid).execute()
    deudas = deudas_res.data or []
    
    registros = []
    for t in transacciones:
        id_tx = t.get("id_transaccion") or t.get("id")
        # Enlazar deudas a esta transacción manualmente
        deudas_tx = [d for d in deudas if d.get("id_transaccion_origen") == id_tx or d.get("id_transaccion") == id_tx]
        
        monto_compartido = sum(float(d.get('monto', 0)) for d in deudas_tx if d.get('tipo_deuda') == 'Me debe')
        pagado_por = next((d.get('persona') for d in deudas_tx if d.get('tipo_deuda') == 'Le debo'), None)
        
        registros.append({
            "ID_Transaccion": id_tx,
            "Fecha": t.get("fecha"),
            "Tipo_Movimiento": t.get("tipo_movimiento"),
            "ID_Subcategoria": t.get("id_subcategoria"),
            "ID_Cuenta_Origen": t.get("id_cuenta_origen"),
            "ID_Cuenta_Destino": t.get("id_cuenta_destino"),
            "Monto": float(t.get("monto") or 0),
            "Descripcion": t.get("descripcion") or "",
            "Monto_Compartido": monto_compartido,
            "Pagado_Por": pagado_por,
            "Solo_Lectura": False
        })
        
    return registros

@router.post("/")
def crear_transaccion(trans: Transaccion, uid: str = Depends(usuario_actual)):
    _validar_referencias(trans, uid)
    
    data_t = {
        "id_usuario": uid,
        "fecha": trans.fecha.strftime("%Y-%m-%d"),
        "tipo_movimiento": trans.tipo_movimiento,
        "id_subcategoria": trans.id_subcategoria,
        "id_cuenta_origen": trans.id_cuenta_origen,
        "id_cuenta_destino": trans.id_cuenta_destino,
        "monto": trans.monto,
        "descripcion": trans.descripcion
    }
    res = supabase.table("transacciones").insert(data_t).execute()
    
    # Extracción segura del ID
    nuevo_id = res.data[0].get("id_transaccion") or res.data[0].get("id")
    
    # Manejo de gastos compartidos protegiendo listas vacías (None)
    partes = [(p.persona, p.monto, "Me debe") for p in (trans.compartido or [])]
    if trans.pagado_por:
        partes.append((trans.pagado_por, trans.monto, "Le debo"))
        
    if partes:
        for nombre, monto, tipo in partes:
            supabase.table("deudas").insert({
                "id_usuario": uid,
                "persona": nombre,
                "tipo_deuda": tipo,
                "monto": monto,
                "fecha_creacion": trans.fecha.strftime("%Y-%m-%d"),
                "id_transaccion_origen": nuevo_id,
                "estado": "Pendiente",
                "descripcion": trans.descripcion
            }).execute()
            
    mensaje = f"Gasto registrado: le debes tu parte a {trans.pagado_por}" if trans.pagado_por else ("Gasto compartido guardado" if (trans.compartido or []) else "Transacción guardada")
    return {"mensaje": mensaje, "id_transaccion": nuevo_id}

@router.put("/{id_transaccion}")
def editar_transaccion(id_transaccion: int, trans: Transaccion, uid: str = Depends(usuario_actual)):
    _validar_referencias(trans, uid)
    
    deudas_res = supabase.table("deudas").select("*").eq("id_transaccion_origen", id_transaccion).eq("id_usuario", uid).execute()
    if any(d.get("tipo_deuda") == "Le debo" for d in (deudas_res.data or [])):
        raise HTTPException(status_code=400, detail="Este gasto lo pagó otra persona: para cambiarlo, elimínalo y regístralo de nuevo")
        
    compartido = sum(float(d.get("monto", 0)) for d in (deudas_res.data or []))
    if compartido and trans.tipo_movimiento != "Gasto":
        raise HTTPException(status_code=400, detail="Este gasto es compartido: no puede cambiar de tipo")
    if trans.monto < compartido:
        raise HTTPException(status_code=400, detail="El monto no puede ser menor a lo que te deben por este gasto")
        
    supabase.table("transacciones").update({
        "fecha": trans.fecha.strftime("%Y-%m-%d"),
        "tipo_movimiento": trans.tipo_movimiento,
        "id_subcategoria": trans.id_subcategoria,
        "id_cuenta_origen": trans.id_cuenta_origen,
        "id_cuenta_destino": trans.id_cuenta_destino,
        "monto": trans.monto,
        "descripcion": trans.descripcion
    }).eq("id_transaccion", id_transaccion).eq("id_usuario", uid).execute()
    
    return {"mensaje": "Transacción actualizada"}

@router.delete("/{id_transaccion}")
def eliminar_transaccion(id_transaccion: int, uid: str = Depends(usuario_actual)):
    supabase.table("transacciones").delete().eq("id_transaccion", id_transaccion).eq("id_usuario", uid).execute()
    return {"mensaje": "Transacción eliminada"}