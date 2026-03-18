import os

# --- Supabase Configuration ---
# Replace these with your actual Supabase project values
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://vescgogylnztgcedjyqj.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_dqJDGJj70F2FCUE91C75BQ_unGL2Pms")
        
# --- Flask Configuration ---
SECRET_KEY = os.environ.get("SECRET_KEY", "hello123")

# --- Admin credentials (simple auth for now) ---
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

# --- User login table configuration ---
USER_AUTH_TABLE = os.environ.get("USER_AUTH_TABLE", "user_accounts")
