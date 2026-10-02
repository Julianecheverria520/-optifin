"""Plantilla de categorías estándar que recibe cada usuario nuevo al registrarse.

Es una copia fija, tomada de las categorías de Julián el 2026-10-02 y sin los nombres personales
(Apto Barranquilla, Tarjeta Codensa, Compras Matías). Si un usuario cambia sus propias categorías,
la plantilla no se altera. Para actualizarla, edita esta lista.
"""
from backend.database import supabase

# (nombre de la categoría, tipo de movimiento, [subcategorías])
PLANTILLA = [
    ("Ingresos Laborales", "Ingreso", ["Salario", "Primas y bonificaciones", "Honorarios / Freelance"]),
    ("Otros Ingresos", "Ingreso", ["Arriendos recibidos", "Intereses y rendimientos", "Ventas", "Reembolsos", "Regalos recibidos", "Otros ingresos"]),
    ("Vivienda", "Gasto", ["Arriendo / Hipoteca", "Administración", "Mantenimiento y reparaciones", "Aseo del hogar"]),
    ("Servicios Públicos", "Gasto", ["Luz", "Agua", "Gas", "Internet", "Plan de celular"]),
    ("Alimentación", "Gasto", ["Mercado", "Restaurantes", "Domicilios", "Café y snacks"]),
    ("Transporte", "Gasto", ["Gasolina", "Transporte público", "Taxi / Apps", "Parqueadero y peajes", "Mantenimiento vehículo", "SOAT e impuestos vehículo"]),
    ("Salud", "Gasto", ["EPS / Medicina prepagada", "Medicamentos", "Citas y exámenes", "Gimnasio"]),
    ("Educación", "Gasto", ["Matrícula / Pensión", "Cursos", "Libros y materiales"]),
    ("Entretenimiento", "Gasto", ["Salidas", "Suscripciones y membresías", "Viajes", "Hobbies"]),
    ("Compras Personales", "Gasto", ["Ropa y calzado", "Cuidado personal", "Tecnología", "Peluquería"]),
    ("Obligaciones Financieras", "Gasto", ["Intereses", "Cuota de manejo", "Seguros", "Impuestos", "Crédito vehículo", "Tarjeta de crédito", "Crédito celular"]),
    ("Regalos y Donaciones", "Gasto", ["Regalos", "Donaciones"]),
    ("Otros Gastos", "Gasto", ["Imprevistos"]),
    ("Familia", "Gasto", ["Hijos"]),
]


def tiene_categorias(id_usuario: str) -> bool:
    res = supabase.table("categorias").select("id_categoria").eq("id_usuario", id_usuario).limit(1).execute()
    return bool(res.data)


def aplicar_plantilla(id_usuario: str) -> tuple[int, int]:
    """Copia la plantilla a las categorías del usuario. Devuelve (categorías, subcategorías) creadas.
    Dos inserciones en bloque (categorías y luego subcategorías) en vez de una por fila."""
    categorias = supabase.table("categorias").insert([
        {"id_usuario": id_usuario, "nombre_categoria": nombre, "tipo_movimiento": tipo}
        for nombre, tipo, _ in PLANTILLA
    ]).execute().data

    id_por_nombre = {c["nombre_categoria"]: c["id_categoria"] for c in categorias}
    subcategorias = [
        {"id_usuario": id_usuario, "id_categoria": id_por_nombre[nombre], "nombre_subcategoria": sub}
        for nombre, _, subs in PLANTILLA for sub in subs
    ]
    supabase.table("subcategorias").insert(subcategorias).execute()
    return len(categorias), len(subcategorias)
