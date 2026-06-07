from app.config import settings


def get_health_payload() -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.app_name,
    }

