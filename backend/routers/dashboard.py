from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from backend import finanzas
from backend.seguridad import usuario_actual

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/resumen/{mes}/{anio}")
def obtener_resumen(mes: int, anio: int, uid: int = Depends(usuario_actual)):
    if not 1 <= mes <= 12:
        raise HTTPException(status_code=400, detail="El mes debe estar entre 1 y 12")

    resumen = finanzas.resumen_mes(mes, anio, uid)
    patrimonio = finanzas.patrimonio(uid)

    # En el mes en curso, la proyección parte del dinero que hay hoy en las cuentas (incluye los
    # saldos iniciales), no solo de lo registrado en el mes: así funciona aunque no haya historial.
    hoy = date.today()
    p = resumen["proyeccion"]
    p["es_mes_actual"] = (anio, mes) == (hoy.year, hoy.month)
    p["disponible_hoy"] = patrimonio["en_cuentas"]
    p["saldo_fin_mes"] = patrimonio["en_cuentas"] + p["por_recibir"] - p["por_pagar"] - p["presupuesto_restante"]

    return {
        **resumen,
        "patrimonio": patrimonio,
        "deudas_por_persona": finanzas.deudas_por_persona(uid),
    }
