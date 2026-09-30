from fastapi import APIRouter, Depends, HTTPException
from backend.models import Abono, Deuda
from backend.seguridad import usuario_actual
from backend.database import supabase

router = APIRouter(prefix="/deudas", tags=["Deudas"])

def actualizar_estado(id_deuda: int):
    """Actualiza el estado de la deuda (Pagada, Parcial, Pendiente) basado en la suma de sus abonos."""
    d_res = supabase.table("deudas").select("monto").eq("id_deuda", id_deuda).execute()
    if not d_res.data: return
    monto = float(d_res.data[0]['monto'])
    
    a_res = supabase.table("abonos").select("monto").eq("id_deuda", id_deuda).execute()
    abonado = sum(float(a['monto']) for a in a_res.data)
    
    estado = "Pagada" if abonado >= monto - 0.005 else ("Parcial" if abonado > 0.005 else "Pendiente")
    supabase.table("deudas").update({"estado": estado}).eq("id_deuda", id_deuda).execute()

def total_abonado(id_deuda: int) -> float:
    a_res = supabase.table("abonos").select("monto").eq("id_deuda", id_deuda).execute()
    return sum(float(a['monto']) for a in a_res.data)

@router.get("/")
def obtener_deudas(uid: str = Depends(usuario_actual)):
    res = supabase.table("deudas").select("*, abonos(monto)").or_(f"id_usuario.eq.{uid},id_usuario_contraparte.eq.{uid}").execute()
    
    resultados = []
    for d in res.data:
        abonado = sum(float(a['monto']) for a in d.get('abonos', []))
        monto = float(d['monto'])
        saldo = monto - abonado
        
        if saldo <= 0.005 and d['estado'] == 'Pagada':
            continue
            
        tipo = d['tipo_deuda']
        persona = d['persona']
        # Invertir la vista si el usuario actual es la contraparte
        if d['id_usuario_contraparte'] == uid:
            tipo = "Le debo" if tipo == "Me debe" else "Me debe"
            persona = "Otro usuario (Compartido)"
            
        resultados.append({
            "ID_Deuda": d['id_deuda'],
            "Persona": persona,
            "ID_Usuario_Contraparte": d['id_usuario_contraparte'],
            "Tipo_Deuda": tipo,
            "Monto": monto,
            "Abonado": abonado,
            "Saldo_Pendiente": saldo,
            "Fecha_Creacion": d['fecha_creacion'],
            "Estado": d['estado'],
            "ID_Cuenta": d['id_cuenta'],
            "Descripcion": d['descripcion'] or "",
            "ID_Transaccion": d['id_transaccion_origen']
        })
    return sorted(resultados, key=lambda x: (x['Estado'] == 'Pagada', x['Fecha_Creacion']), reverse=True)

@router.post("/")
def crear_deuda(deuda: Deuda, uid: str = Depends(usuario_actual)):
    if deuda.id_cuenta:
        c = supabase.table("cuentas").select("id_cuenta").eq("id_cuenta", deuda.id_cuenta).eq("id_usuario", uid).execute()
        if not c.data: raise HTTPException(status_code=400, detail="La cuenta no existe")
        
    res = supabase.table("deudas").insert({
        "id_usuario": uid,
        "persona": deuda.persona,
        "tipo_deuda": deuda.tipo_deuda,
        "monto": deuda.monto,
        "fecha_creacion": deuda.fecha_creacion.strftime("%Y-%m-%d"),
        "id_cuenta": deuda.id_cuenta,
        "estado": "Pendiente"
    }).execute()
    return {"mensaje": "Deuda registrada", "id_deuda": res.data[0]['id_deuda']}

