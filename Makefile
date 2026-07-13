.PHONY: security-check deploy-check deploy stop logs platform-build platform-local platform-stop platform-logs platform-deploy

security-check:
	python3 scripts/security_check.py

deploy-check:
	python3 scripts/deploy_check.py

deploy: security-check deploy-check
	docker compose up --build -d

stop:
	docker compose down

logs:
	docker compose logs --follow --tail=200

platform-build:
	docker compose -f compose.platform.yaml build

platform-local:
	docker compose -f compose.platform.yaml -f compose.platform.local.yaml up -d postgres redis api auth worker frontend

# Full production deployment: preflight, then build and start every service
# (including Caddy TLS termination and the analytics interface).
platform-deploy: security-check deploy-check
	docker compose -f compose.platform.yaml up --build -d

platform-stop:
	docker compose -f compose.platform.yaml -f compose.platform.local.yaml down

platform-logs:
	docker compose -f compose.platform.yaml -f compose.platform.local.yaml logs --follow --tail=200
