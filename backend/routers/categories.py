from fastapi import APIRouter, Depends, HTTPException

from backend import plantilla
from backend.database import supabase
from backend.models import Categoria, Subcategoria
from backend.seguridad import usuario_actual

router = APIRouter(prefix="/categorias", tags=["Categorias"])


def _validar_categoria_padre(id_categoria: int, uid: str):
    res = supabase.table("categorias").select("id_categoria").eq("id_categoria", id_categoria).eq("id_usuario", uid).execute()
    if not res.data:
        raise HTTPException(status_code=400, detail=f"La categoría {id_categoria} no existe")


@router.get("/")
def obtener_categorias(uid: str = Depends(usuario_actual)):
    cats = supabase.table("categorias").select("*").eq("id_usuario", uid).order("id_categoria").execute().data
    subs = supabase.table("subcategorias").select("*").eq("id_usuario", uid).order("id_subcategoria").execute().data
    # Nombres de campo que espera el frontend
    return {
        "categorias": [{"ID_Categoria": c["id_categoria"], "ID_Usuario": c["id_usuario"],
                        "Nombre_Categoria": c["nombre_categoria"], "Tipo_Movimiento": c["tipo_movimiento"]} for c in cats],
        "subcategorias": [{"ID_Subcategoria": s["id_subcategoria"], "ID_Usuario": s["id_usuario"],
                           "ID_Categoria": s["id_categoria"], "Nombre_Subcategoria": s["nombre_subcategoria"]} for s in subs],
    }


@router.post("/plantilla")
def cargar_plantilla(uid: str = Depends(usuario_actual)):
    """Carga las categorías estándar a un usuario que no tiene ninguna."""
    if plantilla.tiene_categorias(uid):
        raise HTTPException(status_code=409, detail="Ya tienes categorías: la plantilla solo se carga en una cuenta vacía")
    n_cat, n_sub = plantilla.aplicar_plantilla(uid)
    return {"mensaje": f"Se cargaron {n_cat} categorías y {n_sub} subcategorías estándar"}


# ---------- Categorías ----------

@router.post("/")
def crear_categoria(cat: Categoria, uid: str = Depends(usuario_actual)):
    res = supabase.table("categorias").insert({
        "id_usuario": uid, "nombre_categoria": cat.nombre_categoria, "tipo_movimiento": cat.tipo_movimiento,
    }).execute()
    return {"mensaje": "Categoría creada", "id_categoria": res.data[0]["id_categoria"]}


@router.put("/{id_categoria}")
def editar_categoria(id_categoria: int, cat: Categoria, uid: str = Depends(usuario_actual)):
    res = supabase.table("categorias").update({
        "nombre_categoria": cat.nombre_categoria, "tipo_movimiento": cat.tipo_movimiento,
    }).eq("id_categoria", id_categoria).eq("id_usuario", uid).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    return {"mensaje": "Categoría actualizada"}


@router.delete("/{id_categoria}")
def eliminar_categoria(id_categoria: int, uid: str = Depends(usuario_actual)):
    subs = supabase.table("subcategorias").select("id_subcategoria").eq("id_categoria", id_categoria).eq("id_usuario", uid).limit(1).execute()
    if subs.data:
        raise HTTPException(status_code=409, detail="No se puede eliminar: la categoría tiene subcategorías. Elimínalas primero")
    res = supabase.table("categorias").delete().eq("id_categoria", id_categoria).eq("id_usuario", uid).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    return {"mensaje": "Categoría eliminada"}


# ---------- Subcategorías ----------

@router.post("/subcategoria")
def crear_subcategoria(sub: Subcategoria, uid: str = Depends(usuario_actual)):
    _validar_categoria_padre(sub.id_categoria, uid)
    res = supabase.table("subcategorias").insert({
        "id_usuario": uid, "id_categoria": sub.id_categoria, "nombre_subcategoria": sub.nombre_subcategoria,
    }).execute()
    return {"mensaje": "Subcategoría creada", "id_subcategoria": res.data[0]["id_subcategoria"]}


@router.put("/subcategoria/{id_subcategoria}")
def editar_subcategoria(id_subcategoria: int, sub: Subcategoria, uid: str = Depends(usuario_actual)):
    _validar_categoria_padre(sub.id_categoria, uid)
    res = supabase.table("subcategorias").update({
        "id_categoria": sub.id_categoria, "nombre_subcategoria": sub.nombre_subcategoria,
    }).eq("id_subcategoria", id_subcategoria).eq("id_usuario", uid).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Subcategoría no encontrada")
    return {"mensaje": "Subcategoría actualizada"}


@router.delete("/subcategoria/{id_subcategoria}")
def eliminar_subcategoria(id_subcategoria: int, uid: str = Depends(usuario_actual)):
    usada = supabase.table("transacciones").select("id_transaccion").eq("id_subcategoria", id_subcategoria).eq("id_usuario", uid).limit(1).execute()
    if usada.data:
        raise HTTPException(status_code=409, detail="No se puede eliminar: la subcategoría tiene movimientos registrados")
    usada = supabase.table("planificacion").select("id_registro").eq("id_subcategoria", id_subcategoria).eq("id_usuario", uid).limit(1).execute()
    if usada.data:
        raise HTTPException(status_code=409, detail="No se puede eliminar: la subcategoría se usa en la planificación")
    res = supabase.table("subcategorias").delete().eq("id_subcategoria", id_subcategoria).eq("id_usuario", uid).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Subcategoría no encontrada")
    return {"mensaje": "Subcategoría eliminada"}
