from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.routers import transactions, debts, categories, accounts, liquidaciones, auth
# from backend.routers import planning, dashboard  # TODO: Pendientes de migrar a Supabase

app = FastAPI(title="OptiFin API")

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
# app.include_router(planning.router)
# app.include_router(dashboard.router)

# 2. Al final, montamos la interfaz visual. 
# Esto convierte la carpeta "frontend" en la cara pública de tu app.
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")