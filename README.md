# DevOps AI Ops Platform

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)
![Terraform](https://img.shields.io/badge/Terraform-1.7+-purple?logo=terraform)
![Kubernetes](https://img.shields.io/badge/Kubernetes-1.28+-blue?logo=kubernetes)
![Docker](https://img.shields.io/badge/Docker-24+-blue?logo=docker)
![License](https://img.shields.io/badge/License-MIT-green)

An AI-powered DevOps automation platform that uses LLM agents to automate incident response, infrastructure provisioning, and CI/CD pipeline optimization.

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────────────────────┐
│   User /     │     │   FastAPI         │     │   Agent Orchestrator (LLM)      │
│   Slack /    │────▶│   Gateway         │────▶│   - Classifies intent           │
│   PagerDuty  │     │   :8000           │     │   - Routes to specialist agent  │
└─────────────┘     └──────────────────┘     └──────────┬──────────────────────┘
                                                         │
                    ┌────────────────────────────────────┼────────────────────────┐
                    │                    │               │            │           │
              ┌─────▼──────┐  ┌─────────▼───┐  ┌───────▼────┐  ┌───▼────────┐  │
              │  Incident   │  │  Infra       │  │  Pipeline  │  │ Monitoring │  │
              │  Agent      │  │  Agent       │  │  Agent     │  │ Agent      │  │
              │             │  │              │  │            │  │            │  │
              │ - Analyze   │  │ - Generate   │  │ - Analyze  │  │ - Query    │  │
              │   logs      │  │   Terraform  │  │   GH       │  │   Prom     │  │
              │ - Query K8s │  │ - Validate   │  │   Actions  │  │ - Detect   │  │
              │ - Auto-     │  │   policies   │  │ - Suggest  │  │   anomaly  │  │
              │   remediate │  │ - Plan/Apply │  │   optimize │  │ - Alert    │  │
              └──────┬──────┘  └──────┬───────┘  └─────┬──────┘  └─────┬──────┘  │
                     │               │               │               │           │
              ┌──────▼───────────────▼───────────────▼───────────────▼──────┐    │
              │                    Cloud Infrastructure                      │    │
              │   AWS EKS  ·  Terraform State  ·  Prometheus  ·  Grafana    │    │
              └─────────────────────────────────────────────────────────────┘    │
              └─────────────────────────────────────────────────────────────────┘
```

## Features

- **AI Incident Response** — Analyzes incidents, queries K8s pod status/logs, suggests and auto-executes safe remediations (pod restart, scale up)
- **Infrastructure Provisioning** — Converts natural language to Terraform plans with built-in policy validation (no public S3, enforce tagging, instance limits)
- **CI/CD Optimization** — Analyzes GitHub Actions workflows and suggests caching, parallelization, matrix builds, artifact reuse
- **Monitoring Integration** — Prometheus metrics, Grafana dashboards, anomaly detection via LLM

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI, Uvicorn, Pydantic |
| AI/LLM | OpenAI GPT-4o, LangChain |
| IaC | Terraform, AWS EKS |
| Containers | Docker, Kubernetes, Helm |
| CI/CD | GitHub Actions, Argo CD |
| Monitoring | Prometheus, Grafana, structlog |
| Cache/Queue | Redis |

## Quick Start

```bash
# Clone
git clone https://github.com/UmarFarooqkadri/devops-ai-integration-demo.git
cd devops-ai-integration-demo

# Install
make install

# Configure
cp .env.example .env
# Edit .env with your API keys

# Run locally
make run-agent

# Or run with Docker
make docker-build
docker-compose up -d
```

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | required |
| `OPENAI_MODEL` | LLM model | `gpt-4o` |
| `K8S_NAMESPACE` | Target namespace | `devops-ai` |
| `AWS_REGION` | AWS region | `eu-north-1` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `REDIS_URL` | Redis connection | `redis://localhost:6379` |

## Usage Examples

### Incident Response
```bash
curl -X POST http://localhost:8000/api/v1/incidents \
  -H "Content-Type: application/json" \
  -d '{"description": "Pod crash-looping in production namespace", "severity": "high", "namespace": "production"}'
```

### Infrastructure Provisioning
```bash
curl -X POST http://localhost:8000/api/v1/infrastructure \
  -H "Content-Type: application/json" \
  -d '{"request": "Create a new staging EKS cluster with 3 nodes in eu-north-1", "environment": "staging"}'
```

### Pipeline Optimization
```bash
curl -X POST http://localhost:8000/api/v1/pipelines/optimize \
  -H "Content-Type: application/json" \
  -d '{"repo": "my-org/my-app", "workflow_content": "..."}'
```

## Project Structure

```
.
├── src/
│   ├── main.py                  # FastAPI application
│   ├── config.py                # Pydantic settings
│   └── agents/
│       ├── orchestrator.py      # LLM-based request router
│       ├── incident_agent.py    # K8s incident analysis & remediation
│       ├── infra_agent.py       # Terraform generation & policy validation
│       └── pipeline_agent.py    # GitHub Actions optimization
├── terraform/
│   ├── main.tf                  # EKS cluster, VPC, IAM
│   ├── variables.tf             # Input variables
│   └── outputs.tf               # Cluster outputs
├── k8s/
│   ├── namespace.yaml           # Namespace definition
│   ├── deployment.yaml          # App deployment with security contexts
│   ├── service.yaml             # ClusterIP service
│   ├── configmap.yaml           # Runtime configuration
│   └── hpa.yaml                 # Horizontal Pod Autoscaler
├── monitoring/
│   └── prometheus.yml           # Prometheus scrape config
├── .github/workflows/
│   ├── ci.yml                   # Lint, test, scan, build
│   └── deploy.yml               # Terraform + K8s deployment
├── Dockerfile                   # Multi-stage production build
├── docker-compose.yml           # Local dev stack
├── Makefile                     # Dev/deploy commands
└── requirements.txt             # Python dependencies
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Run linting and tests (`make lint test`)
4. Commit your changes (`git commit -m 'Add amazing feature'`)
5. Push to the branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request

## License

MIT License — see [LICENSE](LICENSE) for details.
