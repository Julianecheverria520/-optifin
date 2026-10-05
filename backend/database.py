"""Clientes de Supabase.

IMPORTANTE: hay dos tipos de cliente y no se deben mezclar.

- `supabase`: el cliente del SERVIDOR (clave secret / service_role). Se usa para leer y escribir
  datos. NUNCA debe iniciar sesión: en supabase-py, al hacer sign_in/sign_up el cliente reemplaza
  su cabecera Authorization por el token del usuario, y desde ese momento TODAS las consultas de
  TODOS los usuarios saldrían con la identidad del último que inició sesión.

- `cliente_auth()`: un cliente nuevo y desechable para cada login o registro. Su sesión muere con él.
"""
import logging
import os

import httpx
from dotenv import load_dotenv
from supabase import Client, ClientOptions, create_client

logger = logging.getLogger("optifin.database")

# Cargar variables del archivo .env (útil en local; en Render se definen en el panel)
load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Faltan SUPABASE_URL o SUPABASE_KEY en las variables de entorno.")


class _TransporteConReintento(httpx.HTTPTransport):
    """Reintenta las lecturas (GET/HEAD) cuando la conexión se cae a mitad de camino.

    Supabase cierra las conexiones inactivas; si la app justo reutiliza una de esas, la petición
    falla con "Server disconnected" y antes el usuario veía un error 500 que se arreglaba recargando.
    Las escrituras NO se reintentan: si la primera alcanzó a llegar, se duplicarían."""

    REINTENTOS = 2
    ERRORES_DE_CONEXION = (httpx.RemoteProtocolError, httpx.ReadError, httpx.WriteError, httpx.ConnectError, httpx.PoolTimeout)

    def handle_request(self, request):
        intento = 0
        while True:
            try:
                return super().handle_request(request)
            except self.ERRORES_DE_CONEXION as e:
                es_lectura = request.method in ("GET", "HEAD")
                # Un ConnectError nunca llegó al servidor: se puede repetir aunque sea escritura
                if intento >= self.REINTENTOS or not (es_lectura or isinstance(e, httpx.ConnectError)):
                    raise
                intento += 1
                logger.warning("Conexión con Supabase interrumpida (%s); reintento %d de %s %s",
                               type(e).__name__, intento, request.method, request.url.path)


def _cliente_http() -> httpx.Client:
    # HTTP/1.1 y no HTTP/2: la librería de Supabase usa por defecto UNA conexión HTTP/2 compartida, y
    # con varias consultas en paralelo (hilos) esa conexión falla de forma intermitente. Con HTTP/1.1
    # cada consulta simultánea usa su propia conexión del pool. Las conexiones inactivas se descartan
    # a los 30 s, antes de que Supabase las cierre por su lado.
    return httpx.Client(
        http2=False,
        timeout=httpx.Timeout(30.0, connect=10.0),
        limits=httpx.Limits(max_connections=40, max_keepalive_connections=20, keepalive_expiry=30.0),
        transport=_TransporteConReintento(retries=1),
        follow_redirects=True,
    )


def _opciones_sin_sesion(http: httpx.Client | None = None) -> ClientOptions:
    # Sin sesión persistente ni renovación automática en segundo plano.
    # (Se construye directo: ClientOptions().replace(auto_refresh_token=False) ignora el False.)
    return ClientOptions(auto_refresh_token=False, persist_session=False, httpx_client=http)


# Cliente del servidor para datos: compartido por toda la app y siempre con la clave del servidor
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY, options=_opciones_sin_sesion(_cliente_http()))


def cliente_auth() -> Client:
    """Cliente desechable para sign_in / sign_up / refresh: no contamina al cliente del servidor."""
    return create_client(SUPABASE_URL, SUPABASE_KEY, options=_opciones_sin_sesion())
