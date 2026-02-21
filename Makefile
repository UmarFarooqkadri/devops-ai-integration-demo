.PHONY: help install lint test docker-build docker-push tf-init tf-plan tf-apply k8s-deploy k8s-status run-agent clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies
	pip install -r requirements.txt

lint: ## Run linter
	ruff check src/ --fix
	ruff format src/

test: ## Run tests with coverage
	pytest tests/ -v --cov=src --cov-report=term-missing

docker-build: ## Build Docker image
	docker build -t devops-ai-platform:latest .

docker-push: ## Push to GitHub Container Registry
	docker tag devops-ai-platform:latest ghcr.io/umarfarooqkadri/devops-ai-platform:latest
	docker push ghcr.io/umarfarooqkadri/devops-ai-platform:latest

tf-init: ## Initialize Terraform
	cd terraform && terraform init

tf-plan: ## Plan Terraform changes
	cd terraform && terraform plan -out=tfplan

tf-apply: ## Apply Terraform changes
	cd terraform && terraform apply tfplan

k8s-deploy: ## Deploy to Kubernetes
	kubectl apply -f k8s/namespace.yaml
	kubectl apply -f k8s/configmap.yaml
	kubectl apply -f k8s/deployment.yaml
	kubectl apply -f k8s/service.yaml
	kubectl apply -f k8s/hpa.yaml

k8s-status: ## Check Kubernetes deployment status
	kubectl -n devops-ai get pods,svc,hpa

run-agent: ## Run the platform locally
	uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

clean: ## Clean build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache htmlcov .coverage dist *.egg-info
	cd terraform && rm -rf .terraform *.tfplan *.tfstate* 2>/dev/null || true
