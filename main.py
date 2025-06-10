#!/usr/bin/env python3

import os
import sys
import logging
import base64
import tempfile
from kafka import KafkaConsumer, ConsumerRebalanceListener

# Configuration - modify these for your specific kernel
KERNEL_NAME = "hello-world"
DEFAULT_TOPIC = "clustera-hello-world"

def get_cert_data(env_var_name):
    """Get and decode base64 certificate from environment variable"""
    cert_b64 = os.getenv(env_var_name)
    if not cert_b64:
        raise ValueError(f"Environment variable {env_var_name} not found")
    return base64.b64decode(cert_b64)

def write_cert_to_temp_file(cert_data):
    """Write certificate data to a temporary file and return the path"""
    temp_file = tempfile.NamedTemporaryFile(mode='wb', delete=False)
    temp_file.write(cert_data)
    temp_file.close()
    return temp_file.name

def process_message(message):
    """
    Process a single Kafka message.
    
    Override this function to implement your kernel's specific logic.
    
    Args:
        message: Kafka message object with .key, .value, .offset, .partition, etc.
    
    Returns:
        bool: True if message was processed successfully, False otherwise
    """
    try:
        # Extract message key
        key_str = "No key"
        if message.key is not None:
            try:
                key_str = message.key.decode('utf-8')
            except UnicodeDecodeError:
                key_str = f"[Binary key - {len(message.key)} bytes]"
        
        # Extract message value
        value_str = "Null value"
        if message.value is not None:
            try:
                value_str = message.value.decode('utf-8')
            except UnicodeDecodeError:
                value_str = f"[Binary data - {len(message.value)} bytes]"
        
        # Hello-world processing: just log and print the message
        print(f"[{KERNEL_NAME}] Message at offset {message.offset}")
        print(f"  Key: {key_str}")
        print(f"  Value: {value_str}")
        print(f"  Partition: {message.partition}")
        print(f"  Timestamp: {message.timestamp}")
        print("---")
        
        # Force flush output for real-time visibility
        sys.stdout.flush()
        
        # TODO: Implement your kernel's specific processing logic here
        # Examples:
        # - Store to database
        # - Transform and forward to another topic
        # - Trigger external API calls
        # - Update in-memory state
        
        return True
        
    except Exception as e:
        logging.error(f"Error processing message at offset {message.offset}: {e}")
        return False

class KernelPartitionListener(ConsumerRebalanceListener):
    """Handle Kafka partition assignment and rebalancing events"""
    
    def __init__(self, consumer):
        self.consumer = consumer
    
    def on_partitions_assigned(self, assigned):
        """Called when partitions are assigned to this consumer"""
        partition_info = [f"{tp.topic}:{tp.partition}" for tp in assigned]
        logging.info(f"[{KERNEL_NAME}] Partitions assigned: {', '.join(partition_info)}")
        
        # Log initial state for each partition
        for tp in assigned:
            try:
                # Short poll to update internal state
                self.consumer.poll(timeout_ms=10)
                position = self.consumer.position(tp)
                highwater = self.consumer.highwater(tp)
                lag = highwater - position if highwater is not None and position is not None else 'N/A'
                logging.info(f"[{KERNEL_NAME}] Initial state for {tp}: position={position}, highwater={highwater}, lag={lag}")
            except Exception as e:
                logging.error(f"[{KERNEL_NAME}] Error getting initial state for {tp}: {e}")
    
    def on_partitions_revoked(self, revoked):
        """Called when partitions are revoked from this consumer"""
        partition_info = [f"{tp.topic}:{tp.partition}" for tp in revoked]
        logging.info(f"[{KERNEL_NAME}] Partitions revoked: {', '.join(partition_info)}")

