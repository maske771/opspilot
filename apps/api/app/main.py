import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .auth_routes import router as auth_router
from .organization_routes import router as organization_router
from .tickets import router as tickets_router
from .customer_routes import router as customers_router
from .property_routes import router as properties_router
from .unit_routes import router as units_router
from .user_routes import router as users_router
from .dashboard_routes import router as dashboard_router
from .channel_routes import router as channel_router
from .conversation_routes import router as conversation_router
from .inbox_routes import router as inbox_router
from .webhook_routes import router as webhook_router
from .ai_routes import router as ai_router
from .observability import instrumentator, router as observability_router

app = FastAPI(title="OpsPilot API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(organization_router)
app.include_router(users_router)
app.include_router(tickets_router)
app.include_router(customers_router)
app.include_router(properties_router)
app.include_router(units_router)
app.include_router(dashboard_router)
app.include_router(channel_router)
app.include_router(conversation_router)
app.include_router(inbox_router)
app.include_router(webhook_router)
app.include_router(ai_router)
app.include_router(observability_router)

instrumentator.instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "opspilot-api"}
