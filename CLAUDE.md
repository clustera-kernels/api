# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with the API kernel in this repository.

## Architecture

This is the Clustera API kernel - a FastAPI-based REST service that provides HTTP endpoints for submitting natural language queries to the Clustera platform via Kafka. The kernel includes:

1. **REST API Server**: FastAPI application with POST /query endpoint
2. **SSL-enabled Kafka Producer**: Publishes messages using base64-encoded SSL certificates from environment variables
3. **Input Validation**: Pydantic models for request/response validation
4. **Authentication Support**: Optional Bearer token authentication
5. **Health Checks**: Endpoints for monitoring API and Kafka connectivity
6. **CORS Support**: Configurable cross-origin resource sharing

The application is designed to be:
- **HTTP-first**: Provides web-accessible interface to Clustera
- **Reliable**: Confirms Kafka message delivery before responding
- **Secure**: Optional authentication and CORS configuration
- **Observable**: Health checks and structured logging
- **Deployable**: Ready for Railway, Docker, or local deployment

## Key Components

### main.py Structure
- `KERNEL_NAME = "api"` and `DEFAULT_QUERIES_TOPIC = "clustera-queries"` - Core configuration
- Pydantic models: `QueryRequest`, `QueryResponse`, `HealthResponse` - Type-safe API contracts
- `setup_kafka_producer()` - Handles SSL setup and producer configuration
- `submit_query()` - **The main API endpoint** for receiving and publishing queries
- `verify_auth()` - Optional authentication middleware
- `lifespan()` - Application startup/shutdown with Kafka producer management

### API Endpoints
- `POST /query` - Submit natural language queries to Clustera
- `GET /health` - Basic health check
- `GET /health/kafka` - Kafka connectivity check
- `GET /` - Service information and available endpoints

### Environment Configuration
All kernels require these base SSL certificates (base64-encoded):
- `KAFKA_CA_CERT`, `KAFKA_CLIENT_CERT`, `KAFKA_CLIENT_KEY`
- `KAFKA_BOOTSTRAP_SERVERS` - Kafka broker connection string

API-specific configuration:
- `KAFKA_TOPIC_QUERIES` - Topic to publish queries to (default: "clustera-queries")
- `API_HOST`, `API_PORT` - Server binding configuration
- `API_LOG_LEVEL` - Logging level
- `API_AUTH_ENABLED`, `API_AUTH_TOKEN` - Optional authentication
- `CORS_ORIGINS` - CORS configuration

## Commands

### Development Setup
```bash
# Install dependencies including FastAPI
uv sync

# Run locally
python main.py

# Run with uvicorn directly (for development)
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Testing the API
```bash
# Basic query submission
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is the weather today?"}'

# Query with metadata
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Analyze sales data",
    "metadata": {
      "user_id": "analyst_001",
      "priority": "high"
    }
  }'

# Health checks
curl http://localhost:8000/health
curl http://localhost:8000/health/kafka
```

### Production Deployment
```bash
# Build Docker image
docker build -t clustera-api-kernel .

# Run with port mapping
docker run -p 8000:8000 --env-file .env clustera-api-kernel
```

## API Implementation Details

### Request/Response Models

The API uses Pydantic models for type safety and validation:

```python
class QueryRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=10000)
    metadata: Optional[QueryMetadata] = Field(default_factory=QueryMetadata)

class QueryResponse(BaseModel):
    status: str = "published"
    query_id: str           # UUID generated for each query
    topic: str             # Kafka topic used
    timestamp: str         # ISO timestamp
```

### Kafka Message Format

Published messages have this structure:
```json
{
  "query_id": "uuid-generated-id",
  "prompt": "User's natural language prompt",
  "metadata": {
    "user_id": "optional-user-id",
    "source": "api_kernel",
    "timestamp": "2024-01-01T12:00:00Z",
    "api_version": "0.1.0",
    "custom_field": "custom_value"
  }
}
```

### Error Handling

The API implements comprehensive error handling:
- **400 Bad Request**: Invalid request format, missing prompt, validation errors
- **401 Unauthorized**: Missing or invalid authentication token
- **500 Internal Server Error**: Kafka publishing failures
- **503 Service Unavailable**: Kafka producer not available

### Authentication

Optional Bearer token authentication:
```python
async def verify_auth(credentials: HTTPAuthorizationCredentials = Depends(security)):
    auth_enabled = os.getenv("API_AUTH_ENABLED", "false").lower() == "true"
    if auth_enabled:
        # Validate Bearer token against API_AUTH_TOKEN
