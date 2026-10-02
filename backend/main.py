import logging
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.routers import transactions, debts, categories, accounts, liquidaciones, auth, planning, dashboard, admin

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("optifin")
# Las librerías HTTP registran cada petición a Supabase: solo interesan sus advertencias y errores
for ruidoso in ("httpx", "httpx2", "httpcore", "hpack"):
    logging.getLogger(ruidoso).setLevel(logging.WARNING)

CARPETA_FRONTEND = Path(__file__).resolve().parent.parent / "frontend"

app = FastAPI(title="OptiFin API")


@app.exception_handler(Exception)
async def error_inesperado(request: Request, exc: Exception):
    """Cualquier error no previsto: el detalle completo va a los logs de Render (no al navegador,
    donde expondría código y datos internos) y el usuario recibe un mensaje genérico."""
    logger.exception("Error no controlado en %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Ocurrió un error inesperado. Intenta de nuevo en un momento."})


@app.get("/salud", include_in_schema=False)
def salud():
    """Para el health check de Render: responde sin tocar la base de datos."""
    return {"estado": "ok"}


# Respuestas comprimidas (el JSON del Resumen y los scripts pesan mucho menos)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# CORS: la app y la API se sirven desde el mismo dominio, así que no hace falta permitir otros
# orígenes. Solo si algún día el frontend vive en otro dominio, se listan en CORS_ORIGINS
# (separados por coma) en las variables de entorno de Render.
origenes = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]
if origenes:
    app.add_middleware(CORSMiddleware, allow_origins=origenes, allow_credentials=False,
                       allow_methods=["*"], allow_headers=["Authorization", "Content-Type"])

# 1. Primero las rutas de la API
app.include_router(transactions.router)
app.include_router(debts.router)
app.include_router(categories.router)
app.include_router(accounts.router)
app.include_router(liquidaciones.router)
app.include_router(auth.router)
app.include_router(planning.router)
app.include_router(dashboard.router)
app.include_router(admin.router)

# 2. Al final, la interfaz: la carpeta "frontend" es la cara pública de la app
app.mount("/", StaticFiles(directory=CARPETA_FRONTEND, html=True), name="frontend")
