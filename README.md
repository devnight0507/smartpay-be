
## Features

- **FastAPI v0.95+** - Modern, high-performance async web framework with automatic OpenAPI documentation
- **Async SQLAlchemy 2.0** - Type-annotated ORM with async PostgreSQL support for efficient database access
- **Pydantic v2** - Data validation and settings management using Python type annotations
- **Alembic** - Database migrations with a clear workflow and version control
- **WebSockets** - Real-time bi-directional communication with connection management
- **Structured Logging** - Configurable JSON logging with context propagation using Loguru
- **Docker Multi-stage Builds** - Optimized container images for deployment
- **GitHub Actions CI/CD** - Automated testing, building, and deployment pipeline
- **Comprehensive Testing** - Pytest setup with fixtures for async testing
- **Dependency Injection** - Clean, testable dependency management

## Getting Started

### Prerequisites

- Python 3.11+
- Poetry for dependency management
- Docker and Docker Compose for local development
- Kubernetes for deployment (optional)

### Installation

1. Clone this repository:

```bash
git clone https://github.com/devnight0507/smartpay-be
cd smartpay-be
```

2. Set up the development environment:

```bash
make dev-setup   # Creates required directories and copies .env.example to .env
```

3. Edit the `.env` file to configure your environment

4. Start the development environment with Docker Compose:

```bash
make dev-up      # Starts all containers with hot reload
```

5. Run database migrations:

```bash
make migrate     # Applies all migrations
```

The API is now running at http://localhost:8000 with hot reload enabled. Changes to the code will automatically restart the server.

### Development Services

The following services are available in the development environment:

| Service    | URL                            | Description                               |
| ---------- | ------------------------------ | ----------------------------------------- |
| API        | http://localhost:8000          | FastAPI application with hot reload       |
| API Docs   | http://localhost:8000/api/docs | Swagger UI API documentation              |
| PgAdmin    | http://localhost:5050          | PostgreSQL administration interface       |

Login credentials for services:

- **Grafana**: admin / admin
- **PgAdmin**: admin@example.com / admin

### Useful Development Commands

```bash
# Start all containers
make dev-up

# View logs from containers
make logs
# or for a specific service
make logs S=api

# Stop all containers
make dev-down

# Restart containers
make dev-restart

# Create a new migration
make migrations M="description of changes"

# Apply migrations
make migrate

# Rollback last migration
make migrate-down

# Run tests in Docker
make test
# or a specific test
make test T=tests/api/test_health.py

# Format code
make format

# Run linters
make lint

# Get a shell in the API container
make shell
```

Access the API documentation at http://localhost:8000/api/docs

## Code Quality and Type Checking

The project uses pre-commit hooks to ensure code quality and prevent type errors.

### Pre-commit Hooks

The template includes pre-commit hooks for:

- **black**: Code formatting
- **isort**: Import sorting
- **flake8**: Code style and quality checks
- **mypy**: Static type checking
- **trailing-whitespace**: Remove trailing whitespace
- **end-of-file-fixer**: Ensure files end with a newline
- **check-yaml**: Validate YAML files
- **check-added-large-files**: Prevent large files from being committed

### Setting Up Pre-commit

1. Install pre-commit in your virtual environment:

```bash
poetry install
```

2. Install the pre-commit hooks:

```bash
poetry run pre-commit install
```

Now, whenever you commit changes, the pre-commit hooks will automatically run to check your code quality and types.

### Manual Hook Execution

You can manually run all pre-commit hooks on all files:

```bash
poetry run pre-commit run --all-files
```

Or run a specific hook:

```bash
poetry run pre-commit run mypy --all-files
```

### Type Checking

The mypy hook enforces strict type checking with the following settings:

- `--disallow-untyped-defs`: All functions must have type annotations
- `--disallow-incomplete-defs`: All function arguments must have type annotations
- `--ignore-missing-imports`: Ignore missing imports for third-party libraries

Additional mypy configurations are in `pyproject.toml` under `[tool.mypy]`.

## API Documentation

