import os

# --- Supabase Configuration ---
# Set these as environment variables in Vercel (or .env locally).
# The SUPABASE_KEY must be the anon/service-role JWT key from:
# Supabase Dashboard → Project Settings → API → anon public (starts with eyJ...)
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# --- Flask Configuration ---
SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")

# --- Admin credentials (simple auth for now) ---
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

# --- User login table configuration ---
USER_AUTH_TABLE = os.environ.get("USER_AUTH_TABLE", "user_accounts")
