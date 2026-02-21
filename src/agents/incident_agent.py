"""Incident agent — analyzes K8s incidents and executes safe remediations."""

import json
from typing import Any

import structlog
from kubernetes import client as k8s_client
from kubernetes import config as k8s_config
from openai import AsyncOpenAI

from src.config import Settings

logger = structlog.get_logger()

# Safe remediations that can be auto-executed without human approval
SAFE_ACTIONS = {"restart_pod", "scale_up_deployment"}


class IncidentAgent:
    """Analyzes incidents using LLM + K8s API, suggests and executes remediations."""

    def __init__(self, settings: Settings):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
        self.namespace = settings.k8s_namespace
        self._k8s_initialized = False

    def _init_k8s(self):
        """Lazy-init K8s client (may not be available in dev)."""
        if self._k8s_initialized:
            return
        try:
            k8s_config.load_incluster_config()
        except k8s_config.ConfigException:
            try:
                k8s_config.load_kube_config()
            except k8s_config.ConfigException:
                logger.warning("k8s_not_available", msg="Running without K8s access")
                return
        self._k8s_initialized = True

    def _get_pod_status(self, namespace: str) -> list[dict]:
        """Query K8s for pod status in the given namespace."""
        self._init_k8s()
        if not self._k8s_initialized:
            return [{"error": "K8s not available"}]
        v1 = k8s_client.CoreV1Api()
        pods = v1.list_namespaced_pod(namespace=namespace)
        return [
            {
                "name": pod.metadata.name,
                "phase": pod.status.phase,
                "restarts": sum(
                    cs.restart_count for cs in (pod.status.container_statuses or [])
                ),
                "ready": all(
                    cs.ready for cs in (pod.status.container_statuses or [])
                ),
            }
            for pod in pods.items
        ]

    def _get_pod_logs(self, pod_name: str, namespace: str, tail: int = 50) -> str:
        """Fetch recent logs from a pod."""
        self._init_k8s()
        if not self._k8s_initialized:
            return "K8s not available — cannot fetch logs"
        v1 = k8s_client.CoreV1Api()
        try:
            return v1.read_namespaced_pod_log(
                name=pod_name, namespace=namespace, tail_lines=tail
            )
        except k8s_client.ApiException as e:
            return f"Failed to fetch logs: {e.reason}"

    def _restart_pod(self, pod_name: str, namespace: str) -> str:
        """Delete a pod to trigger restart via its controller."""
        self._init_k8s()
        if not self._k8s_initialized:
            return "K8s not available"
        v1 = k8s_client.CoreV1Api()
        v1.delete_namespaced_pod(name=pod_name, namespace=namespace)
        logger.info("pod_restarted", pod=pod_name, namespace=namespace)
        return f"Pod {pod_name} deleted — controller will recreate it"

    def _scale_deployment(self, deployment: str, namespace: str, replicas: int) -> str:
        """Scale a deployment to the specified replica count."""
        self._init_k8s()
        if not self._k8s_initialized:
            return "K8s not available"
        apps = k8s_client.AppsV1Api()
        apps.patch_namespaced_deployment_scale(
            name=deployment,
            namespace=namespace,
            body={"spec": {"replicas": replicas}},
        )
        logger.info("deployment_scaled", deployment=deployment, replicas=replicas)
        return f"Deployment {deployment} scaled to {replicas} replicas"

    async def analyze(
        self, description: str, severity: str, namespace: str
    ) -> dict[str, Any]:
        """Full incident analysis: gather context, LLM analysis, remediation."""
        # Gather K8s context
        pod_status = self._get_pod_status(namespace)
        unhealthy = [p for p in pod_status if not p.get("ready") or p.get("restarts", 0) > 3]

        # Get logs from unhealthy pods
        pod_logs = {}
        for pod in unhealthy[:3]:  # limit to 3 pods to avoid token overflow
            pod_logs[pod["name"]] = self._get_pod_logs(pod["name"], namespace)

        # LLM analysis
        context = json.dumps(
            {"pod_status": pod_status, "unhealthy_pods": unhealthy, "pod_logs": pod_logs},
            indent=2,
        )
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a senior SRE analyzing a Kubernetes incident. "
                        "Given the incident description and cluster state, provide:\n"
                        "1. root_cause: Most likely root cause\n"
                        "2. impact: Blast radius and user impact\n"
                        "3. remediation_steps: Ordered list of actions\n"
                        "4. safe_actions: Actions from this set that can be auto-executed: "
                        f"{SAFE_ACTIONS}\n"
                        "5. prevention: How to prevent recurrence\n"
                        "Respond in JSON format."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Incident: {description}\nSeverity: {severity}\n\nCluster state:\n{context}",
                },
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        analysis = json.loads(response.choices[0].message.content)

        # Auto-execute safe remediations for high severity
        executed = []
        if severity == "high" and analysis.get("safe_actions"):
            for action in analysis["safe_actions"]:
                if action == "restart_pod" and unhealthy:
                    result = self._restart_pod(unhealthy[0]["name"], namespace)
                    executed.append({"action": action, "result": result})
                elif action == "scale_up_deployment":
                    executed.append({"action": action, "result": "Requires deployment name — skipped"})

        return {
            "analysis": analysis,
            "cluster_context": {"total_pods": len(pod_status), "unhealthy": len(unhealthy)},
            "auto_executed": executed,
        }
