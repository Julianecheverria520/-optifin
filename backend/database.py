"""Clientes de Supabase.

IMPORTANTE: hay dos tipos de cliente y no se deben mezclar.

- `supabase`: el cliente del SERVIDOR (clave secret / service_role). Se usa para leer y escribir
  datos. NUNCA debe iniciar sesión: en supabase-py, al hacer sign_in/sign_up el cliente reemplaza
  su cabecera Authorization por el token del usuario, y desde ese momento TODAS las consultas de
  TODOS los usuarios saldrían con la identidad del último que inició sesión.

- `cliente_auth()`: un cliente nuevo y desechable para cada login o registro. Su sesión muere con él.
"""
import os

from dotenv import load_dotenv
from supabase import Client, ClientOptions, create_client

# Cargar variables del archivo .env (útil en local; en Render se definen en el panel)
load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Faltan SUPABASE_URL o SUPABASE_KEY en las variables de entorno.")


def _opciones_sin_sesion() -> ClientOptions:
    # Sin sesión persistente ni renovación automática en segundo plano.
    # (Se construye directo: ClientOptions().replace(auto_refresh_token=False) ignora el False.)
    return ClientOptions(auto_refresh_token=False, persist_session=False)


# Cliente del servidor para datos: compartido por toda la app y siempre con la clave del servidor
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY, options=_opciones_sin_sesion())


def cliente_auth() -> Client:
    """Cliente desechable para sign_in / sign_up / refresh: no contamina al cliente del servidor."""
    return create_client(SUPABASE_URL, SUPABASE_KEY, options=_opciones_sin_sesion())
