.PHONY: token

token:
	docker compose exec app app create-token
