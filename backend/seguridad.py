"""Tokens de sesión firmados (HMAC-SHA256) y dependencia para saber qué usuario hace cada petición.

Formato del token: "<id_usuario>.<expira_unix>.<firma>". La firma usa una clave secreta:
- en producción (Render) se define la variable de entorno OPTIFIN_SECRET;
- en local, si no existe, se genera una vez y se guarda en el archivo .optifin_secret (no subirlo a git).
"""
import hashlib
import hmac
import os
import secrets
import time

from fastapi import HTTPException, Header
from backend.database import supabase

from backend.excel_store import BASE_DIR

ARCHIVO_SECRETO = os.path.join(BASE_DIR, ".optifin_secret")


def _cargar_secreto() -> str:
    if os.environ.get("OPTIFIN_SECRET"):
        return os.environ["OPTIFIN_SECRET"]
    if os.path.exists(ARCHIVO_SECRETO):
        with open(ARCHIVO_SECRETO, encoding="utf-8") as f:
            return f.read().strip()
    secreto = secrets.token_hex(32)
    with open(ARCHIVO_SECRETO, "w", encoding="utf-8") as f:
        f.write(secreto)
    return secreto


SECRETO = _cargar_secreto()
DURACION_CORTA = 12 * 3600        # sin "mantener sesión"
DURACION_LARGA = 30 * 24 * 3600   # con "mantener sesión"


def _firma(contenido: str) -> str:
    return hmac.new(SECRETO.encode(), contenido.encode(), hashlib.sha256).hexdigest()


def crear_token(id_usuario: int, recordar: bool) -> str:
    expira = int(time.time()) + (DURACION_LARGA if recordar else DURACION_CORTA)
    contenido = f"{id_usuario}.{expira}"
    return f"{contenido}.{_firma(contenido)}"


def verificar_token(token: str):
    """ID del usuario si el token es válido y no ha expirado; si no, None."""
    try:
        id_usuario, expira, firma = token.split(".")
        if not hmac.compare_digest(firma, _firma(f"{id_usuario}.{expira}")):
            return None
        if int(expira) < time.time():
            return None
        return int(id_usuario)
    except (ValueError, AttributeError):
        return None


def usuario_actual(authorization: str = Header(None)) -> str:
    """Extrae el UUID de Supabase del JWT y valida la sesión."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No autorizado")
    
    token = authorization.split(" ")[1]
    try:
        res = supabase.auth.get_user(token)
        if not res.user:
            raise HTTPException(status_code=401, detail="Sesión inválida")
        return res.user.id
    except Exception:
        raise HTTPException(status_code=401, detail="Tu sesión caducó. Inicia sesión de nuevo.")