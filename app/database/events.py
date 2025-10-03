from sqlalchemy import event
from sqlalchemy.orm import Session
from app.database.models import User, UserPreferences, Settings

@event.listens_for(User, "after_insert")
def create_defaults(mapper, connection, target):
    session = Session(bind=connection)
    try:
        prefs = UserPreferences(user_id=target.id)
        settings = Settings(user_id=target.id)
        session.add(prefs)
        session.add(settings)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
