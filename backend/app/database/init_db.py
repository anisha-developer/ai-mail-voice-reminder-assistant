from app.database.session import Base, engine
from app.models import action_log, email_message, email_summary, mail_summary_call_log, reminder, reminder_call_log, user, user_preference


def create_tables() -> None:
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    create_tables()

