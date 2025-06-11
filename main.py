#!/usr/bin/env python3

import os
import sys
import logging
import base64
import tempfile
import json
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, validator
from kafka import KafkaProducer
import uvicorn

# Configuration
KERNEL_NAME = "api"
DEFAULT_QUERIES_TOPIC = "clustera-queries"

# Pydantic models for request/response
class QueryMetadata(BaseModel):
    """Optional metadata for the query"""
    user_id: Optional[str] = None
    source: Optional[str] = "api_kernel"
    priority: Optional[str] = "normal"
    
    class Config:
        extra = "allow"  # Allow additional fields

class QueryRequest(BaseModel):
    """Request model for POST /query"""
    prompt: str = Field(..., min_length=1, max_length=10000, description="Natural language prompt")
    metadata: Optional[QueryMetadata] = Field(default_factory=QueryMetadata)
    
    @validator('prompt')
    def validate_prompt(cls, v):
        if not v or not v.strip():
            raise ValueError('Prompt cannot be empty')
        return v.strip()

class QueryResponse(BaseModel):
    """Response model for successful query submission"""
    status: str = "published"
    query_id: str
    topic: str
    timestamp: str

class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    service: str = "clustera-api-kernel"
    timestamp: str

class KafkaHealthResponse(BaseModel):
    """Kafka health check response"""
    status: str
    kafka_connected: bool
    topic: str
    timestamp: str

# Global variables
kafka_producer: Optional[KafkaProducer] = None
security = HTTPBearer(auto_error=False)

def get_cert_data(env_var_name: str) -> bytes:
    """Get and decode base64 certificate from environment variable"""
    cert_b64 = os.getenv(env_var_name)
    if not cert_b64:
        raise ValueError(f"Environment variable {env_var_name} not found")
    return base64.b64decode(cert_b64)

def write_cert_to_temp_file(cert_data: bytes) -> str:
    """Write certificate data to a temporary file and return the path"""
    temp_file = tempfile.NamedTemporaryFile(mode='wb', delete=False)
    temp_file.write(cert_data)
    temp_file.close()
    return temp_file.name

def setup_kafka_producer() -> KafkaProducer:
    """Set up and configure the Kafka producer with SSL"""
    try:
        # Get SSL certificate data from environment variables
        ca_data = get_cert_data("KAFKA_CA_CERT")
        cert_data = get_cert_data("KAFKA_CLIENT_CERT")
        key_data = get_cert_data("KAFKA_CLIENT_KEY")
        
        # Write certificate data to temporary files
        ca_file = write_cert_to_temp_file(ca_data)
        cert_file = write_cert_to_temp_file(cert_data)
        key_file = write_cert_to_temp_file(key_data)
        
        producer = KafkaProducer(
            bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", ""),
            client_id=os.getenv("KAFKA_CLIENT_ID", f"{KERNEL_NAME}-producer-{os.getpid()}"),
            security_protocol="SSL",
            ssl_cafile=ca_file,
            ssl_certfile=cert_file,
            ssl_keyfile=key_file,
            ssl_check_hostname=True,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            key_serializer=lambda k: k.encode('utf-8') if k else None,
            acks='all',  # Wait for all replicas to acknowledge
            retries=3,   # Retry on failure
            batch_size=16384,
            linger_ms=10,
            buffer_memory=33554432,
        )
        
        logging.info(f"[{KERNEL_NAME}] Kafka producer initialized successfully")
        return producer
        
    except Exception as e:
        logging.error(f"[{KERNEL_NAME}] Failed to initialize Kafka producer: {e}")
        raise

async def verify_auth(credentials: HTTPAuthorizationCredentials = Depends(security)) -> bool:
    """Verify API authentication if enabled"""
    auth_enabled = os.getenv("API_AUTH_ENABLED", "false").lower() == "true"
    
    if not auth_enabled:
        return True
    
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    expected_token = os.getenv("API_AUTH_TOKEN")
    if not expected_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication configuration error"
        )
    
    if credentials.credentials != expected_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return True

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    global kafka_producer
    
    # Startup
    logging.info(f"[{KERNEL_NAME}] Starting API kernel...")
    try:
        kafka_producer = setup_kafka_producer()
        logging.info(f"[{KERNEL_NAME}] API kernel startup complete")
    except Exception as e:
        logging.error(f"[{KERNEL_NAME}] Failed to start API kernel: {e}")
        sys.exit(1)
    
    yield
    
    # Shutdown
    logging.info(f"[{KERNEL_NAME}] Shutting down API kernel...")
    if kafka_producer:
        kafka_producer.close()
        logging.info(f"[{KERNEL_NAME}] Kafka producer closed")

