import pandas as pd
import numpy as np
from backend.database import supabase
from datetime import date

EXCEL_FILE = "OptiFin_Estructura_Datos.xlsx"
MI_UUID = "dfd9b5dd-cff5-4895-b8a6-f578dfcaca8d"

def safe_int(val):
    """Convierte decimales de Pandas (como 1.0) a enteros limpios (1), o devuelve None si está vacío."""
    if pd.isna(val) or val is None or str(val).strip() == "":
        return None
    return int(float(val))

def limpiar_nulos(df):
    return df.replace({np.nan: None}).to_dict(orient="records")

def migrar():
    print("Iniciando migración masiva a Supabase...")

    # 1. CUENTAS
    print("Migrando Cuentas...")
    df_cuentas = pd.read_excel(EXCEL_FILE, sheet_name="Cuentas")
    for d in limpiar_nulos(df_cuentas):
        supabase.table("cuentas").upsert({
            "id_cuenta": safe_int(d["ID_Cuenta"]),
            "id_usuario": MI_UUID,
            "nombre_cuenta": d["Nombre_Cuenta"],
            "tipo_cuenta": d["Tipo_Cuenta"],
            "saldo_inicial": float(d["Saldo_Inicial"])
        }).execute()

    # 2. CATEGORÍAS
    print("Migrando Categorías...")
    df_cat = pd.read_excel(EXCEL_FILE, sheet_name="Categorias")
    for d in limpiar_nulos(df_cat):
        supabase.table("categorias").upsert({
            "id_categoria": safe_int(d["ID_Categoria"]),
            "id_usuario": MI_UUID,
            "nombre_categoria": d["Nombre_Categoria"],
            "tipo_movimiento": d["Tipo_Movimiento"]
        }).execute()

    # 3. SUBCATEGORÍAS
    print("Migrando Subcategorías...")
    df_sub = pd.read_excel(EXCEL_FILE, sheet_name="Subcategorias")
    for d in limpiar_nulos(df_sub):
        supabase.table("subcategorias").upsert({
            "id_subcategoria": safe_int(d["ID_Subcategoria"]),
            "id_usuario": MI_UUID,
            "id_categoria": safe_int(d["ID_Categoria"]),
            "nombre_subcategoria": d["Nombre_Subcategoria"]
        }).execute()

    # 4. TRANSACCIONES
    print("Migrando Transacciones históricas...")
    df_trans = pd.read_excel(EXCEL_FILE, sheet_name="Transacciones")
    for d in limpiar_nulos(df_trans):
        supabase.table("transacciones").upsert({
            "id_transaccion": safe_int(d["ID_Transaccion"]),
            "id_usuario": MI_UUID,
            "fecha": str(d["Fecha"]).split(" ")[0],
            "tipo_movimiento": d["Tipo_Movimiento"],
            "id_subcategoria": safe_int(d.get("ID_Subcategoria")),
            "id_cuenta_origen": safe_int(d.get("ID_Cuenta_Origen")),
            "id_cuenta_destino": safe_int(d.get("ID_Cuenta_Destino")),
            "monto": float(d["Monto"]),
            "descripcion": str(d["Descripcion"]) if d.get("Descripcion") else None
        }).execute()

    # 5. PLANIFICACIÓN
    print("Migrando Planificación y Presupuestos...")
    df_plan = pd.read_excel(EXCEL_FILE, sheet_name="Presupuestos_y_Fijos")
    for d in limpiar_nulos(df_plan):
        supabase.table("planificacion").upsert({
            "id_registro": safe_int(d["ID_Registro"]),
            "id_usuario": MI_UUID,
            "tipo": d["Tipo"],
            "nombre_concepto": d["Nombre_Concepto"],
            "monto": float(d["Monto"]),
            "dia_mes": safe_int(d.get("Dia_Mes")),
            "id_subcategoria": safe_int(d["ID_Subcategoria"]),
            "fecha_inicio": f"{date.today().year}-01-01",
            "periodicidad": "Mensual",
            "activo": d.get("Activo", "Sí")
        }).execute()

    # 6. DEUDAS
    print("Migrando Deudas...")
    df_deudas = pd.read_excel(EXCEL_FILE, sheet_name="Deudas")
    for d in limpiar_nulos(df_deudas):
        supabase.table("deudas").upsert({
            "id_deuda": safe_int(d["ID_Deuda"]),
            "id_usuario": MI_UUID,
            "persona": d["Persona"],
            "tipo_deuda": d["Tipo_Deuda"],
            "monto": float(d["Monto"]),
            "fecha_creacion": str(d["Fecha_Creacion"]).split(" ")[0]
        }).execute()

    print("✅ ¡Migración completada con éxito! Tu historial ya está en la nube.")

if __name__ == "__main__":
    migrar()