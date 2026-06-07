# AI Mail Summary and Voice Reminder Assistant

An end-to-end assistant that syncs Gmail, summarizes email, delivers summaries over voice, and creates voice reminders from email context while keeping daily quotas and recovery actions visible in a polished dashboard.

## Problem Statement

Busy users need a safer, faster way to understand important email, hear concise summaries, and create follow-up reminders without manually triaging every message.

## Solution Overview

This project combines Gmail OAuth, Gmail sync, AI summarization, Twilio voice delivery, and reminder workflows into one full-stack assistant with a dashboard for status, quota, and recovery actions.

## Key Features

- Gmail OAuth connection with signed state and Redis-backed nonce replay protection
- Manual and automatic Gmail sync
- Email summarization and today-only summary support
- Twilio voice mail-summary calls
- Voice explanation of a numbered email
- Voice reminder creation from an email context
- Email-linked reminders
- DTMF confirmation fallback for reminder creation
- Reminder playback calls
- Missed reminder retry and recovery
- Dashboard status sections and recovery actions

## Architecture Summary

- React frontend
- FastAPI backend
- PostgreSQL database
- Redis for background scheduler and OAuth nonce storage
- Gmail API for inbox sync and send/reply flows
- Twilio Voice API for outbound summary and reminder calls
- ngrok public webhook tunnel for local Twilio testing
- LLM summarization layer with mock and OpenAI-ready support

## Project Structure

- `backend/` FastAPI app, SQLAlchemy models, Alembic, database config, and services
- `frontend/` React app with Tailwind CSS and app pages
- `docker-compose.yml` local development stack for PostgreSQL, Redis, backend, and frontend
- `alembic.ini` Alembic configuration at the repository root
- `.env.example` root-level Docker environment variables

## Run With Docker Compose

1. Copy `.env.example` to `.env`
2. Copy `backend/.env.example` to `backend/.env`
3. Copy `frontend/.env.example` to `frontend/.env`
4. Start the stack:

```bash
docker compose up --build
```

4. Open:
   - Frontend: `http://localhost:5173`
   - Backend health: `http://localhost:8000/health`
   - PostgreSQL: `localhost:5432`
   - Redis: `localhost:6379`

## Final Demo Flow

Use this end-to-end demo script:

1. Login
2. Connect Gmail
3. Sync Gmail
4. Generate today summaries
5. Start mail summary call
6. Say: `Explain email one`
7. Say: `Remind me about this email in two minutes`
8. Say: `Yes save it` or press `1`
9. Show the reminder in the dashboard
10. Answer the reminder call
11. Show the completed reminder
12. Demonstrate missed reminder retry if needed

## Feature Checklist

- Gmail OAuth
- Gmail sync
- AI email summarization
- Voice mail-summary call
- Email detail explanation by voice
- Voice reminder creation
- Email-linked reminders
- DTMF confirmation fallback
- Reminder call playback
- Missed reminder retry
- Dashboard recovery actions
- Dashboard status sections

## Run Backend Locally

1. Create and activate a Python virtual environment
2. Install dependencies:

```bash
cd backend
pip install -r requirements.txt
```

3. Set up `backend/.env`
4. Start the API:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Run Frontend Locally

1. Install dependencies:

```bash
cd frontend
npm install
```

2. Set `frontend/.env`
3. Start the dev server:

```bash
npm run dev -- --host 0.0.0.0 --port 5173
```

## Run Alembic Migrations

From the repository root or `backend/`:

```bash
alembic upgrade head
```

Create a new migration:

```bash
alembic revision --autogenerate -m "describe change"
```

Rollback one migration:

```bash
alembic downgrade -1
```

## Final Commands

```bash
docker compose up --build -d
docker compose exec backend alembic upgrade head
docker compose exec -e PYTHONPATH=/app backend pytest -q
cd frontend
npm run build
```

## Backend Commands

- Start backend locally: `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
- Run migrations: `alembic upgrade head`
- Create a migration: `alembic revision --autogenerate -m "describe change"`

## Manual Auth Testing

### 1. Test Signup

Send a `POST` request to `http://localhost:8000/auth/signup` with:

```json
{
  "name": "Anish",
  "email": "anish@example.com",
  "password": "StrongPass123!",
  "phone_number": "+1-555-123-4567",
  "timezone": "Asia/Calcutta",
  "preferred_language": "en"
}
```

