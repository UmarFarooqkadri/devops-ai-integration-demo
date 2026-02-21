"""Pipeline agent — analyzes GitHub Actions workflows and suggests optimizations."""

import json
from typing import Any

import structlog
import yaml
from openai import AsyncOpenAI

from src.config import Settings

logger = structlog.get_logger()


class PipelineAgent:
    """Analyzes CI/CD workflows and suggests concrete optimizations."""

    def __init__(self, settings: Settings):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model

    def _parse_workflow(self, content: str) -> dict:
        """Parse a GitHub Actions workflow YAML and extract structure."""
        try:
            workflow = yaml.safe_load(content)
        except yaml.YAMLError:
            return {"error": "Invalid YAML"}

        if not isinstance(workflow, dict):
            return {"error": "Not a valid workflow"}

        jobs = workflow.get("jobs", {})
        analysis = {
            "total_jobs": len(jobs),
            "jobs": {},
            "triggers": list(workflow.get("on", {}).keys()) if isinstance(workflow.get("on"), dict) else [str(workflow.get("on", ""))],
        }

        for job_name, job_config in jobs.items():
            steps = job_config.get("steps", [])
            analysis["jobs"][job_name] = {
                "steps": len(steps),
                "runs_on": job_config.get("runs-on", "unknown"),
                "needs": job_config.get("needs", []),
                "has_cache": any("cache" in str(s).lower() for s in steps),
                "has_matrix": "matrix" in str(job_config.get("strategy", {})),
                "has_artifacts": any("upload-artifact" in str(s) or "download-artifact" in str(s) for s in steps),
                "uses_actions": [
                    s.get("uses", "").split("@")[0]
                    for s in steps
                    if isinstance(s, dict) and s.get("uses")
                ],
            }
        return analysis

    def _detect_quick_wins(self, analysis: dict) -> list[dict]:
        """Detect optimization opportunities from workflow structure."""
        suggestions = []

        for job_name, job in analysis.get("jobs", {}).items():
            if not job.get("has_cache"):
                suggestions.append({
                    "type": "caching",
                    "job": job_name,
                    "impact": "high",
                    "description": f"Job '{job_name}' has no dependency caching — add actions/cache for package managers",
                })

            if job.get("steps", 0) > 8 and not job.get("has_matrix"):
                suggestions.append({
                    "type": "parallelization",
                    "job": job_name,
                    "impact": "medium",
                    "description": f"Job '{job_name}' has {job['steps']} steps — consider splitting into parallel jobs or using matrix strategy",
                })

            if not job.get("has_artifacts") and analysis["total_jobs"] > 1:
                suggestions.append({
                    "type": "artifacts",
                    "job": job_name,
                    "impact": "low",
                    "description": f"Job '{job_name}' doesn't use artifacts — consider sharing build outputs between jobs",
                })

        # Check for independent jobs that could run in parallel
        jobs_with_deps = {name: j.get("needs", []) for name, j in analysis.get("jobs", {}).items()}
        independent = [name for name, deps in jobs_with_deps.items() if not deps]
        if len(independent) > 1:
            suggestions.append({
                "type": "parallelization",
                "job": "workflow",
                "impact": "high",
                "description": f"Jobs {independent} have no dependencies — they already run in parallel (good!)",
            })

        return suggestions

    async def optimize(self, repo: str, workflow_content: str) -> dict[str, Any]:
        """Full pipeline analysis: parse, detect quick wins, LLM deep analysis."""
        # Structural analysis
        analysis = self._parse_workflow(workflow_content)
        quick_wins = self._detect_quick_wins(analysis)

        # LLM deep analysis for nuanced suggestions
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a CI/CD expert specializing in GitHub Actions optimization. "
                        "Analyze the workflow and provide concrete improvements.\n"
                        "For each suggestion, include:\n"
                        "- category: caching|parallelization|security|cost|speed\n"
                        "- description: what to change and why\n"
                        "- before: the current YAML snippet (if applicable)\n"
                        "- after: the improved YAML snippet\n"
                        "- estimated_time_saved: rough estimate in minutes\n"
                        "Return JSON with a 'suggestions' array."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Repository: {repo}\n\nWorkflow:\n```yaml\n{workflow_content}\n```",
                },
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        llm_suggestions = json.loads(response.choices[0].message.content)

        return {
            "workflow_analysis": analysis,
            "quick_wins": quick_wins,
            "ai_suggestions": llm_suggestions.get("suggestions", []),
            "summary": {
                "total_jobs": analysis.get("total_jobs", 0),
                "optimization_opportunities": len(quick_wins) + len(llm_suggestions.get("suggestions", [])),
            },
        }
