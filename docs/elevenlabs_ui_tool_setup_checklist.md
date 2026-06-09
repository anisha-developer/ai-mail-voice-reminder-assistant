# ElevenLabs UI Tool Setup Checklist

Use this checklist to configure the ElevenLabs Conversational AI agent manually if browser automation is not available.

## 1) Agent basics

- **Agent name:** `AI Mail Voice Assistant`
- **First message:**

```text
Hello. I’m your AI mail assistant. I can summarize your emails, explain emails, create reminders, create recurring reminders, and help draft replies. What would you like me to do?
```

- **System prompt:**

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

## 2) Common tool settings

- **Tool type:** `Webhook` or `Server tool`
- **Method:** `POST`
- **URL:** `https://hook.eu1.make.com/svowngbqw3f2vy1om82m5o78gowm2j2c`
- **Headers:**
  - `Content-Type: application/json`

Important:

- Do **not** put `X-Agent-API-Key` inside ElevenLabs.
- Make.com should send `X-Agent-API-Key: strong_secret` when it forwards the tool call to the backend.
- Keep `VOICE_AGENT_PROVIDER=twilio` until all ElevenLabs tools are confirmed.

## 3) Tools to add

### Tool 1: get_today_summaries

- **Name:** `get_today_summaries`
- **Description:** Use when the user asks what emails they have today or when the call starts and you need today’s email summaries. The tool returns a JSON object with a top-level `message` field and `data.summaries`. If `message` is present, speak the message directly. Do not say the tool failed when `success` is true or summaries are returned.
- **Body:**

```json
{
  "action": "get_today_summaries",
  "user_id": 2,
  "call_id": "elevenlabs-test"
}
```

- **Test phrase:** `What emails do I have today?`
- **Expected result:** short numbered list of today’s email summaries

### Tool 2: get_email_detail

- **Name:** `get_email_detail`
- **Description:** Use when the user asks to explain a specific email by number or when the assistant needs a more detailed explanation after `get_today_summaries`. Speak only the top-level `message` field. Do not read the raw JSON or internal IDs unless the user asks for details.
- **Method:** `POST`
- **URL:** `https://hook.eu1.make.com/svowngbqw3f2vy1om82m5o78gowm2j2c`
- **Body:**

```json
{
  "action": "get_email_detail",
  "user_id": 2,
  "email_summary_id": "{{email_summary_id}}",
  "call_id": "{{call_id}}"
}
```

- **Test phrase:** `Explain email one.`
- **Expected result:** detailed explanation for the selected email, spoken from the top-level `message`

### Tool 3: search_email

- **Name:** `search_email`
- **Description:** Use when the user describes an email by sender, subject, or topic instead of number.
- **Body:**

```json
{
  "action": "search_email",
  "user_id": 2,
  "call_id": "elevenlabs-test",
  "query": "college"
}
```

- **Test phrase:** `Tell me about the college email.`
- **Expected result:** matching email summaries

### Tool 4: create_reminder

- **Name:** `create_reminder`
- **Description:** Use only after the user clearly wants a one-time reminder and the title/time are known. Always confirm first.
- **Body:**

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

- **Test phrase:** `Remind me about email one tomorrow morning.`
- **Expected result:** agent asks for confirmation before saving

### Tool 5: create_recurring_reminder

- **Name:** `create_recurring_reminder`
- **Description:** Use only after the user wants a repeating reminder. Always confirm first.
- **Body:**

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

- **Test phrase:** `Remind me every two hours to drink water.`
- **Expected result:** agent asks for confirmation before saving

### Tool 6: draft_email_reply

- **Name:** `draft_email_reply`
- **Description:** Use when the user wants to reply to an email. This creates a draft only.
- **Body:**

```json
{
  "action": "draft_email_reply",
  "user_id": 2,
  "call_id": "elevenlabs-test",
  "email_reference": 1,
  "reply_instruction": "Tell them I will send it tonight"
}
```

- **Test phrase:** `Draft a reply to email one saying I will send it tonight.`
- **Expected result:** draft is created and read back

### Tool 7: send_email_reply

- **Name:** `send_email_reply`
- **Description:** Use only after a draft exists and the user explicitly confirms sending.
- **Body:**

```json
{
  "action": "send_email_reply",
  "user_id": 2,
  "draft_id": "<REAL_DRAFT_ID_FROM_PREVIOUS_TOOL>"
}
```

- **Test phrase:** `Yes, send it.`
- **Expected result:** send only after a real draft ID exists

### Tool 8: log_call_feedback

- **Name:** `log_call_feedback`
- **Description:** Use after or during a conversation to log safe call feedback, transcript, or action summary.
- **Body:**

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

- **Test phrase:** `Log that the user was satisfied with the call.`
- **Expected result:** safe feedback recorded

## 4) Post-call webhook

If you want ElevenLabs or Make to send a post-call summary back to the backend:

- **Endpoint:** `POST /agent/elevenlabs/post-call`
- **URL:** `https://zombie-huntress-flatly.ngrok-free.dev/agent/elevenlabs/post-call`
- **Header:** `X-Agent-API-Key: strong_secret`
- **Body:**

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

## 5) Validation notes

- Local backend health: OK
- Public ngrok health: OK
- Direct `/agent/tools`: OK
- Make webhook accepted payloads: OK
- Targeted backend tests: OK
- Full backend tests: OK

## 6) Important safety rules

1. Keep Twilio as the active provider until ElevenLabs is fully verified.
2. Do not expose Gmail tokens.
3. Do not expose OpenAI keys.
4. Do not expose ElevenLabs keys.
5. Do not expose the Make webhook secret.
6. Do not send email replies without explicit confirmation.
7. Do not create reminders without explicit confirmation.
8. Do not permanently switch provider until the live ElevenLabs flow is validated.

## 7) If UI automation is unavailable

If ElevenLabs login or the browser session cannot be automated, use this document as the exact manual checklist. Paste each field exactly as shown, then add the tools one by one in the same order.