Expected result:
- User is created in `users`
- A default `user_preferences` row is created
- Response includes a JWT access token and user details, but not the password

### 2. Test Login

Send a `POST` request to `http://localhost:8000/auth/login` with:

```json
{
  "email": "anish@example.com",
  "password": "StrongPass123!"
}
```

Expected result:
- A valid JWT access token is returned
- Basic user profile details are returned

### 3. Test Protected Profile Endpoint

Send a `GET` request to `http://localhost:8000/users/me` with:

```http
Authorization: Bearer <your_access_token>
```

Expected result:
- Profile data is returned for the authenticated user
- Without the token, the API returns `401 Unauthorized`

### 4. Test Frontend Protected Route

1. Open `http://localhost:5173`
2. If not logged in, the app should redirect to `/login`
3. Log in or sign up
4. After login, dashboard and settings should open normally
5. Remove the token by clicking Logout
6. Refresh the page and confirm protected routes redirect back to login

## Gmail Connection and Email Sync

The Gmail OAuth flow uses:

- signed OAuth state
- Redis-backed one-time nonce replay protection
- PKCE code verifier handling
- encrypted token storage in the backend

### Email Inbox Flow

1. Log in and connect Gmail from Settings / Profile.
2. Open the Email Inbox page.
3. Click Sync Emails.
4. The backend fetches inbox messages from Gmail and stores them in `email_messages`.
5. Repeating Sync Emails skips duplicates by `user_id + gmail_message_id`.
6. Open a stored email to view sender, recipient, subject, snippet, body, timestamps, and attachment metadata.
7. Automatic background email sync can be enabled separately for connected Gmail users.

### Backend Email Endpoints

- `POST /emails/sync`
- `GET /emails?page=1&limit=20`
- `GET /emails/{email_id}`
- `GET /emails/sync-status`
- `GET /emails/auto-sync-status`

### Reminder Endpoints

- `POST /reminders`
- `GET /reminders`
- `GET /reminders/{reminder_id}`
- `PATCH /reminders/{reminder_id}`
- `DELETE /reminders/{reminder_id}`

### Reminder Agent

Reminder calls are separate from mail summary calls.

Default reminder behavior:

- `REMINDER_CALLS_ENABLED=false`
- `REMINDER_CHECK_INTERVAL_SECONDS=60`
- `REMINDER_DUE_GRACE_SECONDS=120`

When enabled:

- the backend scheduler checks scheduled reminders on the configured interval
- reminders are stored in UTC internally
- reminder calls use Twilio and the existing backend voice setup
- reminder calls do not use the 3-per-day mail summary call limit
- cancelled reminders are skipped
- failed reminders are marked failed and kept for review

Reminder calls do not log:

- Twilio auth tokens
- full reminder notes beyond what is needed for the spoken call

Reminder call TwiML is a simple spoken reminder, not an interactive speech loop.

### Phase 12 Reminder Foundation

Phase 12 focuses on reminder creation, listing, updating, and cancellation only.

Implemented reminder behavior:

- create reminders from the dashboard or the `/reminders` API
- store reminder timestamps in UTC internally
- convert local date/time input using the selected timezone
- fall back to the user profile phone number when no reminder phone number is provided
- reject invalid timezones and past reminder times
- prevent cross-user reminder access
- allow canceling reminders without triggering a call
- keep reminder calls disabled by default with `REMINDER_CALLS_ENABLED=false`

Reminders appear in the dashboard with status labels, and cancelled reminders are not returned as upcoming reminders unless explicitly requested.

Phase 12 manual test checklist:

1. Log in and open the Dashboard.
2. Create a reminder a few minutes in the future.
3. Confirm it appears in the reminder list.
4. Refresh the page and confirm the reminder persists.
5. Cancel the reminder.
6. Confirm the status changes to cancelled.
7. Try a past reminder time and confirm the UI shows a friendly validation error.
8. Confirm `mail_summary_call_logs` and the mail summary quota do not change when reminders are created or cancelled.

### Automatic Gmail Sync

Automatic Gmail sync uses APScheduler inside the FastAPI backend.

Default behavior:

