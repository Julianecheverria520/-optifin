"""Validación de la sesión: qué usuario hace cada petición.

El navegador envía el access token de Supabase ("Authorization: Bearer <token>"). Se valida
LOCALMENTE con las claves públicas del proyecto (JWKS, firma ES256), que se descargan una vez
y quedan en caché: así no se llama a Supabase Auth en cada petición.
Si las claves no se pueden obtener, se valida preguntándole a Supabase (más lento, pero seguro).

Nota: un token sigue siendo válido hasta que expira (60 min) aunque el usuario cierre sesión;
el navegador lo borra al cerrar sesión y lo renueva con el refresh token (POST /auth/renovar).
"""
import logging

import jwt
from fastapi import Header, HTTPException

from backend.database import SUPABASE_URL, supabase

logger = logging.getLogger("optifin.seguridad")

EMISOR = f"{SUPABASE_URL.rstrip('/')}/auth/v1"
_claves = jwt.PyJWKClient(f"{EMISOR}/.well-known/jwks.json", cache_keys=True, lifespan=3600, timeout=10)

SESION_EXPIRADA = "Tu sesión expiró. Inicia sesión de nuevo."
MARGEN_RELOJ = 120  # segundos


def _validar_en_supabase(token: str) -> str:
    """Respaldo: Supabase Auth confirma el token (una llamada de red)."""
    try:
        res = supabase.auth.get_user(token)
    except Exception:
        raise HTTPException(status_code=401, detail=SESION_EXPIRADA)
    if not res or not res.user:
        raise HTTPException(status_code=401, detail=SESION_EXPIRADA)
    return res.user.id


def usuario_actual(authorization: str | None = Header(default=None)) -> str:
    """Dependencia de FastAPI: devuelve el ID (UUID) del usuario del token o responde 401."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No autorizado")
    token = authorization[7:].strip()

    try:
        clave = _claves.get_signing_key_from_jwt(token)
    except jwt.PyJWKClientConnectionError:
        logger.warning("No se pudieron descargar las claves JWKS; se valida con Supabase")
        return _validar_en_supabase(token)
    except (jwt.PyJWKClientError, jwt.InvalidTokenError):
        raise HTTPException(status_code=401, detail=SESION_EXPIRADA)

    try:
        # leeway: margen por diferencias de reloj entre este servidor y Supabase (en una prueba local
        # el reloj iba 84 s atrás y el token parecía emitido "en el futuro")
        datos = jwt.decode(token, clave.key, algorithms=["ES256", "RS256"],
                           audience="authenticated", issuer=EMISOR, leeway=MARGEN_RELOJ)
    except jwt.InvalidTokenError:  # incluye token expirado o firma inválida
        raise HTTPException(status_code=401, detail=SESION_EXPIRADA)
    return datos["sub"]
