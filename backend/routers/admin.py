"""Panel de administración: listar usuarios, restablecer su contraseña y suspenderlos o reactivarlos.

Usa el mismo cliente del servidor (clave secret de Supabase), que ya tiene permisos de administración
de Auth. Los administradores se definen con la variable de entorno ADMIN_EMAILS (correos separados
por coma); si no está, el administrador es el dueño de la app.
"""
import logging
import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from backend import usuarios
from backend.database import supabase
from backend.routers.auth import _validar_password
from backend.seguridad import usuario_actual

router = APIRouter(prefix="/admin", tags=["Admin"])
logger = logging.getLogger("optifin.admin")

ADMIN_EMAILS = {e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "julianecheverria525@gmail.com").split(",") if e.strip()}

# Suspender = bloquear el inicio de sesión por ~10 años. La sesión abierta del usuario deja de
# renovarse, así que pierde el acceso como máximo cuando vence su token (60 min).
SUSPENSION = "87600h"


def es_admin(uid: str) -> bool:
    return any(u["id"] == uid and u["email"] in ADMIN_EMAILS for u in usuarios.listar())


def verificar_admin(uid: str = Depends(usuario_actual)) -> str:
    if not es_admin(uid):
        raise HTTPException(status_code=403, detail="Acceso denegado. Área exclusiva de administración.")
    return uid


def _usuario_existente(id_usuario: str):
    if not any(u["id"] == id_usuario for u in usuarios.listar()):
        raise HTTPException(status_code=404, detail="Usuario no encontrado")


@router.get("/soy-admin")
def soy_admin(uid: str = Depends(usuario_actual)):
    """Para que el menú muestre (o no) el enlace al panel."""
    return {"admin": es_admin(uid)}


@router.get("/usuarios")
def listar_usuarios(uid: str = Depends(verificar_admin)):
    resultado, pagina = [], 1
    while True:
        lote = supabase.auth.admin.list_users(page=pagina, per_page=1000)
        for u in lote:
            meta = u.user_metadata or {}
            baneado = getattr(u, "banned_until", None)
            resultado.append({
                "id": u.id,
                "email": u.email,
                "nombre": meta.get("nombre") or meta.get("name") or (u.email or "").split("@")[0],
                "ultimo_ingreso": u.last_sign_in_at.isoformat() if u.last_sign_in_at else None,
                "confirmado": bool(u.email_confirmed_at),
                "activo": not baneado,
                "es_tu_cuenta": u.id == uid,
            })
        if len(lote) < 1000:
            break
        pagina += 1
    return sorted(resultado, key=lambda u: (u["nombre"] or "").casefold())


class PasswordUpdate(BaseModel):
    password: str

    _password = field_validator("password")(_validar_password)


@router.put("/usuarios/{id_usuario}/password")
def restaurar_password(id_usuario: str, data: PasswordUpdate, uid: str = Depends(verificar_admin)):
    _usuario_existente(id_usuario)
    supabase.auth.admin.update_user_by_id(id_usuario, {"password": data.password})
    logger.info("Admin %s restableció la contraseña de %s", uid, id_usuario)
    return {"mensaje": "Contraseña actualizada"}


class EstadoUpdate(BaseModel):
    activo: bool


@router.put("/usuarios/{id_usuario}/estado")
def cambiar_estado(id_usuario: str, data: EstadoUpdate, uid: str = Depends(verificar_admin)):
    if id_usuario == uid and not data.activo:
        raise HTTPException(status_code=400, detail="No puedes suspender tu propia cuenta.")
    _usuario_existente(id_usuario)
    supabase.auth.admin.update_user_by_id(id_usuario, {"ban_duration": "none" if data.activo else SUSPENSION})
    usuarios.invalidar()
    logger.info("Admin %s %s a %s", uid, "reactivó" if data.activo else "suspendió", id_usuario)
    return {"mensaje": "Usuario reactivado" if data.activo else "Usuario suspendido"}
