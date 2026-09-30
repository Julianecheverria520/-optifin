from fastapi import APIRouter, Depends, HTTPException
from backend.models import Cuenta
from backend.seguridad import usuario_actual
from backend.database import supabase

router = APIRouter(prefix="/cuentas", tags=["Cuentas"])

@router.get("/")
def obtener_cuentas_con_saldos(uid: str = Depends(usuario_actual)):
    cuentas_res = supabase.table("cuentas").select("*").eq("id_usuario", uid).execute()
    trans_res = supabase.table("transacciones").select("*").eq("id_usuario", uid).execute()
    
    cuentas = cuentas_res.data
    transacciones = trans_res.data
    
    resultados = []
    for c in cuentas:
        id_c = c['id_cuenta']
        saldo = float(c['saldo_inicial'])
        
        gastos = sum(float(t['monto']) for t in transacciones if t['tipo_movimiento'] == 'Gasto' and t['id_cuenta_origen'] == id_c)
        ingresos = sum(float(t['monto']) for t in transacciones if t['tipo_movimiento'] == 'Ingreso' and t['id_cuenta_destino'] == id_c)
        traslados_sal = sum(float(t['monto']) for t in transacciones if t['tipo_movimiento'] == 'Traslado' and t['id_cuenta_origen'] == id_c)
        traslados_ent = sum(float(t['monto']) for t in transacciones if t['tipo_movimiento'] == 'Traslado' and t['id_cuenta_destino'] == id_c)
        
        resultados.append({
            "id_cuenta": id_c,
            "nombre": c['nombre_cuenta'],
            "tipo": c['tipo_cuenta'],
            "saldo_inicial": saldo,
            "saldo_actual": saldo + ingresos - gastos + traslados_ent - traslados_sal
        })
    return resultados

@router.post("/")
def crear_cuenta(cuenta: Cuenta, uid: str = Depends(usuario_actual)):
    try:
        res = supabase.table("cuentas").insert({
            "id_usuario": uid,
            "nombre_cuenta": cuenta.nombre_cuenta,
            "tipo_cuenta": cuenta.tipo_cuenta,
            "saldo_inicial": cuenta.saldo_inicial
        }).execute()
        return {"mensaje": "Cuenta creada exitosamente", "id_cuenta": res.data[0]['id_cuenta']}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{id_cuenta}")
def editar_cuenta(id_cuenta: int, cuenta: Cuenta, uid: str = Depends(usuario_actual)):
    try:
        supabase.table("cuentas").update({
            "nombre_cuenta": cuenta.nombre_cuenta,
            "tipo_cuenta": cuenta.tipo_cuenta,
            "saldo_inicial": cuenta.saldo_inicial
        }).eq("id_cuenta", id_cuenta).eq("id_usuario", uid).execute()
        return {"mensaje": "Cuenta actualizada"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{id_cuenta}")
def eliminar_cuenta(id_cuenta: int, uid: str = Depends(usuario_actual)):
    try:
        supabase.table("cuentas").delete().eq("id_cuenta", id_cuenta).eq("id_usuario", uid).execute()
        return {"mensaje": "Cuenta eliminada"}
    except Exception:
        raise HTTPException(status_code=409, detail="No se puede eliminar: la cuenta está asociada a transacciones, deudas o abonos.")