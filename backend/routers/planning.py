from fastapi import APIRouter, Depends, HTTPException
from backend import excel_store as db
from backend.models import ActivoUpdate, AjusteMes, Planificacion, PlanificacionUpdate
from backend.seguridad import usuario_actual

router = APIRouter(prefix="/planificacion", tags=["Planificacion"])
HOJA = "Presupuestos_y_Fijos"
HOJA_AJUSTES = "Ajustes_Mes"


def _filas_ajuste(wb, id_registro: int, anio: int | None = None, mes: int | None = None) -> list[int]:
    """Filas de Ajustes_Mes de un registro (de un mes concreto, o de todos si no se indica)."""
    ws = wb[HOJA_AJUSTES]
    return [r for r in range(2, ws.max_row + 1)
            if db.valor(ws, r, "ID_Registro") == id_registro
            and (anio is None or (db.valor(ws, r, "Anio") == anio and db.valor(ws, r, "Mes") == mes))]


def _fila(plan: PlanificacionUpdate, uid: int) -> dict:
    return {
        "ID_Usuario": uid,
        "Tipo": plan.tipo,
        "Nombre_Concepto": plan.nombre_concepto,
        "Monto": plan.monto,
        "Dia_Mes": plan.dia_mes,
        "ID_Subcategoria": plan.id_subcategoria,
        "Fecha_Inicio": plan.fecha_inicio.strftime("%Y-%m-%d"),
        "Fecha_Fin": plan.fecha_fin.strftime("%Y-%m-%d") if plan.fecha_fin else None,
        "Periodicidad": plan.periodicidad,
    }


def _validar_subcategoria(wb, id_subcategoria: int, uid: int):
    if db.fila_propia(wb["Subcategorias"], id_subcategoria, uid) is None:
        raise HTTPException(status_code=400, detail=f"La subcategoría {id_subcategoria} no existe")


@router.get("/")
def obtener_planificacion(uid: int = Depends(usuario_actual)):
    return db.a_registros(db.solo_usuario(db.leer_hoja(HOJA), uid))


@router.post("/")
def crear_planificacion(plan: Planificacion, uid: int = Depends(usuario_actual)):
    with db.editar_libro() as wb:
        _validar_subcategoria(wb, plan.id_subcategoria, uid)
        nuevo_id = db.agregar(wb[HOJA], {**_fila(plan, uid), "Activo": plan.activo})
    return {"mensaje": "Planificación guardada", "id_registro": nuevo_id}


@router.put("/{id_registro}")
def editar_planificacion(id_registro: int, plan: PlanificacionUpdate, uid: int = Depends(usuario_actual)):
    with db.editar_libro() as wb:
        ws = wb[HOJA]
        fila = db.fila_propia_o_404(ws, id_registro, uid, "Registro")
        _validar_subcategoria(wb, plan.id_subcategoria, uid)
        db.actualizar(ws, fila, _fila(plan, uid))
    return {"mensaje": "Planificación actualizada"}


@router.put("/{id_registro}/activo")
def cambiar_activo(id_registro: int, datos: ActivoUpdate, uid: int = Depends(usuario_actual)):
    """Pausa ("No") o reactiva ("Sí") un concepto sin borrarlo. Los pausados no cuentan en el resumen."""
    with db.editar_libro() as wb:
        ws = wb[HOJA]
        db.actualizar(ws, db.fila_propia_o_404(ws, id_registro, uid, "Registro"), {"Activo": datos.activo})
    return {"mensaje": "Registro activado" if datos.activo == "Sí" else "Registro pausado"}


@router.put("/{id_registro}/ajuste/{anio}/{mes}")
def ajustar_mes(id_registro: int, anio: int, mes: int, ajuste: AjusteMes, uid: int = Depends(usuario_actual)):
    """Fija el valor de un concepto solo para ese mes (crea o reemplaza el ajuste)."""
    if not 1 <= mes <= 12:
        raise HTTPException(status_code=400, detail="El mes debe estar entre 1 y 12")
    with db.editar_libro() as wb:
        db.fila_propia_o_404(wb[HOJA], id_registro, uid, "Registro")
        ws = wb[HOJA_AJUSTES]
        filas = _filas_ajuste(wb, id_registro, anio, mes)
        if filas:
            db.actualizar(ws, filas[0], {"Monto": ajuste.monto})
        else:
            db.agregar(ws, {"ID_Usuario": uid, "ID_Registro": id_registro,
                            "Anio": anio, "Mes": mes, "Monto": ajuste.monto})
    return {"mensaje": "Valor del mes ajustado"}


@router.delete("/{id_registro}/ajuste/{anio}/{mes}")
def quitar_ajuste_mes(id_registro: int, anio: int, mes: int, uid: int = Depends(usuario_actual)):
    """Vuelve a usar el valor de la plantilla en ese mes."""
    with db.editar_libro() as wb:
        db.fila_propia_o_404(wb[HOJA], id_registro, uid, "Registro")
        for fila in reversed(_filas_ajuste(wb, id_registro, anio, mes)):
            db.eliminar(wb[HOJA_AJUSTES], fila)
    return {"mensaje": "Se volvió al valor planeado"}


@router.delete("/{id_registro}")
def eliminar_planificacion(id_registro: int, uid: int = Depends(usuario_actual)):
    """Elimina el concepto y sus ajustes mensuales."""
    with db.editar_libro() as wb:
        ws = wb[HOJA]
        fila = db.fila_propia_o_404(ws, id_registro, uid, "Registro")
        for fila_ajuste in reversed(_filas_ajuste(wb, id_registro)):
            db.eliminar(wb[HOJA_AJUSTES], fila_ajuste)
        db.eliminar(ws, fila)
    return {"mensaje": "Registro eliminado"}
