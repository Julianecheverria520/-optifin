"""Plantilla de categorías y subcategorías que recibe cada usuario nuevo.

Es una copia fija guardada en las hojas Plantilla_Categorias / Plantilla_Subcategorias:
si un usuario cambia sus propias categorías, la plantilla no se altera.
"""
from backend import excel_store as db

HOJA_CAT = "Plantilla_Categorias"
HOJA_SUB = "Plantilla_Subcategorias"
COLUMNAS_CAT = ["ID_Categoria", "Nombre_Categoria", "Tipo_Movimiento"]
COLUMNAS_SUB = ["ID_Subcategoria", "ID_Categoria", "Nombre_Subcategoria"]


def _filas(ws):
    return [r for r in range(2, ws.max_row + 1) if ws.cell(row=r, column=1).value is not None]


def aplicar_plantilla(wb, id_usuario: int) -> tuple[int, int]:
    """Copia la plantilla a las categorías del usuario (dentro de un libro abierto para edición).
    Devuelve (categorías creadas, subcategorías creadas)."""
    ws_pc, ws_ps = wb[HOJA_CAT], wb[HOJA_SUB]
    ids_nuevos = {}
    for r in _filas(ws_pc):
        ids_nuevos[db.valor(ws_pc, r, "ID_Categoria")] = db.agregar(wb["Categorias"], {
            "ID_Usuario": id_usuario,
            "Nombre_Categoria": db.valor(ws_pc, r, "Nombre_Categoria"),
            "Tipo_Movimiento": db.valor(ws_pc, r, "Tipo_Movimiento"),
        })
    creadas = 0
    for r in _filas(ws_ps):
        id_cat = ids_nuevos.get(db.valor(ws_ps, r, "ID_Categoria"))
        if id_cat is None:
            continue
        db.agregar(wb["Subcategorias"], {
            "ID_Usuario": id_usuario,
            "ID_Categoria": id_cat,
            "Nombre_Subcategoria": db.valor(ws_ps, r, "Nombre_Subcategoria"),
        })
        creadas += 1
    return len(ids_nuevos), creadas


def guardar_como_plantilla(wb, id_usuario: int) -> tuple[int, int]:
    """Reemplaza la plantilla por las categorías actuales de un usuario."""
    ws_pc, ws_ps = wb[HOJA_CAT], wb[HOJA_SUB]
    for ws in (ws_pc, ws_ps):
        if ws.max_row > 1:
            ws.delete_rows(2, ws.max_row - 1)

    ws_c, ws_s = wb["Categorias"], wb["Subcategorias"]
    ids_plantilla = {}
    for r in _filas(ws_c):
        if db.valor(ws_c, r, "ID_Usuario") != id_usuario:
            continue
        ids_plantilla[db.valor(ws_c, r, "ID_Categoria")] = db.agregar(ws_pc, {
            "Nombre_Categoria": db.valor(ws_c, r, "Nombre_Categoria"),
            "Tipo_Movimiento": db.valor(ws_c, r, "Tipo_Movimiento"),
        })
    creadas = 0
    for r in _filas(ws_s):
        id_cat = ids_plantilla.get(db.valor(ws_s, r, "ID_Categoria"))
        if db.valor(ws_s, r, "ID_Usuario") != id_usuario or id_cat is None:
            continue
        db.agregar(ws_ps, {"ID_Categoria": id_cat, "Nombre_Subcategoria": db.valor(ws_s, r, "Nombre_Subcategoria")})
        creadas += 1
    return len(ids_plantilla), creadas