- `AUTO_EMAIL_SYNC_ENABLED=false`
- `AUTO_EMAIL_SYNC_INTERVAL_MINUTES=5`
- `AUTO_EMAIL_SYNC_BATCH_USERS=20`
- `AUTO_EMAIL_SYNC_MAX_RESULTS=50`
- `AUTO_EMAIL_SYNC_MAX_PAGES=2`
- `AUTO_SUMMARIZE_AFTER_SYNC=false`

When enabled:

- the backend scheduler checks connected Gmail users on the configured interval
- only users with an active `gmail_connections` row and a stored refresh token are processed
- duplicate prevention still uses `user_id + gmail_message_id`
- each user sync is isolated so one failure does not stop the rest
- manual `POST /emails/sync` remains available

Safe auto-sync logs include:

- `user_id`
- `gmail_email`
- `synced_count`
- `skipped_duplicates`
- `total_processed`
- `latest_gmail_received_at`
- `latest_stored_received_at`
- error message when a user sync fails

Auto sync does not log:

- Gmail access tokens
- Gmail refresh tokens
- full email bodies
- raw Gmail payloads

If `AUTO_SUMMARIZE_AFTER_SYNC=true`, only newly inserted unsummarized emails are summarized after auto sync. The default is `false`, so sync and summarization stay separate unless explicitly enabled.

When auto summary is enabled:

- the backend summarizes only the emails inserted during that successful auto-sync run
- already summarized emails are skipped
- a summary failure does not roll back the stored emails from auto sync
- auto-summary status is exposed alongside auto-sync status in `GET /emails/auto-sync-status`

### Email Summaries Flow

1. Sync Gmail emails into the Inbox page.
2. Open Email Summaries.
3. Click Generate Summaries.
4. The backend summarizes every unsummarized stored email for the authenticated user.
5. Mock summarization works without an OpenAI key.
6. If `LLM_PROVIDER=openai` and `OPENAI_API_KEY` is set, the backend uses the configured OpenAI model.

### Backend Summary Endpoints

- `POST /summaries/generate-all`
- `GET /summaries?page=1&limit=20`
- `GET /summaries/today`
- `GET /summaries/{summary_id}`
- `GET /summaries/{summary_id}/detail`

### Mail Summary Calls Flow

1. Generate email summaries first.
2. Open Mail Summary Calls.
3. Check today's mail summary call usage.
4. Click Prepare Mail Summary Call.
5. The backend collects only today's pending summaries based on each email's `received_at` in the user's timezone.
6. If there are no emails received today, the API returns `No emails received today.`
7. A call-friendly script is generated and stored in `mail_summary_call_logs`.
8. The dashboard shows total summaries in the database, today's summaries, and pending today summaries separately.
9. Voice calls summarize only today's received emails, even though Phase 5 still summarizes all stored emails.
10. Click Mark as Delivered to mark those summaries as delivered.
11. The daily limit is enforced only for `mail_summary` calls.
12. Reminder calls are intentionally not counted in this limit.

### Backend Mail Summary Call Endpoints

- `GET /mail-calls/count-today`
- `POST /mail-calls/prepare`
- `POST /mail-calls/{call_log_id}/mark-delivered`
- `GET /mail-calls/history`
- `GET /mail-calls/pending-summaries`

### Voice Calling For Mail Summary Calls

Phase 7 adds outbound Twilio-based delivery for prepared mail summary calls.

This phase only applies to:

- outbound `mail_summary` delivery calls

This phase does not implement:

- reminder calling
- speech-to-text
- user voice replies
- email reply actions

Required backend environment variables:

```text
VOICE_PROVIDER=twilio
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_FROM_PHONE=
PUBLIC_BACKEND_URL=http://localhost:8000
```

### Twilio Setup

1. Create a Twilio account.
2. Buy or configure a Twilio voice-capable phone number.
3. Copy your Account SID and Auth Token.
4. Set `TWILIO_FROM_PHONE` to your Twilio phone number.
5. Set `PUBLIC_BACKEND_URL` to a publicly reachable backend URL.

### Local Development With ngrok

Twilio must reach your backend webhook URLs from the public internet.

Run:

```bash
ngrok http 8000
```

Then set:

```text
PUBLIC_BACKEND_URL=https://your-ngrok-url.ngrok-free.app
```

### Backend Voice Endpoints

