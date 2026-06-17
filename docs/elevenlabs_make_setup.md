# ElevenLabs + Make.com Setup

This project keeps Twilio as the default voice path and adds an optional ElevenLabs + Make.com agent path for mail-summary actions.

## Copy-paste agent setup

### Agent name

`AI Mail Voice Assistant`

### First message

```text
Hello. I’m your AI mail assistant. I can summarize your emails, explain emails, create reminders, create recurring reminders, and help draft replies. What would you like me to do?
```

### System prompt

```text
You are an AI Mail Summary and Reminder Assistant speaking to the user over a phone call.

You can help with:
- reading today’s email summaries
- explaining a selected email
- searching emails by sender, subject, or topic
- creating one-time reminders
- creating email-linked reminders
- creating recurring reminders
- drafting email replies
- sending replies only after explicit confirmation
- ending the call politely

Rules:
1. Speak clearly and briefly.
2. Do not invent email content.
3. Use tools whenever real email, reminder, or reply data is needed.
4. If the user asks about an email, call the correct tool before answering.
5. If the user says "this email", use the currently discussed email.
6. If no email context exists, ask which email they mean.
7. If reminder time is vague, ask a follow-up question.
8. Always confirm before creating reminders.
9. Always confirm before creating recurring reminders.
10. Always draft first before sending replies.
11. Never send an email unless the user explicitly confirms.
12. Stay within email, reminder, recurring reminder, and reply tasks.
13. If unrelated request is asked, politely guide the user back.
14. Do not give medical, legal, or financial advice.
15. If you cannot understand, ask a helpful clarification instead of repeating a fixed menu.
```

### Tool webhook URL

Use this exact Make.com webhook for every tool:

`https://hook.eu1.make.com/svowngbqw3f2vy1om82m5o78gowm2j2c`

### Backend auth header

`X-Agent-API-Key: strong_secret`

If your local backend uses a different value, confirm it matches `backend/.env` before testing.

ElevenLabs dynamic variables should include both `mail_call_id` and `call_id`. Make.com should pass the backend `mail_call_id` field through unchanged so the reply tool can address the correct mail summary call later.

## Tool list

Configure the ElevenLabs agent with the following tools and descriptions.

### 1. Get today summaries

- Name: `get_today_summaries`
- Description: Return the current user’s summaries for today.
- Method: `POST`
- URL: `https://hook.eu1.make.com/svowngbqw3f2vy1om82m5o78gowm2j2c`
- JSON body:

```json
{
  "action": "get_today_summaries",
  "user_id": 2,
  "mail_call_id": "elevenlabs-test",
  "call_id": "elevenlabs-test"
}
```

### 2. Get email detail

- Name: `get_email_detail`
- Description: Return the detailed summary for one selected email.
- Method: `POST`
- URL: `https://hook.eu1.make.com/svowngbqw3f2vy1om82m5o78gowm2j2c`
- JSON body:

```json
{
  "action": "get_email_detail",
  "user_id": 2,
  "mail_call_id": "elevenlabs-test",
  "call_id": "elevenlabs-test",
  "email_reference": 1
}
```

### 3. Search email

- Name: `search_email`
- Description: Search summaries by sender, subject, or topic.
- Method: `POST`
- URL: `https://hook.eu1.make.com/svowngbqw3f2vy1om82m5o78gowm2j2c`
- JSON body:

```json
{
  "action": "search_email",
  "user_id": 2,
  "call_id": "elevenlabs-test",
  "query": "college"
}
```

### 4. Create reminder

- Name: `create_reminder`
- Description: Create a one-time reminder, optionally linked to an email.
- Method: `POST`
- URL: `https://hook.eu1.make.com/svowngbqw3f2vy1om82m5o78gowm2j2c`
- JSON body:

```json
{
  "action": "create_reminder",
  "user_id": 2,
  "call_id": "elevenlabs-test",
  "title": "Check project email",
  "notes": "Follow up with mentor",
  "reminder_time_text": "tomorrow morning",
  "email_reference": 1
}
```

