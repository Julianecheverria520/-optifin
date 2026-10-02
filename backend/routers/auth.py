"""Registro, inicio de sesión, renovación de sesión y cambio de contraseña con Supabase Auth.

Login, registro y renovación usan un cliente desechable (cliente_auth): iniciar sesión en el
cliente del servidor cambiaría la identidad de TODAS las consultas de la app (ver database.py).
"""
import logging
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from backend import plantilla, usuarios
from backend.database import cliente_auth, supabase
from backend.seguridad import usuario_actual

logger = logging.getLogger("optifin.auth")
router = APIRouter(prefix="/auth", tags=["Auth"])

PATRON_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _normalizar_email(valor: str) -> str:
    valor = valor.strip().lower()
    if not PATRON_EMAIL.match(valor) or len(valor) > 120:
        raise ValueError("Escribe un correo electrónico válido")
    return valor


def _validar_password(valor: str) -> str:
    if not 6 <= len(valor) <= 128:
        raise ValueError("La contraseña debe tener al menos 6 caracteres")
    return valor


class LoginRequest(BaseModel):
    email: str
    password: str
    recordar: bool = False  # el navegador decide dónde guarda la sesión; aquí no cambia nada

    _email = field_validator("email")(_normalizar_email)


class RegisterRequest(BaseModel):
    nombre: str
    email: str
    password: str

    _email = field_validator("email")(_normalizar_email)
    _password = field_validator("password")(_validar_password)

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, valor: str) -> str:
        valor = valor.strip()
        if not 1 <= len(valor) <= 80:
            raise ValueError("Escribe tu nombre")
        return valor


class RenovarRequest(BaseModel):
    refresh_token: str


class CambioPasswordRequest(BaseModel):
    actual: str
    nueva: str

    _nueva = field_validator("nueva")(_validar_password)


def _sesion(session) -> dict:
    """Lo que el navegador guarda para mantener la sesión: el access token (dura 60 min),
    el refresh token para renovarlo y el momento en que expira (segundos Unix)."""
    return {"token": session.access_token, "refresh_token": session.refresh_token, "expira": session.expires_at}


def _usuario(user) -> dict:
    return {"id": user.id, "nombre": (user.user_metadata or {}).get("nombre", ""), "email": user.email}


# ---------- Endpoints ----------

@router.post("/login")
def login(req: LoginRequest):
    try:
        res = cliente_auth().auth.sign_in_with_password({"email": req.email, "password": req.password})
    except Exception as e:
        if "not confirmed" in str(e).lower():
            raise HTTPException(status_code=401, detail="Aún no has confirmado tu correo. Revisa tu bandeja de entrada.")
        if "banned" in str(e).lower():
            raise HTTPException(status_code=403, detail="Tu cuenta está suspendida. Contacta al administrador.")
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos")
    return {"mensaje": "Login exitoso", "usuario": _usuario(res.user), **_sesion(res.session)}


@router.post("/renovar")
def renovar_sesion(req: RenovarRequest):
    """Cambia el refresh token por una sesión nueva (el navegador lo llama antes de que expire)."""
    try:
        res = cliente_auth().auth.refresh_session(req.refresh_token)
    except Exception:
        raise HTTPException(status_code=401, detail="Tu sesión expiró. Inicia sesión de nuevo.")
    if not res or not res.session:
        raise HTTPException(status_code=401, detail="Tu sesión expiró. Inicia sesión de nuevo.")
    return {"usuario": _usuario(res.user), **_sesion(res.session)}


@router.post("/registro")
def registro(req: RegisterRequest):
    try:
        # Supabase crea el usuario y guarda el nombre en los metadatos
        res = cliente_auth().auth.sign_up({"email": req.email, "password": req.password,
                                           "options": {"data": {"nombre": req.nombre}}})
        if not res.user:
            raise HTTPException(status_code=400, detail="No se pudo crear la cuenta")
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e).lower()
        if "already registered" in error_msg or "already exists" in error_msg:
            raise HTTPException(status_code=400, detail="El correo ya está registrado")
        logger.exception("Error de Supabase al registrar %s", req.email)
        raise HTTPException(status_code=400, detail="No se pudo registrar la cuenta. Intenta de nuevo.")

    usuarios.invalidar()  # que el nuevo usuario aparezca para compartir gastos
    # Categorías estándar para que no empiece de cero (si falla, puede cargarlas luego desde Categorías)
    try:
        if not plantilla.tiene_categorias(res.user.id):
            plantilla.aplicar_plantilla(res.user.id)
    except Exception:
        logger.exception("No se pudo cargar la plantilla al usuario %s", res.user.id)

    usuario = {"id": res.user.id, "nombre": req.nombre, "email": req.email}
    if not res.session:
        # Supabase tiene activa la confirmación de correo: aún no puede iniciar sesión
        return {"mensaje": "Cuenta creada. Revisa tu correo y confirma tu dirección para poder iniciar sesión.",
                "usuario": usuario, "token": None, "requiere_confirmacion": True}
    return {"mensaje": "Cuenta creada exitosamente", "usuario": usuario,
            "requiere_confirmacion": False, **_sesion(res.session)}


@router.get("/yo")
def usuario_de_la_sesion(uid: str = Depends(usuario_actual)):
    """Datos del usuario del token."""
    return _usuario(supabase.auth.admin.get_user_by_id(uid).user)


@router.post("/cambiar-password")
def cambiar_password(req: CambioPasswordRequest, uid: str = Depends(usuario_actual)):
    """Exige la contraseña actual (por si alguien usa una sesión abierta en otro equipo)."""
    if req.actual == req.nueva:
        raise HTTPException(status_code=400, detail="La nueva contraseña debe ser distinta de la actual")
    email = supabase.auth.admin.get_user_by_id(uid).user.email
    try:
        cliente_auth().auth.sign_in_with_password({"email": email, "password": req.actual})
    except Exception:
        raise HTTPException(status_code=400, detail="La contraseña actual no es correcta")
    supabase.auth.admin.update_user_by_id(uid, {"password": req.nueva})
    return {"mensaje": "Contraseña actualizada"}
