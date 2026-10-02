"""Usuarios de OptiFin (Supabase Auth): nombre y correo para vincular y mostrar deudas entre usuarios.

Se consulta con la API de administración (clave del servidor) y se guarda en memoria 60 segundos
para no llamar a Supabase Auth en cada petición.
"""
import threading
import time

from backend.database import supabase

_TTL = 60
_cache = {"hasta": 0.0, "usuarios": []}
_lock = threading.Lock()


def listar() -> list[dict]:
    """[{id, nombre, email}] de todos los usuarios registrados."""
    with _lock:
        if time.time() < _cache["hasta"]:
            return _cache["usuarios"]
        usuarios, pagina = [], 1
        while True:
            lote = supabase.auth.admin.list_users(page=pagina, per_page=1000)
            usuarios += [{
                "id": u.id,
                "email": (u.email or "").lower(),
                "nombre": (u.user_metadata or {}).get("nombre") or (u.email or "").split("@")[0],
            } for u in lote]
            if len(lote) < 1000:
                break
            pagina += 1
        _cache.update(hasta=time.time() + _TTL, usuarios=usuarios)
        return usuarios


def nombres() -> dict:
    """{id_usuario: nombre}"""
    return {u["id"]: u["nombre"] for u in listar()}


def buscar(texto: str):
    """Usuario cuyo nombre o correo coincide (sin distinguir mayúsculas), o None si es una persona externa."""
    clave = (texto or "").strip().casefold()
    if not clave:
        return None
    return next((u for u in listar() if clave in (u["email"].casefold(), u["nombre"].strip().casefold())), None)


def invalidar():
    """Olvidar la caché (p. ej. tras registrar un usuario nuevo)."""
    with _lock:
        _cache["hasta"] = 0.0
