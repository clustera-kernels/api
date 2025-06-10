# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture

This is a template for creating Clustera kernels - Kafka consumer applications that provide specific functionality to the Clustera platform. The template includes:

1. **SSL-enabled Kafka Consumer**: Connects using base64-encoded SSL certificates from environment variables
2. **Configurable Processing**: The `process_message()` function can be customized for any kernel logic
3. **Robust Error Handling**: Proper logging, partition management, and manual offset commits
4. **Flexible Configuration**: Environment-based configuration for topic, consumer group, and kernel-specific settings

The application is designed to be:
- **Single-purpose**: Each kernel handles one specific type of functionality
- **Reliable**: Manual offset commits ensure messages aren't lost
- **Observable**: Comprehensive logging with kernel-specific prefixes
- **Deployable**: Ready for Railway, Docker, or local deployment

## Key Components

### main.py Structure
- `KERNEL_NAME` and `DEFAULT_TOPIC` - Configure at the top for your specific kernel
- `process_message(message)` - **The main function to customize** for your kernel's logic
- `setup_kafka_consumer()` - Handles SSL setup and consumer configuration
- `KernelPartitionListener` - Manages Kafka partition assignment and rebalancing
- `main()` - Main execution loop with proper error handling and cleanup

### Environment Configuration
All kernels require these base SSL certificates (base64-encoded):
- `KAFKA_CA_CERT`, `KAFKA_CLIENT_CERT`, `KAFKA_CLIENT_KEY`
- `KAFKA_BOOTSTRAP_SERVERS` - Kafka broker connection string

Optional kernel configuration:
- `KAFKA_TOPIC` - Override default topic
- `KAFKA_CLIENT_ID`, `KAFKA_CONSUMER_GROUP` - Override defaults
- Add kernel-specific variables as needed

## Commands

### Initial Setup (for new kernels)
```bash
# 1. Update kernel configuration in main.py
# Change KERNEL_NAME = "your-kernel-name"
# Change DEFAULT_TOPIC = "your-topic-name"

# 2. Copy environment template and configure
cp .env.template .env

# 3. Install base dependencies
uv sync

# 4. Add kernel-specific dependencies
uv add --optional database  # For database kernels
uv add --optional http      # For HTTP/API kernels
uv add --optional ai        # For AI/ML kernels
```

### Development Workflow
```bash
# Run locally during development
python main.py

# Run with uv (recommended)
uv run python main.py

# Build and test with Docker
docker build -t your-kernel .
docker run --env-file .env your-kernel
```

## Customization Guide

### 1. Basic Configuration
Update these constants in `main.py`:
```python
KERNEL_NAME = "your-kernel-name"     # Used in logging and consumer defaults
DEFAULT_TOPIC = "your-topic-name"    # Default Kafka topic to consume from
```

### 2. Core Processing Logic
The main function to implement is `process_message(message)`:

```python
def process_message(message):
    """
    Process a single Kafka message for your specific kernel.
    
    Args:
        message: Kafka message with .key, .value, .offset, .partition, .timestamp
    
    Returns:
        bool: True if processing succeeded, False if retriable error occurred
        
    Raises:
        Exception: For fatal errors that should stop the kernel
    """
    # 1. Extract and validate message data
    try:
        data = json.loads(message.value.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logging.error(f"Invalid message format: {e}")
        return False  # Skip this message
    
    # 2. Implement your kernel's specific logic
    try:
        # Example patterns:
        # - Store to database: store_memory(data)
        # - Call external API: send_notification(data)
        # - Transform data: enriched = enrich_event(data)
        # - Update metrics: update_analytics(data)
        
        return True
    except RetriableError as e:
        logging.warning(f"Retriable error: {e}")
        return False  # Will retry this message
    except FatalError as e:
        logging.error(f"Fatal error: {e}")
        raise  # Will stop the kernel
```

### 3. Dependencies and Environment
```python
# Add to pyproject.toml dependencies as needed
# Add environment variables for your kernel:

database_url = os.getenv("DATABASE_URL")
api_key = os.getenv("API_KEY") 
model_name = os.getenv("MODEL_NAME", "default-model")
batch_size = int(os.getenv("BATCH_SIZE", "100"))
```

### 4. Error Handling Strategies
- **Return False**: For retriable errors (network timeouts, temporary API issues)
- **Raise Exceptions**: For fatal errors that should stop the kernel
- **Skip Messages**: For permanently invalid/malformed messages
- **Implement Retry Logic**: With exponential backoff for external services

## Common Kernel Patterns

### Database Kernel
```python
def process_message(message):
    """Store structured data in PostgreSQL"""
    data = json.loads(message.value.decode('utf-8'))
    
    with get_db_connection() as conn:
        conn.execute(
            "INSERT INTO events (id, data, created_at) VALUES (%s, %s, %s)",
            (data['id'], json.dumps(data), datetime.utcnow())
        )
        conn.commit()
    return True
```

### API Integration Kernel
```python
def process_message(message):
    """Forward events to external API"""
    data = json.loads(message.value.decode('utf-8'))
    
    response = httpx.post(
        f"{API_BASE_URL}/events",
        json=data,
        headers={"Authorization": f"Bearer {API_KEY}"},
        timeout=30
    )
    
    if response.status_code >= 500:
        return False  # Retry on server errors
    elif response.status_code >= 400:
        logging.warning(f"Client error {response.status_code}: {response.text}")
        return True  # Skip on client errors
    
    return True
```

### AI Processing Kernel
```python
def process_message(message):
    """Process text with AI model"""
    data = json.loads(message.value.decode('utf-8'))
    
    try:
        result = ai_client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": data['text']}]
        )
        
        processed_data = {
            "original_id": data['id'],
            "result": result.choices[0].message.content,
            "model": MODEL_NAME,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Store or forward the result
        store_result(processed_data)
        
    except Exception as e:
        if "rate_limit" in str(e).lower():
            return False  # Retry rate limit errors
        raise  # Fatal for other errors
    
    return True
```

## Deployment Notes

### Railway Deployment
- Set all environment variables in Railway dashboard
- Kernel will auto-restart on failures
- Monitor logs through Railway interface

### Docker Deployment
- All certificates handled via environment variables
- No persistent storage needed for base template
- Scale horizontally by running multiple instances

### Local Development
- Use `.env` file for configuration
- Test with sample messages in your Kafka topic
- Monitor consumer lag to ensure processing keeps up

## Monitoring and Observability

The template includes comprehensive logging with kernel-specific prefixes:
- Partition assignment/revocation events
- Message processing status and timing
- Error details with context
- Consumer lag and position tracking

Add custom metrics for your kernel:
```python
import time

def process_message(message):
    start_time = time.time()
    
    # Your processing logic
    success = do_processing(message)
    
    processing_time = time.time() - start_time
    logging.info(f"[{KERNEL_NAME}] Processed in {processing_time:.2f}s")
    
    return success
```

## Testing Strategy

1. **Unit Tests**: Test `process_message()` with mock messages
2. **Integration Tests**: Test with real Kafka setup
3. **Error Scenarios**: Test network failures, malformed messages
4. **Performance Tests**: Measure throughput and latency
5. **Deployment Tests**: Verify in target environment

Remember to update this file when you customize the kernel with specific implementation details!