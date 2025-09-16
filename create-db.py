from sqlalchemy import create_engine, inspect
from models import UserCashier

# DB user
user_db_path = "users_db/admin-judol.db"
engine = create_engine(f"sqlite:///{user_db_path}")

# Buat tabel UserCashier jika belum ada
UserCashier.metadata.create_all(engine)

# Cek tabel menggunakan Inspector
inspector = inspect(engine)
print(inspector.get_table_names())