@router.put("/{id_deuda}")
def editar_deuda(id_deuda: int, deuda: Deuda, uid: str = Depends(usuario_actual)):
    abonado = total_abonado(id_deuda)
    if deuda.monto < abonado:
        raise HTTPException(status_code=400, detail="El monto no puede ser menor a lo que ya se ha abonado")
        
    supabase.table("deudas").update({
        "persona": deuda.persona,
        "tipo_deuda": deuda.tipo_deuda,
        "monto": deuda.monto,
        "fecha_creacion": deuda.fecha_creacion.strftime("%Y-%m-%d"),
        "id_cuenta": deuda.id_cuenta
    }).eq("id_deuda", id_deuda).eq("id_usuario", uid).execute()
    
    actualizar_estado(id_deuda)
    return {"mensaje": "Deuda actualizada"}

@router.delete("/{id_deuda}")
def eliminar_deuda(id_deuda: int, uid: str = Depends(usuario_actual)):
    # Los abonos se eliminan automáticamente gracias a ON DELETE CASCADE en SQL
    supabase.table("deudas").delete().eq("id_deuda", id_deuda).eq("id_usuario", uid).execute()
    return {"mensaje": "Deuda eliminada"}

@router.get("/personas")
def obtener_personas(uid: str = Depends(usuario_actual)):
    res = supabase.table("deudas").select("persona").eq("id_usuario", uid).execute()
    personas = sorted(list(set(d['persona'] for d in res.data if d['persona'])))
    # Retornamos formato compatible con frontend
    return {"usuarios": [], "personas": personas}

@router.get("/abonos")
def obtener_abonos(uid: str = Depends(usuario_actual)):
    deudas_res = supabase.table("deudas").select("id_deuda").or_(f"id_usuario.eq.{uid},id_usuario_contraparte.eq.{uid}").execute()
    ids_deudas = [d['id_deuda'] for d in deudas_res.data]
    
    if not ids_deudas: return []
    
    abonos_res = supabase.table("abonos").select("*").in_("id_deuda", ids_deudas).execute()
    abonos = []
    for a in abonos_res.data:
        abonos.append({
            "ID_Abono": a['id_abono'],
            "ID_Usuario": a['id_usuario'],
            "ID_Deuda": a['id_deuda'],
            "Fecha": a['fecha'],
            "Monto": float(a['monto']),
            "ID_Cuenta": a['id_cuenta'] if a['id_usuario'] == uid else None,
            "Descripcion": a['descripcion']
        })
    return abonos

@router.post("/{id_deuda}/abonos")
def registrar_abono(id_deuda: int, abono: Abono, uid: str = Depends(usuario_actual)):
    d_res = supabase.table("deudas").select("monto").eq("id_deuda", id_deuda).eq("id_usuario", uid).execute()
    if not d_res.data: raise HTTPException(status_code=404, detail="Deuda no encontrada")
    
    saldo = float(d_res.data[0]['monto']) - total_abonado(id_deuda)
    if abono.monto > saldo + 0.005:
        raise HTTPException(status_code=400, detail=f"El abono supera el saldo pendiente (${saldo:,.0f})")
        
    res = supabase.table("abonos").insert({
        "id_usuario": uid,
        "id_deuda": id_deuda,
        "fecha": abono.fecha.strftime("%Y-%m-%d"),
        "monto": abono.monto,
        "id_cuenta": abono.id_cuenta,
        "descripcion": abono.descripcion
    }).execute()
    
    actualizar_estado(id_deuda)
    return {"mensaje": "Abono registrado", "id_abono": res.data[0]['id_abono']}

@router.delete("/abonos/{id_abono}")
def eliminar_abono(id_abono: int, uid: str = Depends(usuario_actual)):
    a_res = supabase.table("abonos").select("id_deuda, descripcion").eq("id_abono", id_abono).eq("id_usuario", uid).execute()
    if not a_res.data: raise HTTPException(status_code=404, detail="Abono no encontrado")
    
    if str(a_res.data[0]['descripcion'] or "").startswith("Cruce de cuentas"):
        raise HTTPException(status_code=409, detail="Este abono es parte de un cruce de cuentas y no se puede eliminar suelto")
        
    id_deuda = a_res.data[0]['id_deuda']
    supabase.table("abonos").delete().eq("id_abono", id_abono).execute()
    actualizar_estado(id_deuda)
    return {"mensaje": "Abono eliminado"}