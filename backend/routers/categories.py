from fastapi import APIRouter, Depends, HTTPException
from backend.models import Categoria, Subcategoria
from backend.seguridad import usuario_actual
from backend.database import supabase

router = APIRouter(prefix="/categorias", tags=["Categorias"])

def _validar_categoria_padre(id_categoria: int, uid: str):
    res = supabase.table("categorias").select("id_categoria").eq("id_categoria", id_categoria).eq("id_usuario", uid).execute()
    if not res.data:
        raise HTTPException(status_code=400, detail=f"La categoría {id_categoria} no existe")

@router.get("/")
def obtener_categorias(uid: str = Depends(usuario_actual)):
    cat_res = supabase.table("categorias").select("*").eq("id_usuario", uid).execute()
    sub_res = supabase.table("subcategorias").select("*").eq("id_usuario", uid).execute()
    
    # Mapeamos los nombres de columnas para que coincidan exactamente con lo que espera tu Frontend
    categorias = [{
        "ID_Categoria": c["id_categoria"],
        "ID_Usuario": c["id_usuario"],
        "Nombre_Categoria": c["nombre_categoria"],
        "Tipo_Movimiento": c["tipo_movimiento"]
    } for c in cat_res.data]
    
    subcategorias = [{
        "ID_Subcategoria": s["id_subcategoria"],
        "ID_Usuario": s["id_usuario"],
        "ID_Categoria": s["id_categoria"],
        "Nombre_Subcategoria": s["nombre_subcategoria"]
    } for s in sub_res.data]
    
    return {
        "categorias": categorias,
        "subcategorias": subcategorias,
    }

@router.post("/plantilla")
def cargar_plantilla(uid: str = Depends(usuario_actual)):
    """Carga las categorías estándar directamente en Supabase."""
    exist = supabase.table("categorias").select("id_categoria").eq("id_usuario", uid).limit(1).execute()
    if exist.data:
        raise HTTPException(status_code=409, detail="Ya tienes categorías: la plantilla solo se carga en una cuenta vacía")
    
    plantilla = [
        ("Vivienda", "Gasto", ["Arriendo", "Servicios Públicos"]),
        ("Transporte", "Gasto", ["Gasolina", "Transporte Público"]),
        ("Alimentación", "Gasto", ["Mercado", "Restaurantes"]),
        ("Ingresos Laborales", "Ingreso", ["Salario", "Bonificaciones"])
    ]
    
    n_cat, n_sub = 0, 0
    for nom_cat, tipo_mov, subs in plantilla:
        res_c = supabase.table("categorias").insert({
            "id_usuario": uid, "nombre_categoria": nom_cat, "tipo_movimiento": tipo_mov
        }).execute()
        
        id_cat = res_c.data[0].get("id_categoria") or res_c.data[0].get("id")
        n_cat += 1
        
        for nom_sub in subs:
            supabase.table("subcategorias").insert({
                "id_usuario": uid, "id_categoria": id_cat, "nombre_subcategoria": nom_sub
            }).execute()
            n_sub += 1
            
    return {"mensaje": f"Se cargaron {n_cat} categorías y {n_sub} subcategorías estándar"}

# ---------- Categorías ----------

@router.post("/")
def crear_categoria(cat: Categoria, uid: str = Depends(usuario_actual)):
    res = supabase.table("categorias").insert({
        "id_usuario": uid,
        "nombre_categoria": cat.nombre_categoria,
        "tipo_movimiento": cat.tipo_movimiento
    }).execute()
    nuevo_id = res.data[0].get("id_categoria") or res.data[0].get("id")
    return {"mensaje": "Categoría creada", "id_categoria": nuevo_id}

@router.put("/{id_categoria}")
def editar_categoria(id_categoria: int, cat: Categoria, uid: str = Depends(usuario_actual)):
    res = supabase.table("categorias").update({
        "nombre_categoria": cat.nombre_categoria,
        "tipo_movimiento": cat.tipo_movimiento
    }).eq("id_categoria", id_categoria).eq("id_usuario", uid).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    return {"mensaje": "Categoría actualizada"}

@router.delete("/{id_categoria}")
def eliminar_categoria(id_categoria: int, uid: str = Depends(usuario_actual)):
    sub_res = supabase.table("subcategorias").select("id_subcategoria").eq("id_categoria", id_categoria).execute()
    if sub_res.data:
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
        "id_usuario": uid,
        "id_categoria": sub.id_categoria,
        "nombre_subcategoria": sub.nombre_subcategoria
    }).execute()
    nuevo_id = res.data[0].get("id_subcategoria") or res.data[0].get("id")
    return {"mensaje": "Subcategoría creada", "id_subcategoria": nuevo_id}

@router.put("/subcategoria/{id_subcategoria}")
def editar_subcategoria(id_subcategoria: int, sub: Subcategoria, uid: str = Depends(usuario_actual)):
    _validar_categoria_padre(sub.id_categoria, uid)
    res = supabase.table("subcategorias").update({
        "id_categoria": sub.id_categoria,
        "nombre_subcategoria": sub.nombre_subcategoria
    }).eq("id_subcategoria", id_subcategoria).eq("id_usuario", uid).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Subcategoría no encontrada")
    return {"mensaje": "Subcategoría actualizada"}

@router.delete("/subcategoria/{id_subcategoria}")
def eliminar_subcategoria(id_subcategoria: int, uid: str = Depends(usuario_actual)):
    t_res = supabase.table("transacciones").select("id_transaccion").eq("id_subcategoria", id_subcategoria).limit(1).execute()
    if t_res.data:
        raise HTTPException(status_code=409, detail="No se puede eliminar: la subcategoría tiene movimientos registrados")
        
    p_res = supabase.table("planificacion").select("id_registro").eq("id_subcategoria", id_subcategoria).limit(1).execute()
    if p_res.data:
        raise HTTPException(status_code=409, detail="No se puede eliminar: la subcategoría se usa en la planificación")
        
    res = supabase.table("subcategorias").delete().eq("id_subcategoria", id_subcategoria).eq("id_usuario", uid).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Subcategoría no encontrada")
    return {"mensaje": "Subcategoría eliminada"}