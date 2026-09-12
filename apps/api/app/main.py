from fastapi import FastAPI

from .tickets import router as tickets_router

app = FastAPI(title="OpsPilot API", version="0.1.0")
app.include_router(tickets_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
