.PHONY: help setup start stop restart logs clean test test-watch lint format check-env

# Colors
GREEN  := $(shell tput -Txterm setaf 2)
YELLOW := $(shell tput -Txterm setaf 3)
WHITE  := $(shell tput -Txterm setaf 7)
RESET  := $(shell tput -Txterm sgr0)

help: ## Show this help
	@echo '\nUsage: make ${YELLOW}<target>${RESET}\n\nTargets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  ${YELLOW}%-15s${RESET} %s\n", $$1, $$2}' $(MAKEFILE_LIST)

##@ Environment

setup: ## Copy .env.example to .env if it doesn't exist
	@if [ ! -f .env ]; then \
		cp env.example .env; \
		echo "${GREEN}Created .env file. Please update it with your API credentials.${RESET}"; \
	else \
		echo "${YELLOW}.env file already exists${RESET}"; \
	fi

##@ Docker Compose

start: check-env ## Start all services
	@echo "${GREEN}Starting LLMOps environment...${RESET}"
	docker-compose up -d --build
	@echo "\n${GREEN}Services started successfully!${RESET}"
	@echo "- API: http://localhost:8000"
	@echo "- LiteLLM: http://localhost:8001"
	@echo "- MLflow UI: http://localhost:5000"

stop: ## Stop all services
	@echo "${YELLOW}Stopping LLMOps environment...${RESET}"
	docker-compose stop

restart: stop start ## Restart all services

logs: ## View logs from all services
	@echo "${YELLOW}Viewing logs (press Ctrl+C to exit)...${RESET}"
	docker-compose logs -f

clean: ## Stop services and remove containers, volumes, and networks
	@echo "${YELLOW}Cleaning up LLMOps environment...${RESET}"
	docker-compose down -v --remove-orphans

##@ Testing

test: check-env ## Run integration tests
	@echo "${GREEN}Running integration tests...${RESET}"
	docker-compose exec api pytest /app/tests/ -v --cov=app --cov-report=term-missing

test-watch: check-env ## Run tests in watch mode
	@echo "${GREEN}Starting test watcher...${RESET}"
	docker-compose exec api ptw /app/tests/ -- -v --cov=app --cov-report=term-missing

##@ Code Quality

lint: ## Run code linter
	@echo "${GREEN}Running code linter...${RESET}"
	docker-compose exec api flake8 /app/src

format: ## Format code with black and isort
	@echo "${GREEN}Formatting code...${RESET}"
	docker-compose exec api black /app/src
	docker-compose exec api isort /app/src

##@ Utils

check-env:
	@if [ ! -f .env ]; then \
		echo "${YELLOW}Error: .env file not found. Run 'make setup' first.${RESET}" >&2; \
		exit 1; \
	fi

##@ Dependencies

install-test-deps: ## Install test dependencies
	@echo "${GREEN}Installing test dependencies...${RESET}"
	pip install -r test-requirements.txt

##@ Documentation

docs: ## Generate API documentation
	@echo "${GREEN}Generating API documentation...${RESET}"
	docker-compose exec api python -m pdoc --html -o /app/docs /app/src/api --force

##@ Monitoring

mlflow: check-env ## Open MLflow UI in browser
	@open http://localhost:5001

##@ API Examples

api-test: check-env ## Test API health check
	@echo "${GREEN}Testing API health check...${RESET}"
	@curl -s http://localhost:8000/health | jq

api-models: check-env ## List available models
	@echo "${GREEN}Fetching available models...${RESET}"
	@curl -s http://localhost:8000/models | jq

api-generate: check-env ## Generate text with default model (prompt required: make api-generate PROMPT="your prompt")
	@if [ -z "$(PROMPT)" ]; then \
		echo "${YELLOW}Error: PROMPT is required. Usage: make api-generate PROMPT=\"your prompt\"${RESET}" >&2; \
		exit 1; \
	fi
	@echo "${GREEN}Generating text with prompt: $(PROMPT)${RESET}"
	@curl -s -X POST http://localhost:8000/generate \
		-H "Content-Type: application/json" \
		-d '{"prompt": "$(PROMPT)", "model": "groq-kimi-primary"}' | jq

api-generate-gemini: check-env ## Generate text with Gemini model (prompt required: make api-generate-gemini PROMPT="your prompt")
	@if [ -z "$(PROMPT)" ]; then \
		echo "${YELLOW}Error: PROMPT is required. Usage: make api-generate-gemini PROMPT=\"your prompt\"${RESET}" >&2; \
		exit 1; \
	fi
	@echo "${GREEN}Generating text with Gemini: $(PROMPT)${RESET}"
	@curl -s -X POST http://localhost:8000/generate \
		-H "Content-Type: application/json" \
		-d '{"prompt": "$(PROMPT)", "model": "gemini-third"}' | jq

api-generate-groq: check-env ## Generate text with Groq model (prompt required: make api-generate-groq PROMPT="your prompt")
	@if [ -z "$(PROMPT)" ]; then \
		echo "${YELLOW}Error: PROMPT is required. Usage: make api-generate-groq PROMPT=\"your prompt\"${RESET}" >&2; \
		exit 1; \
	fi
	@echo "${GREEN}Generating text with Groq: $(PROMPT)${RESET}"
	@curl -s -X POST http://localhost:8000/generate \
		-H "Content-Type: application/json" \
		-d '{"prompt": "$(PROMPT)", "model": "groq-kimi-primary"}' | jq

api-generate-openai: check-env ## Generate text with OpenAI model (prompt required: make api-generate-openai PROMPT="your prompt")
	@if [ -z "$(PROMPT)" ]; then \
		echo "${YELLOW}Error: PROMPT is required. Usage: make api-generate-openai PROMPT=\"your prompt\"${RESET}" >&2; \
		exit 1; \
	fi
	@echo "${GREEN}Generating text with OpenAI: $(PROMPT)${RESET}"
	@curl -s -X POST http://localhost:8000/generate \
		-H "Content-Type: application/json" \
		-d '{"prompt": "$(PROMPT)", "model": "gpt-4o-secondary"}' | jq

api-generate-openrouter: check-env ## Generate text with OpenRouter model (prompt required: make api-generate-openrouter PROMPT="your prompt")
	@if [ -z "$(PROMPT)" ]; then \
		echo "${YELLOW}Error: PROMPT is required. Usage: make api-generate-openrouter PROMPT=\"your prompt\"${RESET}" >&2; \
		exit 1; \
	fi
	@echo "${GREEN}Generating text with OpenRouter: $(PROMPT)${RESET}"
	@curl -s -X POST http://localhost:8000/generate \
		-H "Content-Type: application/json" \
		-d '{"prompt": "$(PROMPT)", "model": "openrouter-fallback"}' | jq
##@ Helpers

.DEFAULT_GOAL := help
