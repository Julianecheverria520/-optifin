import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Cargar variables del archivo .env (útil en local)
load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

if not url or not key:
    raise ValueError("Faltan SUPABASE_URL o SUPABASE_KEY en las variables de entorno.")

# Inicializar cliente global para toda la app
supabase: Client = create_client(url, key)