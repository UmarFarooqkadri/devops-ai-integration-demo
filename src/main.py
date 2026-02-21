"""FastAPI application — AI-powered DevOps automation platform."""

from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException
from prometheus_client import Counter, Histogram, generate_latest
from pydantic import BaseModel
from starlette.responses import Response

from src.agents.orchestrator import AgentOrchestrator
from src.config import get_settings

logger = structlog.get_logger()

# ── Metrics ─────────────────────────────────────────────────────────────────
REQUEST_COUNT = Counter("api_requests_total", "Total API requests", ["endpoint", "status"])
REQUEST_LATENCY = Histogram("api_request_duration_seconds", "Request latency", ["endpoint"])

# ── Request/Response models ─────────────────────────────────────────────────

class IncidentRequest(BaseModel):
    description: str
    severity: str = "medium"
    namespace: str = "default"


class InfraRequest(BaseModel):
    request: str
    environment: str = "staging"
    dry_run: bool = True


class PipelineRequest(BaseModel):
    repo: str = ""
    workflow_content: str


class AgentResponse(BaseModel):
    status: str
    agent: str
    result: dict[str, Any]


# ── App lifecycle ───────────────────────────────────────────────────────────
orchestrator: AgentOrchestrator | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and teardown resources."""
    global orchestrator
    settings = get_settings()
    orchestrator = AgentOrchestrator(settings)
    logger.info("platform_started", model=settings.openai_model, namespace=settings.k8s_namespace)
    yield
    logger.info("platform_shutdown")


app = FastAPI(
    title="DevOps AI Ops Platform",
    description="AI-powered DevOps automation for incident response, IaC, and CI/CD optimization",
    version="1.0.0",
    lifespan=lifespan,
)


# ── Endpoints ───────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "healthy", "model": get_settings().openai_model}


@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type="text/plain")


@app.get("/api/v1/status")
async def status():
    return {
        "status": "operational",
        "agents": ["incident", "infrastructure", "pipeline"],
        "namespace": get_settings().k8s_namespace,
    }


@app.post("/api/v1/incidents", response_model=AgentResponse)
async def handle_incident(req: IncidentRequest):
    """Analyze an incident and suggest/execute remediation."""
    with REQUEST_LATENCY.labels(endpoint="incidents").time():
        try:
            result = await orchestrator.handle_incident(
                description=req.description,
                severity=req.severity,
                namespace=req.namespace,
            )
            REQUEST_COUNT.labels(endpoint="incidents", status="success").inc()
            return AgentResponse(status="completed", agent="incident", result=result)
        except Exception as e:
            REQUEST_COUNT.labels(endpoint="incidents", status="error").inc()
            logger.error("incident_failed", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/infrastructure", response_model=AgentResponse)
async def provision_infrastructure(req: InfraRequest):
    """Generate and validate a Terraform plan from natural language."""
    with REQUEST_LATENCY.labels(endpoint="infrastructure").time():
        try:
            result = await orchestrator.handle_infrastructure(
                request=req.request,
                environment=req.environment,
                dry_run=req.dry_run,
            )
            REQUEST_COUNT.labels(endpoint="infrastructure", status="success").inc()
            return AgentResponse(status="completed", agent="infrastructure", result=result)
        except Exception as e:
            REQUEST_COUNT.labels(endpoint="infrastructure", status="error").inc()
            logger.error("infra_failed", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/pipelines/optimize", response_model=AgentResponse)
async def optimize_pipeline(req: PipelineRequest):
    """Analyze a CI/CD workflow and suggest optimizations."""
    with REQUEST_LATENCY.labels(endpoint="pipelines").time():
        try:
            result = await orchestrator.handle_pipeline(
                repo=req.repo,
                workflow_content=req.workflow_content,
            )
            REQUEST_COUNT.labels(endpoint="pipelines", status="success").inc()
            return AgentResponse(status="completed", agent="pipeline", result=result)
        except Exception as e:
            REQUEST_COUNT.labels(endpoint="pipelines", status="error").inc()
            logger.error("pipeline_failed", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))
