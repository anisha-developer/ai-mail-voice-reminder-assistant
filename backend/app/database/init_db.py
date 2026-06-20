from app.database.session import Base, engine
from app.models import action_log, email_message, email_reply_action, email_summary, gmail_connection, mail_summary_call_log, priority_contact, priority_mail_alert_log, recurring_reminder_rule, reminder, reminder_call_log, user, user_call_preference, user_preference, voice_call_interaction, voice_email_reply_log, voice_reminder_session, voice_reply_session


def create_tables() -> None:
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    create_tables()
