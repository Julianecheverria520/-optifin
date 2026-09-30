from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from backend.models import LiquidacionNueva
from backend.routers.debts import actualizar_estado, total_abonado
from backend.seguridad import usuario_actual
from backend.database import supabase

router = APIRouter(prefix="/liquidaciones", tags=["Liquidaciones"])
TOLERANCIA = 0.5 

def _pendientes(uid: str, persona: str = None, ids: set = None):
    query = supabase.table("deudas").select("*").or_(f"id_usuario.eq.{uid},id_usuario_contraparte.eq.{uid}")
    if persona: query = query.ilike("persona", persona)
    res = query.execute()
    
    resultado = []
    for d in res.data:
        id_deuda = d['id_deuda']
        if ids is not None and id_deuda not in ids: continue
        
        dueno = d['id_usuario']
        contraparte = d['id_usuario_contraparte']
        tipo = d['tipo_deuda']
        
        if dueno == uid:
            persona_vista, id_otro = d['persona'], contraparte
        elif contraparte == uid:
            persona_vista, id_otro = "Otro usuario", dueno
            tipo = "Le debo" if tipo == "Me debe" else "Me debe"
        else:
            continue
            
        saldo = float(d['monto']) - total_abonado(id_deuda)
        if saldo > TOLERANCIA and d['estado'] != 'Pagada':
            resultado.append({
                "id_deuda": id_deuda,
                "dueno": dueno,
                "tipo": tipo,
                "persona": persona_vista,
                "id_usuario_contraparte": id_otro,
                "fecha": d['fecha_creacion'],
                "descripcion": d['descripcion'],
                "saldo": saldo,
            })
    return sorted(resultado, key=lambda d: (d["fecha"], d["id_deuda"]))

def _calculo(pendientes: list) -> dict:
    me_deben = sum(d["saldo"] for d in pendientes if d["tipo"] == "Me debe")
    debo = sum(d["saldo"] for d in pendientes if d["tipo"] == "Le debo")
    return {
        "total_me_deben": me_deben,
        "total_debo": debo,
        "monto_cruzado": min(me_deben, debo),
        "neto": me_deben - debo
    }

def _aplicar(id_liquidacion: int, pendientes: list, monto_cruzado: float):
    hoy = date.today().strftime("%Y-%m-%d")
    for tipo in ("Me debe", "Le debo"):
        restante = monto_cruzado
        for d in (d for d in pendientes if d["tipo"] == tipo):
            if restante <= TOLERANCIA: break
            abono = min(d["saldo"], restante)
            
            supabase.table("abonos").insert({
                "id_usuario": d["dueno"],
                "id_deuda": d["id_deuda"],
                "fecha": hoy,
                "monto": round(abono, 2),
                "id_cuenta": None,
                "descripcion": f"Cruce de cuentas #{id_liquidacion}",
            }).execute()
            
            actualizar_estado(d["id_deuda"])
            restante -= abono

@router.get("/")
def obtener_liquidaciones(uid: str = Depends(usuario_actual)):
    res = supabase.table("liquidaciones").select("*").or_(f"id_usuario.eq.{uid},id_usuario_contraparte.eq.{uid}").order("id_liquidacion", desc=True).execute()
    
    resultado = []
    for l in res.data:
        if l["id_usuario"] == uid:
            resultado.append({
                "ID_Liquidacion": l['id_liquidacion'],
                "Persona": l['persona'],
                "Fecha": l['fecha'],
                "Monto_Cruzado": float(l['monto_cruzado']),
                "Total_Me_Deben": float(l['total_me_deben'] or 0),
                "Total_Debo": float(l['total_debo'] or 0),
                "Neto": float(l['neto'] or 0),
                "Estado": l['estado'],
                "Soy_Proponente": True,
                "ID_Usuario": l['id_usuario'],
                "ID_Usuario_Contraparte": l['id_usuario_contraparte']
            })
        else:
            resultado.append({
                "ID_Liquidacion": l['id_liquidacion'],
                "Persona": "Otro usuario",
                "Fecha": l['fecha'],
                "Monto_Cruzado": float(l['monto_cruzado']),
                "Total_Me_Deben": float(l['total_debo'] or 0),
                "Total_Debo": float(l['total_me_deben'] or 0),
                "Neto": -(float(l['neto'] or 0)),
                "Estado": l['estado'],
                "Soy_Proponente": False,
                "ID_Usuario": l['id_usuario'],
                "ID_Usuario_Contraparte": l['id_usuario_contraparte']
            })
    return resultado

@router.get("/vista-previa")
def vista_previa(persona: str, uid: str = Depends(usuario_actual)):
    pendientes = _pendientes(uid, persona=persona)
    contraparte = next((d['id_usuario_contraparte'] for d in pendientes if d.get('id_usuario_contraparte')), None)
    
    return {
        "persona": persona,
        "id_usuario_contraparte": contraparte,
        "requiere_aprobacion": contraparte is not None,
        "me_deben": [d for d in pendientes if d["tipo"] == "Me debe"],
        "debo": [d for d in pendientes if d["tipo"] == "Le debo"],
        **_calculo(pendientes),
    }

