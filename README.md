# Clustera API Kernel

A Clustera kernel that provides a REST API endpoint for submitting natural language queries to the Clustera platform via Kafka.

## What is the API Kernel?

The API kernel is a specialized Clustera module that:
- Exposes a REST API with a `POST /query` endpoint
- Receives natural language prompts via HTTP requests
- Publishes queries to a configurable Kafka topic
- Returns confirmation once messages are successfully published
- Provides an HTTP interface to the Clustera platform

This kernel serves as the entry point for external applications to submit queries to Clustera for processing by other kernels.

## API Specification

### POST /query

Submit a natural language query to the Clustera platform.

**Request:**
```json
{
  "prompt": "What is the weather like today?",
  "metadata": {
    "user_id": "user123",
    "source": "web_app"
  }
}
```

**Response (201 Created):**
```json
{
  "status": "published",
  "query_id": "uuid-generated-id",
  "topic": "clustera-queries",
  "timestamp": "2024-01-01T12:00:00Z"
}
```

**Error Responses:**
- `400 Bad Request`: Invalid request format or missing prompt
- `500 Internal Server Error`: Kafka publishing failure
- `503 Service Unavailable`: Kafka connection issues

## Quick Start

### 1. Environment Setup

```bash
# Install dependencies
uv sync

# Install HTTP dependencies for the API kernel
uv add --optional http
```

### 2. Configure Environment Variables

Edit `.env` and set:

```env
# Kafka Configuration (required)
KAFKA_BOOTSTRAP_SERVERS=your-kafka-brokers
KAFKA_CA_CERT=base64-encoded-ca-certificate
KAFKA_CLIENT_CERT=base64-encoded-client-certificate
KAFKA_CLIENT_KEY=base64-encoded-client-private-key

# API Kernel Configuration
KAFKA_TOPIC_QUERIES=clustera-queries          # Topic to publish queries to
API_HOST=0.0.0.0                              # API server host
API_PORT=8000                                 # API server port
API_LOG_LEVEL=info                            # Logging level

# Optional: Authentication and security
API_AUTH_ENABLED=false                        # Enable API authentication
API_AUTH_TOKEN=your-secret-token              # Required if auth enabled
CORS_ORIGINS=*                                # CORS allowed origins
```

### 3. Run the API Kernel

```bash
# Run locally
python main.py

# Run with uv
uv run python main.py

# Run with Docker
docker build -t clustera-api-kernel .
docker run -p 8000:8000 --env-file .env clustera-api-kernel
```

The API will be available at `http://localhost:8000`

### 4. Test the API

```bash
# Submit a query
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is the current time?"}'

# With metadata
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Analyze this data",
    "metadata": {
      "user_id": "user123",
      "priority": "high"
    }
  }'
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `KAFKA_BOOTSTRAP_SERVERS` | - | Kafka broker connection string (required) |
| `KAFKA_CA_CERT` | - | Base64-encoded CA certificate (required) |
| `KAFKA_CLIENT_CERT` | - | Base64-encoded client certificate (required) |
| `KAFKA_CLIENT_KEY` | - | Base64-encoded client private key (required) |
| `KAFKA_TOPIC_QUERIES` | `clustera-queries` | Topic to publish queries to |
| `API_HOST` | `0.0.0.0` | API server host |
| `API_PORT` | `8000` | API server port |
| `API_LOG_LEVEL` | `info` | Logging level (debug, info, warning, error) |
| `API_AUTH_ENABLED` | `false` | Enable API authentication |
| `API_AUTH_TOKEN` | - | Authentication token (if auth enabled) |
| `CORS_ORIGINS` | `*` | CORS allowed origins |

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
    "custom_field": "custom_value"
  }
}
```

## Project Structure

```
api-kernel/
├── main.py              # FastAPI application and Kafka producer
├── pyproject.toml       # Python project configuration
├── Dockerfile           # Container configuration
├── README.md            # This file
├── CLAUDE.md            # AI assistant guidance
├── .env.template        # Environment variable template
├── .env                 # Your environment variables (not in git)
└── .gitignore          # Git ignore patterns
```

## Deployment

### Railway (Recommended)

1. Connect your repository to Railway
2. Set environment variables in Railway dashboard
3. Railway will automatically expose the service on HTTPS
4. Use the provided URL to access your API

### Docker

```bash
# Build image
docker build -t clustera-api-kernel .

# Run container with port mapping
docker run -p 8000:8000 --env-file .env clustera-api-kernel
```

### Local Development

```bash
# Install with HTTP dependencies
uv sync
uv add --optional http

# Run with auto-reload
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## API Usage Examples

### Basic Query Submission

```python
import httpx

# Submit a simple query
response = httpx.post(
    "http://localhost:8000/query",
    json={"prompt": "What is machine learning?"}
)

if response.status_code == 201:
    result = response.json()
    print(f"Query {result['query_id']} published successfully")
```

### Query with Metadata

```python
import httpx

# Submit a query with metadata
response = httpx.post(
    "http://localhost:8000/query",
    json={
        "prompt": "Generate a summary of our sales data",
        "metadata": {
            "user_id": "analyst_001",
            "department": "sales",
            "priority": "high",
            "data_source": "salesforce"
        }
    }
)
```

### JavaScript/Frontend Integration

```javascript
// Submit query from web application
async function submitQuery(prompt, metadata = {}) {
  try {
    const response = await fetch('/query', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ prompt, metadata })
    });
    
    if (response.ok) {
      const result = await response.json();
      console.log('Query submitted:', result.query_id);
      return result;
    } else {
      throw new Error(`HTTP ${response.status}`);
    }
  } catch (error) {
    console.error('Failed to submit query:', error);
  }
}
```

## Health Checks and Monitoring

The API includes health check endpoints:

- `GET /health` - Basic health check
- `GET /health/kafka` - Kafka connectivity check
- `GET /metrics` - Prometheus-compatible metrics (if enabled)

## Security Considerations

1. **Authentication**: Enable `API_AUTH_ENABLED` and set `API_AUTH_TOKEN` for production
2. **CORS**: Configure `CORS_ORIGINS` appropriately for your frontend domains
3. **Rate Limiting**: Consider implementing rate limiting for production use
4. **Input Validation**: All prompts are validated and sanitized
5. **SSL/TLS**: Use HTTPS in production (handled by Railway/reverse proxy)

## Troubleshooting

### Common Issues

**API not responding:**
- Check if port 8000 is available
- Verify `API_HOST` and `API_PORT` settings
- Check firewall and network configuration

**Kafka publishing failures:**
- Verify Kafka SSL certificates are correct
- Check `KAFKA_BOOTSTRAP_SERVERS` connectivity
- Ensure topic `KAFKA_TOPIC_QUERIES` exists
- Verify Kafka permissions for your client

**Authentication errors:**
- Check `API_AUTH_TOKEN` if authentication is enabled
- Verify token is included in request headers

### Debug Mode

Run with debug logging for troubleshooting:

```bash
API_LOG_LEVEL=debug uv run python main.py
```

## Integration with Other Kernels

The API kernel works with other Clustera kernels:

1. **Query Processing Kernel**: Consumes from `clustera-queries` topic
2. **Memory Kernel**: Stores query history and context
3. **Analytics Kernel**: Tracks query patterns and usage
4. **Response Kernel**: Publishes responses back to users

## Contributing

1. Fork this repository
2. Create a feature branch
3. Implement your changes
4. Add tests for new functionality
5. Update documentation
6. Submit a pull request

## License

[Your License Here]