```

## Customization Patterns

### Adding New Endpoints

To add new endpoints to the API:

```python
@app.post("/analyze")
async def analyze_data(
    request: AnalyzeRequest,
    authenticated: bool = Depends(verify_auth)
) -> AnalyzeResponse:
    # Implement analysis logic
    # Publish to different Kafka topic if needed
    pass
```

### Custom Metadata Processing

Enhance metadata handling:

```python
class QueryMetadata(BaseModel):
    user_id: Optional[str] = None
    priority: Optional[str] = "normal"
    department: Optional[str] = None
    data_source: Optional[str] = None
    
    class Config:
        extra = "allow"  # Allow additional fields
```

### Enhanced Authentication

Implement JWT or API key authentication:

```python
from fastapi.security import HTTPBearer, APIKeyHeader
from jose import JWTError, jwt

async def verify_jwt_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=["HS256"])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

### Rate Limiting

Add rate limiting with slowapi:

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/query")
@limiter.limit("10/minute")
async def submit_query(request: Request, query: QueryRequest):
    # Implementation with rate limiting
```

## Monitoring and Observability

### Health Checks

The API provides multiple health check endpoints:

```python
@app.get("/health")           # Basic service health
@app.get("/health/kafka")     # Kafka connectivity
@app.get("/metrics")          # Prometheus metrics (if enabled)
```

### Logging

Structured logging with kernel identification:

```python
logging.info(f"[{KERNEL_NAME}] Published query {query_id} to {topic}")
```

### Metrics Collection

Add Prometheus metrics:

```python
from prometheus_client import Counter, Histogram, generate_latest

QUERY_COUNTER = Counter('queries_total', 'Total queries processed')
QUERY_DURATION = Histogram('query_duration_seconds', 'Query processing time')

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type="text/plain")
```

## Integration Patterns

### Frontend Integration

JavaScript/TypeScript integration:

```typescript
interface QueryRequest {
  prompt: string;
  metadata?: {
    user_id?: string;
    priority?: string;
    [key: string]: any;
  };
}

async function submitQuery(query: QueryRequest): Promise<QueryResponse> {
  const response = await fetch('/query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(query)
  });
  
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  
  return response.json();
}
```

### Backend Integration

Python client integration:

```python
import httpx

async def submit_clustera_query(prompt: str, metadata: dict = None):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://your-api.railway.app/query",
            json={"prompt": prompt, "metadata": metadata or {}},
            headers={"Authorization": f"Bearer {API_TOKEN}"}
        )
        response.raise_for_status()
        return response.json()
```

## Deployment Configurations

### Railway Deployment

Environment variables in Railway:
```
KAFKA_BOOTSTRAP_SERVERS=your-kafka:9092
KAFKA_CA_CERT=base64-encoded-cert
KAFKA_CLIENT_CERT=base64-encoded-cert
KAFKA_CLIENT_KEY=base64-encoded-key
KAFKA_TOPIC_QUERIES=clustera-queries
API_AUTH_ENABLED=true
API_AUTH_TOKEN=secure-random-token
CORS_ORIGINS=https://yourapp.com
```

### Docker Compose

```yaml
version: '3.8'
services:
  api-kernel:
    build: .
    ports:
      - "8000:8000"
    environment:
      - KAFKA_BOOTSTRAP_SERVERS=kafka:9092
      - KAFKA_TOPIC_QUERIES=clustera-queries
      - API_AUTH_ENABLED=false
    depends_on:
      - kafka
```

### Local Development

```bash
# Create .env file with required variables
cat > .env << EOF
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_CA_CERT=base64-cert-here
KAFKA_CLIENT_CERT=base64-cert-here
KAFKA_CLIENT_KEY=base64-key-here
KAFKA_TOPIC_QUERIES=clustera-queries
API_HOST=0.0.0.0
API_PORT=8000
API_LOG_LEVEL=debug
EOF

# Run with auto-reload
uv run uvicorn main:app --reload
```

## Security Best Practices

1. **Always use HTTPS in production**
2. **Enable authentication for production deployments**
3. **Configure CORS appropriately for your domains**
4. **Use strong, unique API tokens**
5. **Implement rate limiting for public APIs**
6. **Validate and sanitize all input**
7. **Never log sensitive data**
8. **Keep SSL certificates secure**

## Testing Strategy

1. **Unit Tests**: Test individual endpoint functions
2. **Integration Tests**: Test with real Kafka setup
3. **API Tests**: Test HTTP endpoints with various inputs
4. **Load Tests**: Verify performance under load
5. **Security Tests**: Test authentication and authorization

Remember to update this file when you extend the API with additional endpoints or functionality!