The API documentation is automatically generated from route decorators and available at:

- Swagger UI: `/api/docs`
- ReDoc: `/api/redoc`
- OpenAPI JSON: `/api/openapi.json`

### Route-Based Documentation

The template uses FastAPI's route decorators to generate comprehensive API documentation:

```python
@router.get(
    "/job",
    response_model=JobReadDTO,
    summary="Query the oldest Job Queue Record",
    response_description="A Job Queue record matching agent's Subscription ID",
    responses={
        HTTP_200_OK: {
            "model": JobReadDTO,
            "description": ResponseMessage("RecordRetrieved", {"record": "Job"}).description,
        },
        HTTP_403_FORBIDDEN: {
            "model": Union[JWTMalformedForbiddenModel, InvalidAuthCredForbiddenModel],
            "description": "Detailed error description...",
        },
        # Other response codes...
    },
    tags=["Job Consumer"],
)
async def get_open_job(...):
    """Detailed function docstring that appears in Swagger."""
    # Implementation
```

### Standardized Response Models

The template includes a comprehensive set of standardized response models in `app/api/responses.py` that you can use to ensure consistent API documentation and responses:

- `ResponseMessage` for generating consistent response messages
- Standard error models for common error cases
- HTTP status code constants
- Tag definitions for endpoint categorization


You can add more languages by extending the `TRANSLATIONS` dictionary in `app/api/i18n.py`.

## Configuration

The application is configured using environment variables. All settings are defined in `app/core/config.py` and can be overridden by environment variables.

### Key Configuration Parameters

| Variable                  | Description                                         | Default               |
| ------------------------- | --------------------------------------------------- | --------------------- |
| `ENVIRONMENT`             | Environment name (development, staging, production) | `development`         |
| `DEBUG`                   | Enable debug mode                                   | `True` in development |
| `SECRET_KEY`              | Secret key for security                             | Required              |
| `POSTGRES_*`              | Database connection parameters                      | Required              |
| `LOG_LEVEL`               | Minimum log level                                   | `INFO`                |

## Database Migrations

Database migrations are managed with Alembic:

```bash
# Create a new migration
alembic revision --autogenerate -m "description"

# Run migrations
alembic upgrade head

# Rollback one version
alembic downgrade -1
```

## WebSockets

The template includes a fully-featured WebSocket implementation:

```python
# Connect to WebSocket
ws_url = "ws://localhost:8000/api/v1/ws/connect"
async with websocket_connect(ws_url) as websocket:
    # Subscribe to a topic
    await websocket.send_json({
        "type": "subscribe",
        "data": {"topic": "notifications"}
    })

    # Receive messages
    async for message in websocket:
        data = json.loads(message)
        print(f"Received: {data}")
```

Send notifications to WebSocket clients:

```bash
curl -X POST "http://localhost:8000/api/v1/ws/broadcast" \
     -H "Authorization: Bearer <token>" \
     -H "Content-Type: application/json" \
     -d '{"message": "Hello WebSocket clients", "topic": "notifications"}'
```

### Logging

Structured logging is configured using Loguru with JSON format by default:

```python
from loguru import logger

logger.info("User registered", extra={"user_id": user_id, "trace_id": trace_id})
```

## Testing

The template includes a complete test suite setup with pytest:

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=app --cov-report=term-missing

# Run specific test file
pytest tests/api/test_items.py

# Run tests in parallel
pytest -xvs -n auto
```

## Docker

Build the Docker image:

```bash
docker build -t smartpay-be:latest -f docker/Dockerfile .
```

Run the container:

```bash
docker run -p 8000:8000 --env-file .env smartpay-be:latest
```

## CI/CD

The template includes a GitHub Actions workflow for CI/CD:

### GitHub Actions

- Linting and type checking
- Running tests with coverage

## Troubleshooting

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/my-feature`
3. Commit your changes: `git commit -am 'Add my feature'`
4. Push to the branch: `git push origin feat/my-feature`
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details

## Release Deployment Test
```
002
```