### 5. Create recurring reminder

- Name: `create_recurring_reminder`
- Description: Create a repeating reminder.
- Method: `POST`
- URL: `https://hook.eu1.make.com/svowngbqw3f2vy1om82m5o78gowm2j2c`
- JSON body:

```json
{
  "action": "create_recurring_reminder",
  "user_id": 2,
  "title": "Drink water",
  "notes": "Take a short break",
  "repeat_type": "custom_interval",
  "interval_value": 2,
  "interval_unit": "hours",
  "timezone": "Asia/Kolkata"
}
```

### 6. Draft email reply

- Name: `draft_email_reply`
- Description: Draft a reply before sending.
- Method: `POST`
- URL: `https://hook.eu1.make.com/svowngbqw3f2vy1om82m5o78gowm2j2c`
- JSON body:

```json
{
  "action": "draft_email_reply",
  "user_id": 2,
  "call_id": "elevenlabs-test",
  "email_reference": 1,
  "reply_instruction": "Tell them I will send it tonight"
}
```

### 7. Send email reply

- Name: `send_email_reply`
- Description: Send a reply only after explicit confirmation.
- Method: `POST`
- URL: `https://hook.eu1.make.com/svowngbqw3f2vy1om82m5o78gowm2j2c`
- JSON body:

```json
{
  "action": "send_email_reply",
  "user_id": 2,
  "draft_id": 10
}
```

### 8. Log call feedback

- Name: `log_call_feedback`
- Description: Store safe call feedback and transcript metadata.
- Method: `POST`
- URL: `https://hook.eu1.make.com/svowngbqw3f2vy1om82m5o78gowm2j2c`
- JSON body:

```json
{
  "action": "log_call_feedback",
  "user_id": 2,
  "call_id": "elevenlabs-test",
  "feedback_text": "User was satisfied",
  "transcript": "Test transcript",
  "action_summary": "Read summaries and created reminder"
}
```

### 9. Post-call webhook

- Name: `post_call`
- Description: Store safe post-call summary metadata.
- Method: `POST`
- URL: `https://zombie-huntress-flatly.ngrok-free.dev/agent/elevenlabs/post-call`
- Header: `X-Agent-API-Key: strong_secret`
- JSON body:

```json
{
  "user_id": 2,
  "call_id": "elevenlabs-test",
  "conversation_id": "conv_test",
  "transcript": "User asked for email summaries.",
  "summary": "Read summaries and created a reminder.",
  "status": "completed"
}
```

## Test phrases

- `What are my emails today?`
- `Explain email number one`
- `Search for college email`
- `Remind me about this email in 2 minutes`
- `Create a reminder tomorrow morning`
- `Create a recurring reminder every 2 hours`
- `Draft a reply saying I will send it tonight`
- `Send the reply`
- `End the call`

## Expected results

- Tools return clean JSON.
- No Gmail tokens are exposed.
- No raw email bodies are exposed.
- Reminder creation is confirmed before saving.
- Recurring reminder creation is confirmed before saving.
- Replies are drafted before sending.
- Unsupported requests should be redirected back to email/reminder/reply tasks.

## Safety rules

1. Keep `VOICE_AGENT_PROVIDER=twilio` until you explicitly test ElevenLabs mode.
2. Never log or expose Gmail access tokens or refresh tokens.
3. Never log or expose the ElevenLabs API key or Make webhook URL.
4. Never send an email without explicit confirmation.
5. Never create a reminder without confirmation.
6. Never create a recurring reminder without confirmation.
7. Fall back to Twilio if ElevenLabs settings are missing.
8. Use the Make webhook URL exactly as shown above.

## Current backend validation

- Local backend health: passed
- Public ngrok health: passed
- Direct `/agent/tools`: passed with `X-Agent-API-Key: strong_secret`
- Make webhook: accepted the payload, but the public response is `Accepted`
- Targeted agent tests: passed
- Full backend tests: passed

If you want me to finish the live ElevenLabs UI setup, I can give you a strict field-by-field checklist for the agent builder next.