# Create FastAPI app
app = FastAPI(
    title="Clustera API Kernel",
    description="REST API endpoint for submitting natural language queries to Clustera",
    version="0.1.0",
    lifespan=lifespan
)

# Add CORS middleware
cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

@app.post("/query", response_model=QueryResponse, status_code=status.HTTP_201_CREATED)
async def submit_query(
    request: QueryRequest,
    authenticated: bool = Depends(verify_auth)
) -> QueryResponse:
    """
    Submit a natural language query to the Clustera platform.
    
    The query will be published to the configured Kafka topic for processing
    by other Clustera kernels.
    """
    global kafka_producer
    
    if not kafka_producer:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Kafka producer not available"
        )
    
    # Generate unique query ID
    query_id = str(uuid.uuid4())
    
    # Get topic from environment
    topic = os.getenv("KAFKA_TOPIC_QUERIES", DEFAULT_QUERIES_TOPIC)
    
    # Prepare message payload
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Ensure metadata exists and add system fields
    metadata = request.metadata.dict() if request.metadata else {}
    metadata.update({
        "source": "api_kernel",
        "timestamp": timestamp,
        "api_version": "0.1.0"
    })
    
    message = {
        "query_id": query_id,
        "prompt": request.prompt,
        "metadata": metadata
    }
    
    try:
        # Publish to Kafka
        future = kafka_producer.send(
            topic=topic,
            key=query_id,
            value=message
        )
        
        # Wait for confirmation (with timeout)
        record_metadata = future.get(timeout=10)
        
        logging.info(
            f"[{KERNEL_NAME}] Published query {query_id} to {topic} "
            f"(partition {record_metadata.partition}, offset {record_metadata.offset})"
        )
        
        return QueryResponse(
            query_id=query_id,
            topic=topic,
            timestamp=timestamp
        )
        
    except Exception as e:
        logging.error(f"[{KERNEL_NAME}] Failed to publish query {query_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to publish query: {str(e)}"
        )

@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Basic health check endpoint"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc).isoformat()
    )

@app.get("/health/kafka", response_model=KafkaHealthResponse)
async def kafka_health_check() -> KafkaHealthResponse:
    """Check Kafka connectivity"""
    global kafka_producer
    
    topic = os.getenv("KAFKA_TOPIC_QUERIES", DEFAULT_QUERIES_TOPIC)
    kafka_connected = kafka_producer is not None
    
    if kafka_connected:
        try:
            # Try to get metadata to verify connection
            metadata = kafka_producer.partitions_for(topic)
            kafka_connected = metadata is not None
        except Exception as e:
            logging.warning(f"[{KERNEL_NAME}] Kafka health check failed: {e}")
            kafka_connected = False
    
    return KafkaHealthResponse(
        status="healthy" if kafka_connected else "unhealthy",
        kafka_connected=kafka_connected,
        topic=topic,
        timestamp=datetime.now(timezone.utc).isoformat()
    )

@app.get("/")
async def root():
    """Root endpoint with basic information"""
    return {
        "service": "clustera-api-kernel",
        "version": "0.1.0",
        "description": "REST API endpoint for submitting queries to Clustera",
        "endpoints": {
            "submit_query": "POST /query",
            "health": "GET /health",
            "kafka_health": "GET /health/kafka"
        }
    }

def main():
    """Main entry point for running the API server"""
    # Configure logging
    log_level = os.getenv("API_LOG_LEVEL", "info").upper()
    logging.basicConfig(
        level=getattr(logging, log_level),
        format=f'%(asctime)s - [{KERNEL_NAME}] - %(levelname)s - %(message)s'
    )
    
    # Get server configuration
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    
    logging.info(f"[{KERNEL_NAME}] Starting API server on {host}:{port}")
    
    # Run the server
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        log_level=log_level.lower(),
        access_log=True
    )

if __name__ == "__main__":
    main()
