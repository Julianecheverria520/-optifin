import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.routers import transactions, debts, categories, accounts, liquidaciones, auth, planning, dashboard

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("optifin")
# Las librerías HTTP registran cada petición a Supabase: solo interesan sus advertencias y errores
for ruidoso in ("httpx", "httpx2", "httpcore", "hpack"):
    logging.getLogger(ruidoso).setLevel(logging.WARNING)

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. Primero cargamos las rutas de tu API (el cerebro)
app.include_router(transactions.router)
app.include_router(debts.router)
app.include_router(categories.router)
app.include_router(accounts.router)
app.include_router(liquidaciones.router)
app.include_router(auth.router)
app.include_router(planning.router)
app.include_router(dashboard.router)

# 2. Al final, montamos la interfaz visual. 
# Esto convierte la carpeta "frontend" en la cara pública de tu app.
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")