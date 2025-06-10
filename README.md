# Clustera Kernel Template

A template for creating new Clustera kernels - Python Kafka consumers that provide specific functionality to the Clustera platform.

## What is a Clustera Kernel?

A Clustera kernel is a module of functionality that:
- Consumes messages from Kafka topics
- Processes messages according to specific business logic
- Integrates with databases, APIs, or other services
- Provides capabilities like memory, analytics, notifications, etc.

This template provides a robust foundation with:
- SSL-enabled Kafka consumer setup
- Proper error handling and logging
- Partition management and rebalancing
- Manual offset commits for reliability
- Configurable processing logic

## Quick Start

### 1. Clone and Customize

```bash
# Clone this template
git clone <your-template-repo> my-new-kernel
cd my-new-kernel

# Update the kernel configuration in main.py
# Change KERNEL_NAME and DEFAULT_TOPIC at the top of main.py
```

### 2. Environment Setup

```bash
# Copy the environment template
cp .env.template .env

# Install dependencies
uv sync

# Optional: Install additional dependencies for your kernel type
uv add --optional database  # For database kernels
uv add --optional http      # For HTTP/API kernels  
uv add --optional ai        # For AI/ML kernels
```

### 3. Configure Environment Variables

Edit `.env` and set:

```env
# Kafka Configuration (required)
KAFKA_BOOTSTRAP_SERVERS=your-kafka-brokers
KAFKA_CA_CERT=base64-encoded-ca-certificate
KAFKA_CLIENT_CERT=base64-encoded-client-certificate
KAFKA_CLIENT_KEY=base64-encoded-client-private-key

# Kernel Configuration (optional)
KAFKA_TOPIC=your-topic-name                    # Defaults to clustera-hello-world
KAFKA_CLIENT_ID=your-client-id                 # Defaults to {kernel-name}-consumer-{pid}
KAFKA_CONSUMER_GROUP=your-consumer-group       # Defaults to {kernel-name}-group

# Add your kernel-specific environment variables here
DATABASE_URL=postgresql://...                  # If using database
API_KEY=your-api-key                          # If using external APIs
```

### 4. Implement Your Logic

The main function you'll customize is `process_message()` in `main.py`:

```python
def process_message(message):
    """
    Process a single Kafka message.
    
    Replace the hello-world logic with your kernel's specific functionality.
    """
    # Your kernel logic here
    # Examples:
    # - Parse message and store in database
    # - Call external APIs
    # - Transform and forward to another topic
    # - Update in-memory state
    
    return True  # Return False if processing failed
```

### 5. Run Your Kernel

```bash
# Run locally
python main.py

# Run with uv
uv run python main.py

# Run with Docker
docker build -t my-kernel .
docker run --env-file .env my-kernel
```

## Customization Guide

### Kernel Configuration

Update these constants in `main.py`:

```python
KERNEL_NAME = "your-kernel-name"        # Used in logging and defaults
DEFAULT_TOPIC = "your-default-topic"    # Default Kafka topic to consume
```

### Processing Logic

The `process_message(message)` function receives Kafka messages with these attributes:
- `message.key` - Message key (bytes or None)
- `message.value` - Message value (bytes or None) 
- `message.offset` - Message offset in partition
- `message.partition` - Partition number
- `message.timestamp` - Message timestamp
- `message.headers` - Message headers (list of tuples)

### Error Handling

Customize error handling in the main loop:
- Return `False` from `process_message()` for retriable errors
- Raise exceptions for fatal errors
- Implement retry logic, dead letter queues, or circuit breakers as needed

### Dependencies

Add kernel-specific dependencies:

```bash
# Database kernels
uv add --optional database

# HTTP/API kernels  
uv add --optional http

# AI/ML kernels
uv add --optional ai

# Or add specific packages
uv add requests numpy pandas
```

### Environment Variables

Add kernel-specific environment variables and update the `.env.template`:

```python
# In your code
database_url = os.getenv("DATABASE_URL")
api_key = os.getenv("API_KEY")
model_name = os.getenv("MODEL_NAME", "default-model")
```

## Project Structure

```
your-kernel/
├── main.py              # Main kernel application
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
3. Deploy automatically on git push

### Docker

```bash
# Build image
docker build -t your-kernel .

# Run container
docker run --env-file .env your-kernel
```

### Local Development

```bash
# Install in development mode
uv sync --dev

# Run with auto-reload (if you add file watching)
uv run python main.py
```

## Example Kernels

### Memory Kernel
```python
def process_message(message):
    """Store messages as memories in PostgreSQL"""
    memory_data = json.loads(message.value.decode('utf-8'))
    store_memory(memory_data)
    return True
```

### Analytics Kernel
```python
def process_message(message):
    """Process analytics events"""
    event = json.loads(message.value.decode('utf-8'))
    update_metrics(event)
    send_to_warehouse(event)
    return True
```

### Notification Kernel
```python
def process_message(message):
    """Send notifications based on events"""
    notification = json.loads(message.value.decode('utf-8'))
    if should_notify(notification):
        send_notification(notification)
    return True
```

## Best Practices

1. **Idempotency**: Ensure message processing is idempotent
2. **Error Handling**: Distinguish between retriable and fatal errors
3. **Monitoring**: Add metrics and health checks
4. **Testing**: Test with sample messages and error conditions
5. **Documentation**: Update CLAUDE.md with kernel-specific guidance
6. **Security**: Never commit secrets; use environment variables

## Troubleshooting

### SSL Certificate Issues
- Ensure certificates are base64-encoded
- Check certificate expiration
- Verify certificate permissions

### Kafka Connection Issues
- Verify bootstrap servers
- Check network connectivity
- Validate consumer group permissions

### Processing Issues
- Check message format expectations
- Verify external service availability
- Monitor consumer lag

## Contributing

1. Fork this template
2. Create your kernel
3. Test thoroughly
4. Document your changes
5. Submit a pull request

## License

[Your License Here]