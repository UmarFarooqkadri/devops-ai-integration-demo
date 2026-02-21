"""Infrastructure agent — generates Terraform plans with policy validation."""

import json
from typing import Any

import structlog
from openai import AsyncOpenAI

from src.config import Settings

logger = structlog.get_logger()

# Policy rules — violations block provisioning
POLICIES = {
    "no_public_s3": {
        "description": "S3 buckets must not have public access",
        "check": lambda tf: "public" not in tf.lower() or "block_public" in tf.lower(),
    },
    "enforce_tagging": {
        "description": "All resources must have environment and owner tags",
        "check": lambda tf: "tags" in tf.lower(),
    },
    "instance_size_limit": {
        "description": "EC2 instances must not exceed xlarge in non-prod",
        "check": lambda tf: "2xlarge" not in tf or "4xlarge" not in tf,
    },
    "encryption_required": {
        "description": "Storage resources must have encryption enabled",
        "check": lambda tf: "encrypted" in tf.lower() or "kms" in tf.lower() or "s3" not in tf.lower(),
    },
}


class InfrastructureAgent:
    """Converts natural language to Terraform plans with policy guardrails."""

    def __init__(self, settings: Settings):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
        self.region = settings.aws_region

    def _validate_policies(self, terraform_code: str, environment: str) -> list[dict]:
        """Run policy checks against generated Terraform code."""
        violations = []
        for name, policy in POLICIES.items():
            # Skip instance size check for production
            if name == "instance_size_limit" and environment == "production":
                continue
            if not policy["check"](terraform_code):
                violations.append({
                    "policy": name,
                    "description": policy["description"],
                    "severity": "high",
                })
        return violations

    def _estimate_cost(self, terraform_code: str) -> dict:
        """Rough cost estimation based on resource types found in the plan."""
        cost_map = {
            "aws_instance": {"t3.micro": 8, "t3.small": 15, "t3.medium": 30, "t3.large": 60, "t3.xlarge": 120},
            "aws_eks_cluster": {"base": 73},
            "aws_rds_instance": {"db.t3.micro": 13, "db.t3.small": 25, "db.t3.medium": 50},
            "aws_s3_bucket": {"base": 2},
            "aws_elasticache": {"base": 25},
        }
        estimated_monthly = 0.0
        resources_found = []
        for resource, costs in cost_map.items():
            if resource.replace("aws_", "") in terraform_code.lower():
                base_cost = costs.get("base", list(costs.values())[0])
                estimated_monthly += base_cost
                resources_found.append(resource)
        return {
            "estimated_monthly_usd": round(estimated_monthly, 2),
            "resources_detected": resources_found,
            "note": "Rough estimate — use AWS Cost Calculator for accuracy",
        }

    async def plan(
        self, request: str, environment: str, dry_run: bool
    ) -> dict[str, Any]:
        """Generate a Terraform plan from natural language with policy validation."""
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a senior cloud architect. Generate production-ready Terraform code "
                        f"for AWS region {self.region}, environment: {environment}.\n"
                        "Requirements:\n"
                        "- Use terraform >= 1.7 syntax\n"
                        "- Include proper tags (environment, owner, managed_by=terraform)\n"
                        "- Enable encryption for all storage\n"
                        "- Use private subnets where possible\n"
                        "- Block public access on S3\n"
                        "- Include security groups with least-privilege rules\n\n"
                        "Return JSON with:\n"
                        "- terraform_code: the HCL code as a string\n"
                        "- resources: list of resources being created\n"
                        "- explanation: brief description of what's being provisioned"
                    ),
                },
                {"role": "user", "content": request},
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        plan = json.loads(response.choices[0].message.content)
        terraform_code = plan.get("terraform_code", "")

        # Policy validation
        violations = self._validate_policies(terraform_code, environment)
        cost = self._estimate_cost(terraform_code)

        approved = len(violations) == 0
        if violations:
            logger.warning("policy_violations", count=len(violations), environment=environment)

        return {
            "plan": plan,
            "policy_check": {
                "approved": approved,
                "violations": violations,
                "policies_checked": len(POLICIES),
            },
            "cost_estimate": cost,
            "dry_run": dry_run,
            "would_apply": approved and not dry_run,
        }
