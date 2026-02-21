"""Agent orchestrator — classifies intent and routes to specialist agents."""

from typing import Any

import structlog
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from src.agents.incident_agent import IncidentAgent
from src.agents.infra_agent import InfrastructureAgent
from src.agents.pipeline_agent import PipelineAgent
from src.config import Settings

logger = structlog.get_logger()


class AgentOrchestrator:
    """Routes DevOps requests to the appropriate specialist agent using LLM classification."""

    def __init__(self, settings: Settings):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
        self.incident_agent = IncidentAgent(settings)
        self.infra_agent = InfrastructureAgent(settings)
        self.pipeline_agent = PipelineAgent(settings)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def _classify_intent(self, text: str) -> str:
        """Use LLM to classify the request type."""
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Classify the DevOps request into exactly one category: "
                        "incident, infrastructure, or pipeline. "
                        "Respond with only the category name."
                    ),
                },
                {"role": "user", "content": text},
            ],
            temperature=0,
            max_tokens=20,
        )
        intent = response.choices[0].message.content.strip().lower()
        logger.info("intent_classified", intent=intent, text=text[:80])
        return intent

    async def handle_incident(
        self, description: str, severity: str, namespace: str
    ) -> dict[str, Any]:
        """Route to incident agent for analysis and remediation."""
        logger.info("handling_incident", severity=severity, namespace=namespace)
        return await self.incident_agent.analyze(description, severity, namespace)

    async def handle_infrastructure(
        self, request: str, environment: str, dry_run: bool
    ) -> dict[str, Any]:
        """Route to infrastructure agent for Terraform planning."""
        logger.info("handling_infrastructure", environment=environment, dry_run=dry_run)
        return await self.infra_agent.plan(request, environment, dry_run)

    async def handle_pipeline(
        self, repo: str, workflow_content: str
    ) -> dict[str, Any]:
        """Route to pipeline agent for CI/CD optimization."""
        logger.info("handling_pipeline", repo=repo)
        return await self.pipeline_agent.optimize(repo, workflow_content)

    async def route(self, text: str) -> dict[str, Any]:
        """Auto-classify and route a free-text DevOps request."""
        intent = await self._classify_intent(text)
        handlers = {
            "incident": lambda: self.handle_incident(text, "medium", "default"),
            "infrastructure": lambda: self.handle_infrastructure(text, "staging", True),
            "pipeline": lambda: self.handle_pipeline("", text),
        }
        handler = handlers.get(intent)
        if not handler:
            return {"error": f"Unknown intent: {intent}", "supported": list(handlers)}
        return await handler()