- `POST /voice/mail-calls/{call_log_id}/start`
- `GET /voice/mail-calls/{call_log_id}/twiml`
- `POST /voice/webhooks/twilio/status`
- `POST /voice/webhooks/twilio/speech`
- `GET /voice/mail-calls/{call_log_id}/interactions`

### Phase 8 Speech Handling

Phase 8 adds basic speech-to-text handling during mail summary calls.

Voice behavior in the current Phase 8 flow:

```text
Hello. You received today's emails.
I will read a practical number of them for this call.
Is there any important mail you want me to explain in detail?
You can say the email number, or say no to end the call.
```

Supported commands in this phase:

- `repeat summary`
- `repeat`
- `say again`
- `explain email number 1`
- `explain email number 2`
- `read email 3 in detail`
- `end call`
- `stop`
- `no`
- `nothing`
- `that's all`
- `no need`

Detected intents in this phase:

- `REPEAT_SUMMARY`
- `DETAIL_EMAIL`
- `END_CALL`
- `UNKNOWN`

The system stores each interaction in `voice_call_interactions` and responds with TwiML using `detailed_summary`, not raw email bodies.

Additional Phase 8 behavior:

- Voice playback is slowed down with SSML prosody and pauses between sections.
- Live playback reads only today's summaries and only a practical subset for the phone call.
- If there are more emails today than the live playback limit, the caller is told that the dashboard contains the rest.
- The caller can ask for up to 2 detailed email explanations.
- The caller can repeat the summary once.
- Unknown speech is tolerated briefly, then the call ends politely.
- Silence ends the call politely instead of creating an endless loop.

### Phase 9 Advanced Intent Understanding

Phase 9 upgrades the speech webhook with a dedicated intent parser so natural language phrases map more reliably to voice actions.

Supported intents:

- `DETAIL_EMAIL`
- `REPEAT_SUMMARY`
- `END_CALL`
- `HELP`
- `TODAY_SUMMARY`
- `IMPORTANT_CHECK`
- `UNKNOWN`

Example phrases:

- `Tell me more about email one`
- `Explain the first mail`
- `Read email number two in detail`
- `Repeat today's summaries`
- `Say that again`
- `What can I say?`
- `Which emails did I receive today?`
- `Is there anything important?`
- `No`

Important notes:

- The parser uses word boundaries so `know` does not accidentally trigger `END_CALL`.
- Email detail lookup is still based on the numbered summaries read in the current call.
- Sender/subject-based lookup is not part of Phase 9 yet.
- Email replies are not part of Phase 9.

Test checklist:

1. Prepare a today-only mail summary call.
2. Start the Twilio call.
3. Say `Tell me more about the first email`.
4. Confirm `DETAIL_EMAIL` and `email_reference=1`.
5. Say `What can I say?`.
6. Confirm `HELP`.
7. Say `Repeat that`.
8. Confirm `REPEAT_SUMMARY`.
9. Say `I want to know more`.
10. Confirm it does not end the call because of the word `know`.
11. Say `Is there anything important?`.
12. Confirm the safe `IMPORTANT_CHECK` response.
13. Say `No`.
14. Confirm `END_CALL` and a clean hangup.
15. Confirm `voice_call_interactions` includes `user_transcript`, `detected_intent`, `email_reference`, `confidence`, and `system_response_text`.

### Phase 10 Smart Email Detail Search

Phase 10 improves the detail lookup flow so the caller can refer to emails naturally instead of only by number.

Supported lookup styles:

- Number-based: `explain email number one`
- Sender-based: `read the email from Google`
- Subject-based: `explain the Kaggle notebook email`
- Keyword-based: `tell me about the assignment mail`
- Latest / first / last: `read the latest email`

How it works:

- Lookup is limited to the summaries already included in the current today-only mail summary call.
- The assistant does not search the full mailbox.
- If multiple emails match, the assistant asks the caller to choose by number.
- If no match is found, the assistant explains that the email was not in today’s summaries.

Current limitations:

- Sender/subject/keyword lookup is only for the emails already included in the current call.
- Global mailbox search is not part of Phase 10.
- Email replies are not part of Phase 10.

Test checklist:

