from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import transactions, planning, debts, categories, dashboard, accounts, liquidaciones, auth

app = FastAPI(title="OptiFin API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(transactions.router)
app.include_router(planning.router)
app.include_router(debts.router)
app.include_router(categories.router)
app.include_router(dashboard.router)
app.include_router(accounts.router)
app.include_router(liquidaciones.router)
app.include_router(auth.router)