from fastapi import APIRouter, Depends, HTTPException
from backend import excel_store as db
from backend import plantilla
from backend.models import Categoria, Subcategoria
from backend.seguridad import usuario_actual

router = APIRouter(prefix="/categorias", tags=["Categorias"])


def _fila_categoria(cat: Categoria, uid: int) -> dict:
    return {
        "ID_Usuario": uid,
        "Nombre_Categoria": cat.nombre_categoria,
        "Tipo_Movimiento": cat.tipo_movimiento,
    }


def _fila_subcategoria(sub: Subcategoria, uid: int) -> dict:
    return {
        "ID_Usuario": uid,
        "ID_Categoria": sub.id_categoria,
        "Nombre_Subcategoria": sub.nombre_subcategoria,
    }


def _validar_categoria_padre(wb, id_categoria: int, uid: int):
    if db.fila_propia(wb["Categorias"], id_categoria, uid) is None:
        raise HTTPException(status_code=400, detail=f"La categoría {id_categoria} no existe")


@router.get("/")
def obtener_categorias(uid: int = Depends(usuario_actual)):
    return {
        "categorias": db.a_registros(db.solo_usuario(db.leer_hoja("Categorias"), uid)),
        "subcategorias": db.a_registros(db.solo_usuario(db.leer_hoja("Subcategorias"), uid)),
    }


@router.post("/plantilla")
def cargar_plantilla(uid: int = Depends(usuario_actual)):
    """Carga las categorías estándar a un usuario que no tiene ninguna."""
    with db.editar_libro() as wb:
        if db.existe_valor(wb["Categorias"], "ID_Usuario", uid):
            raise HTTPException(status_code=409, detail="Ya tienes categorías: la plantilla solo se carga en una cuenta vacía")
        n_cat, n_sub = plantilla.aplicar_plantilla(wb, uid)
    return {"mensaje": f"Se cargaron {n_cat} categorías y {n_sub} subcategorías estándar"}


# ---------- Categorías ----------

@router.post("/")
def crear_categoria(cat: Categoria, uid: int = Depends(usuario_actual)):
    with db.editar_libro() as wb:
        nuevo_id = db.agregar(wb["Categorias"], _fila_categoria(cat, uid))
    return {"mensaje": "Categoría creada", "id_categoria": nuevo_id}


@router.put("/{id_categoria}")
def editar_categoria(id_categoria: int, cat: Categoria, uid: int = Depends(usuario_actual)):
    with db.editar_libro() as wb:
        ws = wb["Categorias"]
        db.actualizar(ws, db.fila_propia_o_404(ws, id_categoria, uid, "Categoría"), _fila_categoria(cat, uid))
    return {"mensaje": "Categoría actualizada"}


@router.delete("/{id_categoria}")
def eliminar_categoria(id_categoria: int, uid: int = Depends(usuario_actual)):
    with db.editar_libro() as wb:
        ws = wb["Categorias"]
        fila = db.fila_propia_o_404(ws, id_categoria, uid, "Categoría")
        if db.existe_valor(wb["Subcategorias"], "ID_Categoria", id_categoria):
            raise HTTPException(status_code=409, detail="No se puede eliminar: la categoría tiene subcategorías. Elimínalas primero")
        db.eliminar(ws, fila)
    return {"mensaje": "Categoría eliminada"}


# ---------- Subcategorías ----------

@router.post("/subcategoria")
def crear_subcategoria(sub: Subcategoria, uid: int = Depends(usuario_actual)):
    with db.editar_libro() as wb:
        _validar_categoria_padre(wb, sub.id_categoria, uid)
        nuevo_id = db.agregar(wb["Subcategorias"], _fila_subcategoria(sub, uid))
    return {"mensaje": "Subcategoría creada", "id_subcategoria": nuevo_id}


@router.put("/subcategoria/{id_subcategoria}")
def editar_subcategoria(id_subcategoria: int, sub: Subcategoria, uid: int = Depends(usuario_actual)):
    with db.editar_libro() as wb:
        _validar_categoria_padre(wb, sub.id_categoria, uid)
        ws = wb["Subcategorias"]
        db.actualizar(ws, db.fila_propia_o_404(ws, id_subcategoria, uid, "Subcategoría"), _fila_subcategoria(sub, uid))
    return {"mensaje": "Subcategoría actualizada"}


@router.delete("/subcategoria/{id_subcategoria}")
def eliminar_subcategoria(id_subcategoria: int, uid: int = Depends(usuario_actual)):
    with db.editar_libro() as wb:
        ws = wb["Subcategorias"]
        fila = db.fila_propia_o_404(ws, id_subcategoria, uid, "Subcategoría")
        if db.existe_valor(wb["Transacciones"], "ID_Subcategoria", id_subcategoria):
            raise HTTPException(status_code=409, detail="No se puede eliminar: la subcategoría tiene movimientos registrados")
        if db.existe_valor(wb["Presupuestos_y_Fijos"], "ID_Subcategoria", id_subcategoria):
            raise HTTPException(status_code=409, detail="No se puede eliminar: la subcategoría se usa en la planificación")
        db.eliminar(ws, fila)
    return {"mensaje": "Subcategoría eliminada"}