1. Prepare a today-only mail summary call.
2. Start the Twilio voice call.
3. Say `Explain the latest email`.
4. Say `Tell me about the Kaggle email`.
5. Say `Read the email from Google`.
6. Say `Explain the project email`.
7. Say `No`.
8. Confirm the call ends politely.
9. Verify `voice_call_interactions` shows the original transcript, detected intent, email reference when matched, and system response text.

### Phase 11 Voice-Based Email Reply Agent

Phase 11 lets the caller draft and send a Gmail reply by voice, but only after explicit confirmation.

Supported reply commands:

- `reply to this email`
- `send a reply`
- `reply to email number one`
- `reply saying I will submit it tomorrow`
- `yes send it`
- `no`
- `cancel`
- `edit it`

Safety rules:

- The assistant never sends a reply without explicit confirmation.
- If Gmail send permission is missing, the assistant asks the user to reconnect Gmail.
- The dashboard and Settings page show whether Gmail can send replies.
- If multiple emails match, the assistant asks the user to choose the target email number.
- The assistant stores reply drafts and reply action history in the database.

Known limitations:

- No complex partial editing yet.
- No attachments yet.
- No new email composition yet.
- Replies are limited to the selected email only.

### Manual Email Sync Test Checklist

1. Start the Docker stack.
2. Log in to the app.
3. Make sure Gmail is connected.
4. Open Email Inbox.
5. Click Sync Emails.
6. Confirm emails are fetched and stored.
7. Click Sync Emails again.
8. Confirm duplicate emails are skipped.
9. Open an email detail view.
10. Confirm sender, subject, snippet, body, and received time display correctly.
11. Confirm no AI summary is generated in this phase.
12. Confirm the backend never exposes Gmail access or refresh tokens in the frontend.

## Gmail OAuth Setup

Before testing Gmail connection, create Google OAuth credentials in Google Cloud:

1. Open the Google Cloud Console and select or create a project.
2. Enable the Gmail API for the project.
3. Configure the OAuth consent screen.
4. Add test users if the app is in testing mode.
5. Create OAuth client credentials for a Web application.
6. Add this redirect URI:

```text
http://localhost:8000/gmail/callback
```

Required backend environment variables:

```text
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:8000/gmail/callback
GOOGLE_SCOPES=https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/gmail.send
TOKEN_ENCRYPTION_KEY=
OAUTH_STATE_SECRET=
REDIS_URL=redis://redis:6379/0
LLM_PROVIDER=mock
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
AUTO_EMAIL_SYNC_ENABLED=false
AUTO_EMAIL_SYNC_INTERVAL_MINUTES=5
AUTO_EMAIL_SYNC_BATCH_USERS=20
AUTO_EMAIL_SYNC_MAX_RESULTS=50
AUTO_EMAIL_SYNC_MAX_PAGES=2
AUTO_SUMMARIZE_AFTER_SYNC=false
REMINDER_CALLS_ENABLED=false
REMINDER_CHECK_INTERVAL_SECONDS=60
REMINDER_DUE_GRACE_SECONDS=120
```

To generate `TOKEN_ENCRYPTION_KEY`, run:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

You can set `OAUTH_STATE_SECRET` to a separate random secret, or leave it blank to reuse the app `SECRET_KEY`.

Redis is used to store OAuth nonces for one-time replay protection. Each Gmail OAuth state nonce is written to Redis with a 10-minute TTL and deleted as soon as the callback validates it.

If Redis is unavailable during OAuth connect or callback validation, the flow fails cleanly and token exchange does not continue.

## Known Benign Warning

The backend may print a passlib/bcrypt version warning similar to:

```text
(trapped) error reading bcrypt version
AttributeError: module 'bcrypt' has no attribute '__about__'
```

This warning is benign in the current environment and does not affect the app flow or test results.

## Gmail OAuth State Security

The Gmail OAuth flow uses a signed state payload instead of a plain encoded value.

The signed state includes:

- `user_id`
- `timestamp`
- `nonce`

The backend verifies the signature before exchanging the OAuth code for tokens. It also rejects callbacks if the state is older than 10 minutes.

This protects the Gmail connection flow against:

- tampering with the callback state
- replaying an old callback
- attaching Gmail tokens to the wrong logged-in user

Replay protection uses Redis-backed nonce keys, so each OAuth state can only be used once. Reusing the same callback state will fail.

### Smoke Test Note

- First callback with a valid signed state should succeed.
- Reusing the same state should fail with an expired/already-used error.

