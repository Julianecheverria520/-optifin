from fastapi import APIRouter, Depends, HTTPException
# Asegúrate de importar el cliente de supabase que uses en tu proyecto, 
# por ejemplo: from backend.database import supabase
from backend.database import supabase 
from backend.models import ActivoUpdate, AjusteMes, Planificacion, PlanificacionUpdate
from backend.seguridad import usuario_actual

router = APIRouter(prefix="/planificacion", tags=["Planificacion"])

def _validar_subcategoria(id_subcategoria: int, uid: str):
    res = supabase.table("subcategorias").select("id_subcategoria").eq("id_subcategoria", id_subcategoria).eq("id_usuario", uid).execute()
    if not res.data:
        raise HTTPException(status_code=400, detail=f"La subcategoría {id_subcategoria} no existe")

@router.get("/")
def obtener_planificacion(uid: str = Depends(usuario_actual)):
    res = supabase.table("planificacion").select("*").eq("id_usuario", uid).execute()
    return res.data

@router.post("/")
def crear_planificacion(plan: Planificacion, uid: str = Depends(usuario_actual)):
    _validar_subcategoria(plan.id_subcategoria, uid)
    data = {
        "id_usuario": uid,
        "tipo": plan.tipo,
        "nombre_concepto": plan.nombre_concepto,
        "monto": plan.monto,
        "dia_mes": plan.dia_mes,
        "id_subcategoria": plan.id_subcategoria,
        "fecha_inicio": plan.fecha_inicio.strftime("%Y-%m-%d"),
        "fecha_fin": plan.fecha_fin.strftime("%Y-%m-%d") if plan.fecha_fin else None,
        "periodicidad": plan.periodicidad,
        "activo": plan.activo
    }
    res = supabase.table("planificacion").insert(data).execute()
    
    nuevo_id = res.data[0].get("id_registro") or res.data[0].get("id")
    return {"mensaje": "Planificación guardada", "id_registro": nuevo_id}

@router.put("/{id_registro}")
def editar_planificacion(id_registro: int, plan: PlanificacionUpdate, uid: str = Depends(usuario_actual)):
    _validar_subcategoria(plan.id_subcategoria, uid)
    data = {
        "tipo": plan.tipo,
        "nombre_concepto": plan.nombre_concepto,
        "monto": plan.monto,
        "dia_mes": plan.dia_mes,
        "id_subcategoria": plan.id_subcategoria,
        "fecha_inicio": plan.fecha_inicio.strftime("%Y-%m-%d"),
        "fecha_fin": plan.fecha_fin.strftime("%Y-%m-%d") if plan.fecha_fin else None,
        "periodicidad": plan.periodicidad,
    }
    res = supabase.table("planificacion").update(data).eq("id_registro", id_registro).eq("id_usuario", uid).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    return {"mensaje": "Planificación actualizada"}

@router.put("/{id_registro}/activo")
def cambiar_activo(id_registro: int, datos: ActivoUpdate, uid: str = Depends(usuario_actual)):
    res = supabase.table("planificacion").update({"activo": datos.activo}).eq("id_registro", id_registro).eq("id_usuario", uid).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    return {"mensaje": "Registro activado" if datos.activo == "Sí" else "Registro pausado"}

@router.put("/{id_registro}/ajuste/{anio}/{mes}")
def ajustar_mes(id_registro: int, anio: int, mes: int, ajuste: AjusteMes, uid: str = Depends(usuario_actual)):
    if not 1 <= mes <= 12:
        raise HTTPException(status_code=400, detail="El mes debe estar entre 1 y 12")
    
    # Validar que la planificación pertenezca al usuario
    plan = supabase.table("planificacion").select("id_registro").eq("id_registro", id_registro).eq("id_usuario", uid).execute()
    if not plan.data:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
        
    existente = supabase.table("ajustes_mes").select("id_registro").eq("id_registro", id_registro).eq("anio", anio).eq("mes", mes).execute()
    
    if existente.data:
        supabase.table("ajustes_mes").update({"monto": ajuste.monto}).eq("id_registro", id_registro).eq("anio", anio).eq("mes", mes).execute()
    else:
        supabase.table("ajustes_mes").insert({
            "id_usuario": uid,
            "id_registro": id_registro,
            "anio": anio,
            "mes": mes,
            "monto": ajuste.monto
        }).execute()
        
    return {"mensaje": "Valor del mes ajustado"}

@router.delete("/{id_registro}/ajuste/{anio}/{mes}")
def quitar_ajuste_mes(id_registro: int, anio: int, mes: int, uid: str = Depends(usuario_actual)):
    supabase.table("ajustes_mes").delete().eq("id_registro", id_registro).eq("anio", anio).eq("mes", mes).eq("id_usuario", uid).execute()
    return {"mensaje": "Se volvió al valor planeado"}

@router.delete("/{id_registro}")
def eliminar_planificacion(id_registro: int, uid: str = Depends(usuario_actual)):
    # Limpiar los ajustes primero para evitar conflictos de llaves foráneas
    supabase.table("ajustes_mes").delete().eq("id_registro", id_registro).eq("id_usuario", uid).execute()
    
    res = supabase.table("planificacion").delete().eq("id_registro", id_registro).eq("id_usuario", uid).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    return {"mensaje": "Registro eliminado"}