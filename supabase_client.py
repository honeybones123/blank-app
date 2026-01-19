import os
from dotenv import load_dotenv
from supabase import create_client, Client


def get_supabase() -> Client:
    load_dotenv()
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()

    if not url or not key:
        raise RuntimeError(
            "Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY env vars on the Streamlit service."
        )

    return create_client(url, key)


def projects_table_name() -> str:
    return os.getenv("SUPABASE_PROJECTS_TABLE", "projects").strip() or "projects"
