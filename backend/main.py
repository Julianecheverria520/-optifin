from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend import excel_store
from backend.routers import transactions, planning, debts, categories, dashboard, accounts, liquidaciones, auth

# Hojas/columnas que el código necesita y que un Excel antiguo podría no tener
ESTRUCTURA_REQUERIDA = {
    # Password guarda el hash de la contraseña (ver routers/auth.py)
    "Usuarios": ["ID_Usuario", "Nombre", "Email", "Password"],
    # Categorías estándar que recibe cada usuario nuevo (ver backend/plantilla.py)
    "Plantilla_Categorias": ["ID_Categoria", "Nombre_Categoria", "Tipo_Movimiento"],
    "Plantilla_Subcategorias": ["ID_Subcategoria", "ID_Categoria", "Nombre_Subcategoria"],
    # Vigencia de cada concepto: desde qué mes aplica y hasta cuál (vacío = indefinido)
    "Presupuestos_y_Fijos": ["ID_Registro", "ID_Usuario", "Tipo", "Nombre_Concepto", "Monto", "Dia_Mes",
                             "ID_Subcategoria", "Estado", "Activo", "Fecha_Inicio", "Fecha_Fin", "Periodicidad"],
    "Deudas": ["ID_Deuda", "ID_Usuario", "Persona", "Tipo_Deuda", "Monto", "Fecha_Creacion", "Estado", "ID_Cuenta",
               "ID_Transaccion", "ID_Usuario_Contraparte", "Descripcion"],
    "Abonos_Deuda": ["ID_Abono", "ID_Usuario", "ID_Deuda", "Fecha", "Monto", "ID_Cuenta", "Descripcion"],
    # Valor de un concepto de planificación solo para un mes (p. ej. la factura de luz llegó por más)
    "Ajustes_Mes": ["ID_Ajuste", "ID_Usuario", "ID_Registro", "Anio", "Mes", "Monto"],
    # Cruces de cuentas con una persona (compensar lo que me debe con lo que le debo)
    "Liquidaciones": ["ID_Liquidacion", "ID_Usuario", "Persona", "ID_Usuario_Contraparte", "Fecha",
                      "Total_Me_Deben", "Total_Debo", "Monto_Cruzado", "Neto", "Estado", "Deudas", "Fecha_Resolucion"],
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        cambios = excel_store.asegurar_estructura(ESTRUCTURA_REQUERIDA)
        if cambios:
            print(f"Excel actualizado: se agregó {', '.join(cambios)}")
    except PermissionError:
        print(f"AVISO: no se pudo revisar la estructura del Excel. {excel_store.MSG_BLOQUEADO}")
    yield


app = FastAPI(title="OptiFin API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
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