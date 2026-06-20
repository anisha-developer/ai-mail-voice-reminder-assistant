from fastapi import APIRouter

from app.api.routes.emails import router as emails_router
from app.api.routes.email_replies import router as email_replies_router
from app.api.routes.summaries import router as summaries_router
from app.api.routes.auth import router as auth_router
from app.api.routes.agent_tools import router as agent_tools_router
from app.api.routes.gmail import router as gmail_router
from app.api.routes.health import router as health_router
from app.api.routes.call_preferences import router as call_preferences_router
from app.api.routes.mail_calls import router as mail_calls_router
from app.api.routes.priority_contacts import router as priority_contacts_router
from app.api.routes.recurring_reminders import router as recurring_reminders_router
from app.api.routes.reminders import router as reminders_router
from app.api.routes.users import router as users_router
from app.api.routes.voice import router as voice_router

api_router = APIRouter()
api_router.include_router(agent_tools_router)
api_router.include_router(auth_router)
api_router.include_router(gmail_router)
api_router.include_router(call_preferences_router)
api_router.include_router(priority_contacts_router)
api_router.include_router(emails_router)
api_router.include_router(email_replies_router)
api_router.include_router(summaries_router)
api_router.include_router(mail_calls_router)
api_router.include_router(reminders_router)
api_router.include_router(recurring_reminders_router)
api_router.include_router(voice_router)
api_router.include_router(users_router)
api_router.include_router(health_router)