def setup_kafka_consumer():
    """Set up and configure the Kafka consumer with SSL"""
    # Get SSL certificate data from environment variables
    ca_data = get_cert_data("KAFKA_CA_CERT")
    cert_data = get_cert_data("KAFKA_CLIENT_CERT")
    key_data = get_cert_data("KAFKA_CLIENT_KEY")
    
    # Write certificate data to temporary files
    ca_file = write_cert_to_temp_file(ca_data)
    cert_file = write_cert_to_temp_file(cert_data)
    key_file = write_cert_to_temp_file(key_data)
    
    # Get topic from environment or use default
    topic_name = os.getenv("KAFKA_TOPIC", DEFAULT_TOPIC)
    
    consumer = KafkaConsumer(
        topic_name,
        bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", ""),
        client_id=os.getenv("KAFKA_CLIENT_ID", f"{KERNEL_NAME}-consumer-{os.getpid()}"),
        group_id=os.getenv("KAFKA_CONSUMER_GROUP", f"{KERNEL_NAME}-group"),
        security_protocol="SSL",
        ssl_cafile=ca_file,
        ssl_certfile=cert_file,
        ssl_keyfile=key_file,
        ssl_check_hostname=True,
        session_timeout_ms=30000,      # 30 seconds
        heartbeat_interval_ms=10000,   # 10 seconds  
        max_poll_interval_ms=300000,   # 5 minutes
        auto_offset_reset='earliest',  # Start from beginning if no committed offset
        enable_auto_commit=False,      # Manual offset commits for reliability
        max_poll_records=1             # Process one message at a time
    )
    
    return consumer, (ca_file, cert_file, key_file)

def main():
    """Main kernel execution loop"""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO, 
        format=f'%(asctime)s - [{KERNEL_NAME}] - %(levelname)s - %(message)s'
    )
    
    logging.info(f"Starting {KERNEL_NAME} kernel...")
    
    # Set up Kafka consumer
    consumer, cert_files = setup_kafka_consumer()
    ca_file, cert_file, key_file = cert_files
    
    try:
        # Subscribe with partition listener
        partition_listener = KernelPartitionListener(consumer)
        topic_name = os.getenv("KAFKA_TOPIC", DEFAULT_TOPIC)
        consumer.subscribe([topic_name], listener=partition_listener)
        
        logging.info(f"[{KERNEL_NAME}] Subscribed to topic: {topic_name}")
        logging.info(f"[{KERNEL_NAME}] Consumer group: {consumer.config['group_id']}")
        
        # Main processing loop
        while True:
            try:
                message_batch = consumer.poll(timeout_ms=1000)
                
                if not message_batch:
                    # No messages received, continue polling
                    continue
                
                # Process messages from all partitions
                for topic_partition, messages in message_batch.items():
                    logging.info(f"[{KERNEL_NAME}] Received {len(messages)} messages from {topic_partition}")
                    
                    # Process each message
                    for i, message in enumerate(messages):
                        logging.info(f"[{KERNEL_NAME}] Processing message {i+1}/{len(messages)} at offset {message.offset}")
                        
                        success = process_message(message)
                        
                        if not success:
                            logging.warning(f"[{KERNEL_NAME}] Failed to process message at offset {message.offset}")
                            # TODO: Implement error handling strategy:
                            # - Skip and continue
                            # - Retry with backoff
                            # - Send to dead letter queue
                            # - Stop processing
                    
                    # Manually commit offsets after processing all messages in the batch
                    consumer.commit()
                    logging.debug(f"[{KERNEL_NAME}] Committed offsets for {topic_partition}")

            except Exception as e:
                logging.error(f"[{KERNEL_NAME}] Error consuming messages: {e}")
                # TODO: Implement recovery strategy
                
    except KeyboardInterrupt:
        logging.info(f"[{KERNEL_NAME}] Received shutdown signal")
    except Exception as e:
        logging.error(f"[{KERNEL_NAME}] Fatal error: {e}")
        raise
    finally:
        # Clean up temporary certificate files
        try:
            os.unlink(ca_file)
            os.unlink(cert_file)
            os.unlink(key_file)
            logging.info(f"[{KERNEL_NAME}] Cleaned up temporary certificate files")
        except Exception as e:
            logging.warning(f"[{KERNEL_NAME}] Error cleaning up certificate files: {e}")
        
        logging.info(f"[{KERNEL_NAME}] Kernel shutdown complete")

if __name__ == "__main__":
    main()
