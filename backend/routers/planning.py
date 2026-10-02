from fastapi import APIRouter, Depends, HTTPException

from backend.database import supabase
from backend.models import ActivoUpdate, AjusteMes, Planificacion, PlanificacionUpdate
from backend.seguridad import usuario_actual

router = APIRouter(prefix="/planificacion", tags=["Planificacion"])


def _validar_subcategoria(id_subcategoria: int, uid: str):
    res = supabase.table("subcategorias").select("id_subcategoria").eq("id_subcategoria", id_subcategoria).eq("id_usuario", uid).execute()
    if not res.data:
        raise HTTPException(status_code=400, detail=f"La subcategoría {id_subcategoria} no existe")


def _registro_propio(id_registro: int, uid: str):
    res = supabase.table("planificacion").select("id_registro").eq("id_registro", id_registro).eq("id_usuario", uid).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Registro no encontrado")


def _fila(plan: PlanificacionUpdate) -> dict:
    return {
        "tipo": plan.tipo,
        "nombre_concepto": plan.nombre_concepto,
        "monto": plan.monto,
        "dia_mes": plan.dia_mes,
        "id_subcategoria": plan.id_subcategoria,
        "fecha_inicio": plan.fecha_inicio.isoformat(),
        "fecha_fin": plan.fecha_fin.isoformat() if plan.fecha_fin else None,
        "periodicidad": plan.periodicidad,
    }


@router.get("/")
def obtener_planificacion(uid: str = Depends(usuario_actual)):
    res = supabase.table("planificacion").select("*").eq("id_usuario", uid).order("id_registro").execute()
    # Nombres de campo que espera planificacion.js
    return [{
        "ID_Registro": p["id_registro"],
        "ID_Usuario": p["id_usuario"],
        "Tipo": p["tipo"],
        "Nombre_Concepto": p["nombre_concepto"],
        "Monto": float(p["monto"]),
        "Dia_Mes": p.get("dia_mes"),
        "ID_Subcategoria": p["id_subcategoria"],
        "Fecha_Inicio": p.get("fecha_inicio"),
        "Fecha_Fin": p.get("fecha_fin"),
        "Periodicidad": p.get("periodicidad"),
        "Activo": p.get("activo"),
    } for p in res.data]


@router.post("/")
def crear_planificacion(plan: Planificacion, uid: str = Depends(usuario_actual)):
    _validar_subcategoria(plan.id_subcategoria, uid)
    res = supabase.table("planificacion").insert({"id_usuario": uid, **_fila(plan), "activo": plan.activo}).execute()
    return {"mensaje": "Planificación guardada", "id_registro": res.data[0]["id_registro"]}


@router.put("/{id_registro}")
def editar_planificacion(id_registro: int, plan: PlanificacionUpdate, uid: str = Depends(usuario_actual)):
    _validar_subcategoria(plan.id_subcategoria, uid)
    res = supabase.table("planificacion").update(_fila(plan)).eq("id_registro", id_registro).eq("id_usuario", uid).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    return {"mensaje": "Planificación actualizada"}


@router.put("/{id_registro}/activo")
def cambiar_activo(id_registro: int, datos: ActivoUpdate, uid: str = Depends(usuario_actual)):
    res = supabase.table("planificacion").update({"activo": datos.activo}).eq("id_registro", id_registro).eq("id_usuario", uid).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    return {"mensaje": "Registro activado" if datos.activo == "Sí" else "Registro pausado"}


# ---------- Ajuste del valor de un concepto solo para un mes ----------
# En Supabase la tabla ajustes_mes enlaza el concepto con la columna id_planificacion.

@router.put("/{id_registro}/ajuste/{anio}/{mes}")
def ajustar_mes(id_registro: int, anio: int, mes: int, ajuste: AjusteMes, uid: str = Depends(usuario_actual)):
    if not 1 <= mes <= 12:
        raise HTTPException(status_code=400, detail="El mes debe estar entre 1 y 12")
    _registro_propio(id_registro, uid)
    existente = (supabase.table("ajustes_mes").select("id_ajuste").eq("id_planificacion", id_registro)
                 .eq("anio", anio).eq("mes", mes).eq("id_usuario", uid).execute().data)
    if existente:
        supabase.table("ajustes_mes").update({"monto": ajuste.monto}).eq("id_ajuste", existente[0]["id_ajuste"]).execute()
    else:
        supabase.table("ajustes_mes").insert({
            "id_usuario": uid, "id_planificacion": id_registro, "anio": anio, "mes": mes, "monto": ajuste.monto,
        }).execute()
    return {"mensaje": "Valor del mes ajustado"}


@router.delete("/{id_registro}/ajuste/{anio}/{mes}")
def quitar_ajuste_mes(id_registro: int, anio: int, mes: int, uid: str = Depends(usuario_actual)):
    _registro_propio(id_registro, uid)
    (supabase.table("ajustes_mes").delete().eq("id_planificacion", id_registro)
     .eq("anio", anio).eq("mes", mes).eq("id_usuario", uid).execute())
    return {"mensaje": "Se volvió al valor planeado"}


@router.delete("/{id_registro}")
def eliminar_planificacion(id_registro: int, uid: str = Depends(usuario_actual)):
    """Elimina el concepto y sus ajustes mensuales."""
    _registro_propio(id_registro, uid)
    supabase.table("ajustes_mes").delete().eq("id_planificacion", id_registro).eq("id_usuario", uid).execute()
    supabase.table("planificacion").delete().eq("id_registro", id_registro).eq("id_usuario", uid).execute()
    return {"mensaje": "Registro eliminado"}
