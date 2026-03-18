from supabase import create_client, Client
import config

_client: Client | None = None


def get_supabase() -> Client:
    global _client
    if _client is None:
        _client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
    return _client
