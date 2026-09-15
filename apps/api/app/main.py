from fastapi import FastAPI

from .auth_routes import router as auth_router
from .organization_routes import router as organization_router
from .tickets import router as tickets_router
from .customer_routes import router as customers_router
from .property_routes import router as properties_router
from .unit_routes import router as units_router
from .user_routes import router as users_router

app = FastAPI(title="OpsPilot API", version="0.1.0")
app.include_router(auth_router)
app.include_router(organization_router)
app.include_router(users_router)
app.include_router(tickets_router)
app.include_router(customers_router)
app.include_router(properties_router)
app.include_router(units_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "opspilot-api"}
