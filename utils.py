

from models import UserProduct, UserTransaction, InvoiceTemplate
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from flask import session

def get_user_db(include_template=False):
    """
    Return (engine, db_session, UserProduct, UserTransaction, [InvoiceTemplate])
    sesuai user login aktif.
    """
    user_db_path = session.get("user_db")
    if not user_db_path:
        return None, None, None, None, None if include_template else (None, None, None, None)

    engine = create_engine(f"sqlite:///{user_db_path}")
    Session = scoped_session(sessionmaker(bind=engine))
    db_session = Session()

    if include_template:
        return engine, db_session, UserProduct, UserTransaction, InvoiceTemplate
    else:
        return engine, db_session, UserProduct, UserTransaction
