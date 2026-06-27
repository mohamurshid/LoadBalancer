.PHONY: build up down logs clean

# Build both docker images (server replicas are spawned later by the load balancer)
build:
	docker build -t server_image:latest ./server
	docker-compose build

# Bring the whole stack up (creates net1 network + load balancer container,
# which then spawns N server containers itself)
up: build
	docker-compose up -d

# Stop everything: load balancer + any server containers it spawned
down:
	docker-compose down
	-docker ps -a --filter "network=net1" --format "{{.Names}}" | grep -v loadbalancer | xargs -r docker rm -f

# Tail load balancer logs
logs:
	docker-compose logs -f loadbalancer

# Full cleanup: stop containers, remove images and network
clean: down
	-docker rmi server_image:latest loadbalancer_image:latest
	-docker network rm net1