## Gmail Connection Test Checklist

1. Start the Docker stack.
2. Run Alembic migrations.
3. Log in to the app.
4. Open Settings / Profile.
5. Click Connect Gmail.
6. Complete Google OAuth consent.
7. Confirm the app returns to Settings with a success message.
8. Confirm Gmail status shows connected.
9. Confirm the Gmail address appears in the UI.
10. Confirm no raw tokens appear in frontend responses.
11. Click Disconnect Gmail.
12. Confirm Gmail status returns to disconnected.

## Automatic Email Sync Test Checklist

1. Start the Docker stack.
2. Run migrations:

```bash
docker compose exec backend alembic upgrade head
```

3. In `backend/.env`, set:

```text
AUTO_EMAIL_SYNC_ENABLED=true
AUTO_EMAIL_SYNC_INTERVAL_MINUTES=1
AUTO_EMAIL_SYNC_MAX_RESULTS=20
AUTO_EMAIL_SYNC_MAX_PAGES=1
AUTO_SUMMARIZE_AFTER_SYNC=true
```

4. Restart the backend or Docker stack.
5. Check backend logs:

```bash
docker compose logs backend --tail=200
```

6. Confirm the log includes `Auto email sync scheduler started`.
7. Send a fresh email to the connected Gmail account.
8. Wait 1 to 2 minutes.
9. Open Email Inbox.
10. Confirm stored email count increases automatically.
11. Confirm the new email appears near the top without manually clicking Sync Emails.
12. Confirm auto sync status shows the latest run result.
13. Click manual Sync Emails.
14. Confirm the same email is skipped as a duplicate.
15. Open Email Summaries and manually generate summaries for any newly inserted unsummarized emails.

## Automatic Email Summary Test Checklist

1. Start the Docker stack.
2. Run migrations.
3. In `backend/.env`, set:

```text
AUTO_EMAIL_SYNC_ENABLED=true
AUTO_EMAIL_SYNC_INTERVAL_MINUTES=1
AUTO_EMAIL_SYNC_BATCH_USERS=20
AUTO_EMAIL_SYNC_MAX_RESULTS=20
AUTO_EMAIL_SYNC_MAX_PAGES=1
AUTO_SUMMARIZE_AFTER_SYNC=true
```

4. Restart the backend or Docker stack.
5. Confirm `GET /emails/auto-sync-status` reports `auto_summarize_after_sync=true`.
6. Send a fresh Gmail message to the connected account.
7. Wait 1 to 2 minutes without clicking Sync Emails or Generate Summaries.
8. Confirm the new email appears in the Inbox and is summarized automatically.
9. Confirm Email Summaries shows the new summary row.
10. Confirm `email_messages.is_summarized=true` for the new email.
11. Click manual Sync Emails and confirm the email is skipped as a duplicate.
12. Click manual Generate Summaries and confirm the auto-summarized email is counted as already summarized.

## Manual Email Summary Test Checklist

1. Start the Docker stack.
2. Log in to the app.
3. Confirm Gmail is connected.
4. Confirm emails are synced in Email Inbox.
5. Open Email Summaries.
6. Click Generate Summaries.
7. Confirm every unsummarized email gets a summary.
8. Confirm `email_messages.is_summarized` becomes `true`.
9. Confirm summaries are listed.
10. Open a detailed summary.
11. Confirm the detailed summary appears.
12. Run Generate Summaries again.
13. Confirm already summarized emails are skipped.
14. Confirm no duplicate summaries are created.
15. Confirm no email is filtered or hidden.

## Manual Mail Summary Call Test Checklist

1. Start the Docker stack.
2. Log in to the app.
3. Confirm email summaries already exist.
4. Open Mail Summary Calls.
5. Confirm count today shows `0 used` and `3 remaining` for a fresh day.
6. Click Prepare Mail Summary Call.
7. Confirm the script is generated only from today's received emails.
8. Confirm a `mail_summary_call_logs` row is created with status `prepared`.
9. Click Mark as Delivered.
10. Confirm the included summaries are marked as delivered.
11. Confirm used mail summary calls today increases.
12. Repeat until used mail summary calls today reaches `3`.
13. Confirm the fourth prepare attempt is blocked.
14. Confirm reminder calls are not involved in this limit.
15. Confirm call history displays correctly.

