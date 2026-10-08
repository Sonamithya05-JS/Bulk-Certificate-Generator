"""FastAPI application: wires together routers, startup and error handlers."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api import certificates, jobs
from app.config import CERTIFICATES_DIR
from app.database.database import init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs once at startup: create DB tables and the certificates folder."""
    init_db()
    CERTIFICATES_DIR.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="Bulk Certificate Generator API",
    description="Submit a list of recipients once and get one PDF certificate per recipient.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(jobs.router)
app.include_router(certificates.router)


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Turn Pydantic's verbose errors into a short, readable list."""
    errors = [
        {
            "field": ".".join(str(part) for part in error["loc"] if part != "body"),
            "message": str(error["msg"]).removeprefix("Value error, "),
        }
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422, content={"detail": "Invalid request data", "errors": errors}
    )


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """Log the real error, but never show database internals to API users."""
    logger.exception("Database error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "A database error occurred"})