@router.post("/")
def proponer_liquidacion(datos: LiquidacionNueva, uid: str = Depends(usuario_actual)):
    pendientes = _pendientes(uid, persona=datos.persona)
    calculo = _calculo(pendientes)
    
    if calculo["monto_cruzado"] <= TOLERANCIA:
        raise HTTPException(status_code=400, detail="No hay nada que cruzar: solo hay deudas en un sentido.")
        
    contraparte = next((d['id_usuario_contraparte'] for d in pendientes if d.get('id_usuario_contraparte')), None)
    
    # Prevenir cruces duplicados
    existentes = supabase.table("liquidaciones").select("id_liquidacion").eq("estado", "Pendiente").or_(f"id_usuario.eq.{uid},id_usuario_contraparte.eq.{uid}").execute()
    if existentes.data:
        raise HTTPException(status_code=409, detail="Ya hay un cruce pendiente con esta persona.")

    res = supabase.table("liquidaciones").insert({
        "id_usuario": uid,
        "persona": pendientes[0]["persona"],
        "id_usuario_contraparte": contraparte,
        "fecha": date.today().strftime("%Y-%m-%d"),
        "total_me_deben": calculo["total_me_deben"],
        "total_debo": calculo["total_debo"],
        "monto_cruzado": calculo["monto_cruzado"],
        "neto": calculo["neto"],
        "estado": "Pendiente" if contraparte else "Aplicada",
        "deudas": ",".join(str(d["id_deuda"]) for d in pendientes),
        "fecha_resolucion": None if contraparte else date.today().strftime("%Y-%m-%d"),
    }).execute()
    
    nuevo_id = res.data[0]['id_liquidacion']
    
    if not contraparte:
        _aplicar(nuevo_id, pendientes, calculo["monto_cruzado"])
        return {"mensaje": "Cruce de cuentas aplicado", "id_liquidacion": nuevo_id}
        
    return {"mensaje": f"Cruce propuesto. Queda pendiente de que {pendientes[0]['persona']} lo apruebe.", "id_liquidacion": nuevo_id}

@router.post("/{id_liquidacion}/aprobar")
def aprobar_liquidacion(id_liquidacion: int, uid: str = Depends(usuario_actual)):
    l_res = supabase.table("liquidaciones").select("*").eq("id_liquidacion", id_liquidacion).execute()
    if not l_res.data: raise HTTPException(status_code=404, detail="Liquidación no encontrada")
    
    liq = l_res.data[0]
    if liq['estado'] != 'Pendiente': raise HTTPException(status_code=409, detail="Esta liquidación ya no está pendiente")
    if uid != liq['id_usuario_contraparte']: raise HTTPException(status_code=403, detail="Solo la otra persona puede aprobar este cruce")

    ids = {int(i) for i in str(liq['deudas'] or "").split(",") if i.strip()}
    pendientes = _pendientes(liq['id_usuario'], ids=ids)
    calculo = _calculo(pendientes)
    
    if (abs(calculo["total_me_deben"] - float(liq["total_me_deben"])) > TOLERANCIA or 
        abs(calculo["total_debo"] - float(liq["total_debo"])) > TOLERANCIA):
        raise HTTPException(status_code=409, detail="Los saldos cambiaron desde que se propuso el cruce. Pide que lo anulen y propongan uno nuevo.")

    _aplicar(id_liquidacion, pendientes, calculo["monto_cruzado"])
    supabase.table("liquidaciones").update({"estado": "Aplicada", "fecha_resolucion": date.today().strftime("%Y-%m-%d")}).eq("id_liquidacion", id_liquidacion).execute()
    return {"mensaje": "Cruce aprobado y aplicado"}

@router.post("/{id_liquidacion}/rechazar")
def rechazar_liquidacion(id_liquidacion: int, uid: str = Depends(usuario_actual)):
    supabase.table("liquidaciones").update({"estado": "Rechazada", "fecha_resolucion": date.today().strftime("%Y-%m-%d")}).eq("id_liquidacion", id_liquidacion).eq("id_usuario_contraparte", uid).execute()
    return {"mensaje": "Cruce rechazado"}

@router.post("/{id_liquidacion}/anular")
def anular_liquidacion(id_liquidacion: int, uid: str = Depends(usuario_actual)):
    supabase.table("liquidaciones").update({"estado": "Anulada", "fecha_resolucion": date.today().strftime("%Y-%m-%d")}).eq("id_liquidacion", id_liquidacion).eq("id_usuario", uid).execute()
    return {"mensaje": "Cruce anulado"}