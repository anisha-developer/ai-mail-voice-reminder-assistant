from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import delete, select, update

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.database.session import SessionLocal
from app.models.email_summary import EmailSummary
from app.models.mail_summary_call_log import MailSummaryCallLog
from app.models.user import User
from app.models.voice_call_interaction import VoiceCallInteraction


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset local mail-call Phase 8 test state for one user.")
    parser.add_argument("--email", required=True, help="User email to reset")
    parser.add_argument(
        "--keep-call-logs",
        action="store_true",
        help="Keep mail_summary_call_logs and only reset summary delivery fields",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        user = db.execute(select(User).where(User.email == args.email)).scalar_one_or_none()
        if user is None:
            raise SystemExit(f"User not found: {args.email}")

        db.execute(
            update(EmailSummary)
            .where(EmailSummary.user_id == user.id)
            .values(
                is_delivered_in_mail_call=False,
                delivered_at=None,
                mail_call_log_id=None,
            )
        )

        db.execute(delete(VoiceCallInteraction).where(VoiceCallInteraction.user_id == user.id))

        if not args.keep_call_logs:
            db.execute(delete(MailSummaryCallLog).where(MailSummaryCallLog.user_id == user.id))

        db.commit()
        print(f"Reset complete for {args.email}")
        if args.keep_call_logs:
            print("Mail summary call logs were kept.")
        else:
            print("Mail summary call logs and voice interactions were removed.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