## Manual Phase 7 Voice Call Test Checklist

1. Start the Docker stack.
2. Log in to the app.
3. Confirm summaries exist.
4. Open Mail Summary Calls.
5. Prepare a mail summary call.
6. Confirm the script is generated.
7. Start ngrok with `ngrok http 8000`.
8. Set `PUBLIC_BACKEND_URL` to the ngrok URL.
9. Add Twilio credentials to `backend/.env`.
10. Rebuild the backend container.
11. Click Start Voice Call.
12. Confirm the target phone receives the call.
13. Confirm Twilio reads the prepared script.
14. Confirm the Twilio status webhook updates `call_status` and `provider_status`.
15. Confirm a completed call marks summaries as delivered.
16. Confirm a failed call stores `failure_reason`.
17. Confirm the daily 3-call rule still applies only to `mail_summary` calls.
18. Confirm reminder calls are not part of this limit.

## Manual Phase 8 Speech Test Checklist

1. Start the Docker stack.
2. Start ngrok.
3. Set `PUBLIC_BACKEND_URL` to the ngrok HTTPS URL.
4. Log in to the app.
5. Confirm there are emails received today.
6. Prepare a mail summary call.
7. Confirm the script mentions only today's email count.
8. Start the voice call.
9. Listen to the summary and confirm the voice is slower and clearer.
10. Confirm the call reads only today's summaries and only a practical subset for playback.
11. When asked, say `explain email number 1`.
12. Confirm the detailed summary is spoken slowly.
13. Say `no`.
14. Confirm the call ends cleanly.
15. Start another call and say `repeat summary`.
16. Confirm the summary repeats once.
17. Say an unknown phrase such as `I want to know something`.
18. Confirm it does not incorrectly match `no` inside `know`.
19. Open Mail Summary Calls in the app.
20. Confirm transcript history, detected intents, email references, and system responses are shown.
21. Confirm `voice_call_interactions` contains rows for the call.

## Manual Phase 14 Voice Reminder Creation Test Checklist

1. Start the Docker stack.
2. Confirm reminder scheduler settings are enabled in `backend/.env`.
3. Confirm ngrok is active and `PUBLIC_BACKEND_URL` points to a live HTTPS tunnel.
4. Log in to the app.
5. Open Mail Summary Calls.
6. Start a mail summary voice call.
7. Ask for an email explanation.
8. Say `Remind me about this email in 2 minutes`.
9. Confirm the assistant asks for confirmation before creating the reminder.
10. Say `Yes save it`.
11. Confirm the assistant says the reminder was saved.
12. Open the Dashboard and confirm the new reminder is visible.
13. Confirm `voice_reminder_sessions` records the session and created reminder.
14. Wait for the reminder time and confirm the reminder call is placed.
15. Confirm the reminder call speaks the reminder title and notes.
16. Confirm the reminder call completes cleanly.
17. Test a general reminder such as `Remind me to check my Kaggle notebook in 2 minutes`.
18. Confirm cancelling with `No` does not create a reminder.
19. Confirm the existing mail summary reply, repeat, and end-call flows still work.
20. Known limitations:
    - recurring reminders are not implemented
    - complex reminder editing by voice is not implemented

## Missed Reminder Recovery

If a reminder call is missed, the app now retries automatically before marking it final missed:

- First miss: retry after 2 minutes
- Second miss: retry after 5 minutes
- Third miss: mark as `missed`

Reminder statuses now include:

- `scheduled`
- `calling`
- `retry_scheduled`
- `snoozed`
- `missed`
- `completed`
- `failed`
- `cancelled`

Dashboard reminder actions:

- `Call Again`
- `Snooze 10 minutes`
- `Mark Done`
- `Cancel`

Manual reminder endpoints:

- `POST /reminders/{id}/call-again`
- `POST /reminders/{id}/snooze`
- `POST /reminders/{id}/mark-done`

Notes:

- Reminder retries do not affect the mail-summary 3-per-day quota.
- Reminder playback calls remain one-way and do not use speech interaction.
- `retry_scheduled` reminders are picked up automatically by the reminder scheduler.
- `snoozed` reminders are picked up once `snoozed_until` has passed.
- `missed` reminders are not auto-called again unless the user explicitly chooses `Call Again`.
