"""Registro e inicio de sesión de usuarios usando Supabase Auth."""
import re
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, field_validator

import logging

from backend import plantilla, usuarios
from backend.database import cliente_auth, supabase

logger = logging.getLogger("optifin.auth")

router = APIRouter(prefix="/auth", tags=["Auth"])

PATRON_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def _normalizar_email(valor: str) -> str:
    valor = valor.strip().lower()
    if not PATRON_EMAIL.match(valor) or len(valor) > 120:
        raise ValueError("Escribe un correo electrónico válido")
    return valor


class LoginRequest(BaseModel):
    email: str
    password: str
    recordar: bool = False

    _email = field_validator("email")(_normalizar_email)


class RegisterRequest(BaseModel):
    nombre: str
    email: str
    password: str

    _email = field_validator("email")(_normalizar_email)

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, valor: str) -> str:
        valor = valor.strip()
        if not 1 <= len(valor) <= 80:
            raise ValueError("Escribe tu nombre")
        return valor

    @field_validator("password")
    @classmethod
    def validar_password(cls, valor: str) -> str:
        if not 6 <= len(valor) <= 128:
            raise ValueError("La contraseña debe tener al menos 6 caracteres")
        return valor


# ---------- Endpoints ----------

@router.post("/login")
def login(req: LoginRequest):
    try:
        # Supabase valida la contraseña y devuelve un JWT
        # Cliente desechable: iniciar sesión en el cliente del servidor cambiaría la identidad
        # de TODAS las consultas de la app (ver backend/database.py)
        res = cliente_auth().auth.sign_in_with_password({
            "email": req.email,
            "password": req.password
        })
        
        usuario = {
            "id": res.user.id, # Ahora es un UUID (ej: "123e4567-e89b-...")
            "nombre": res.user.user_metadata.get("nombre", ""),
            "email": res.user.email
        }
        return {"mensaje": "Login exitoso", "usuario": usuario, "token": res.session.access_token}
    except Exception as e:
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos")


@router.post("/registro")
def registro(req: RegisterRequest):
    try:
        # Supabase crea el usuario y guarda el nombre en los metadatos
        res = cliente_auth().auth.sign_up({
            "email": req.email,
            "password": req.password,
            "options": {
                "data": {"nombre": req.nombre}
            }
        })
        
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
        return {
            "mensaje": "Cuenta creada. Revisa tu correo y confirma tu dirección para poder iniciar sesión.",
            "usuario": usuario,
            "token": None,
            "requiere_confirmacion": True,
        }
    return {
        "mensaje": "Cuenta creada exitosamente",
        "usuario": usuario,
        "token": res.session.access_token,
        "requiere_confirmacion": False,
    }


@router.get("/yo")
def usuario_de_la_sesion(authorization: str = Header(None)):
    """Validamos el JWT directamente con Supabase (reemplaza tu antigua función usuario_actual)."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token no proporcionado")
    
    token = authorization.split(" ")[1]
    try:
        # Supabase verifica criptográficamente si el token es válido y no ha expirado
        res = supabase.auth.get_user(token)
        if not res.user:
            raise HTTPException(status_code=401, detail="Sesión inválida")
        
        return {
            "id": res.user.id,
            "nombre": res.user.user_metadata.get("nombre", ""),
            "email": res.user.email
        }
    except Exception:
        raise HTTPException(status_code=401, detail="Tu sesión caducó. Inicia sesión de nuevo.")