from sqlalchemy import create_engine, text

engine = create_engine("sqlite:///users_db/demo.db")

with engine.connect() as conn:
    conn.execute(text("ALTER TABLE user_transaction ADD COLUMN kasir_name TEXT"))
    conn.commit()  # commit perubahan
