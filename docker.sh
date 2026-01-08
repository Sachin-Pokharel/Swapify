#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Container name
CONTAINER_NAME="fastapi_streamlit"
COMPOSE_FILE="docker-compose.yml"

# Function to print colored messages
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function to check if container exists
container_exists() {
    docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"
}

# Function to check if container is running
container_running() {
    docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"
}

# Function to start containers
start_containers() {
    print_info "Starting containers..."
    if container_running; then
        print_warning "Container ${CONTAINER_NAME} is already running"
        return 0
    fi
    
    docker-compose -f ${COMPOSE_FILE} up -d
    
    if [ $? -eq 0 ]; then
        print_success "Containers started successfully!"
        print_info "FastAPI: http://localhost:6374"
        print_info "Streamlit: http://localhost:6375"
        print_info "API Docs: http://localhost:6374/docs"
    else
        print_error "Failed to start containers"
        return 1
    fi
}

# Function to stop containers
stop_containers() {
    print_info "Stopping containers..."
    if ! container_exists; then
        print_warning "Container ${CONTAINER_NAME} does not exist"
        return 0
    fi
    
    docker-compose -f ${COMPOSE_FILE} down
    
    if [ $? -eq 0 ]; then
        print_success "Containers stopped successfully!"
    else
        print_error "Failed to stop containers"
        return 1
    fi
}

# Function to restart containers
restart_containers() {
    print_info "Restarting containers..."
    docker-compose -f ${COMPOSE_FILE} restart
    
    if [ $? -eq 0 ]; then
        print_success "Containers restarted successfully!"
    else
        print_error "Failed to restart containers"
        return 1
    fi
}

# Function to rebuild containers
rebuild_containers() {
    print_info "Rebuilding containers..."
    docker-compose -f ${COMPOSE_FILE} build --no-cache
    
    if [ $? -eq 0 ]; then
        print_success "Containers rebuilt successfully!"
        print_info "Use './docker.sh up' to start the containers"
    else
        print_error "Failed to rebuild containers"
        return 1
    fi
}

# Function to show logs
show_logs() {
    if ! container_running; then
        print_error "Container ${CONTAINER_NAME} is not running"
        return 1
    fi
    
    print_info "Showing logs (Press Ctrl+C to exit)..."
    docker-compose -f ${COMPOSE_FILE} logs -f
}

# Function to show status
show_status() {
    print_info "Container status:"
    if container_running; then
        print_success "Container ${CONTAINER_NAME} is RUNNING"
        echo ""
        docker ps --filter "name=${CONTAINER_NAME}" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    elif container_exists; then
        print_warning "Container ${CONTAINER_NAME} exists but is NOT RUNNING"
    else
        print_warning "Container ${CONTAINER_NAME} does not exist"
    fi
}

# Function to execute command in container
exec_container() {
    if ! container_running; then
        print_error "Container ${CONTAINER_NAME} is not running"
        return 1
    fi
    
    docker exec -it ${CONTAINER_NAME} "$@"
}

# Function to show help
show_help() {
    echo "Swapify Docker Helper Script"
    echo ""
    echo "Usage: ./docker.sh [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  up          Start the containers"
    echo "  down        Stop the containers"
    echo "  restart     Restart the containers"
    echo "  rebuild     Rebuild the containers (no cache)"
    echo "  logs        Show container logs (follow mode)"
    echo "  status      Show container status"
    echo "  exec        Execute command in container (e.g., ./docker.sh exec bash)"
    echo "  help        Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./docker.sh up          # Start containers"
    echo "  ./docker.sh down        # Stop containers"
    echo "  ./docker.sh restart     # Restart containers"
    echo "  ./docker.sh logs        # View logs"
    echo "  ./docker.sh exec bash   # Open bash in container"
}

# Main script logic
case "$1" in
    up|start)
        start_containers
        ;;
    down|stop)
        stop_containers
        ;;
    restart)
        restart_containers
        ;;
    rebuild|build)
        rebuild_containers
        ;;
    logs)
        show_logs
        ;;
    status|ps)
        show_status
        ;;
    exec)
        shift
        exec_container "$@"
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        if [ -z "$1" ]; then
            show_help
        else
            print_error "Unknown command: $1"
            echo ""
            show_help
            exit 1
        fi
        ;;
esac

