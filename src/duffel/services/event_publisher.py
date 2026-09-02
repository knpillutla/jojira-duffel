"""
Event Publisher Service for Jojira Duffel Integration.
Supports event publishing to RabbitMQ (local Docker), Azure Service Bus (Cloud), and local in-memory fallback queues.
"""

from datetime import datetime, timezone
import json
import logging
from queue import Empty, Queue
import time
from typing import Any, Optional

from ..config import DuffelConfig

logger = logging.getLogger(__name__)

# In-memory fallback queue for local development/testing without active RabbitMQ or Azure Service Bus
_IN_MEMORY_EVENT_QUEUE: Queue = Queue()


class EventPublisher:
    """Multi-broker event publisher for order hold events."""

    def __init__(self, config: Optional[DuffelConfig] = None):
        self.config = config or DuffelConfig()
        self.broker_type = getattr(self.config, "message_broker", "rabbitmq").lower()

        # RabbitMQ params
        self.rmq_host = getattr(self.config, "rabbitmq_host", "127.0.0.1")
        self.rmq_port = getattr(self.config, "rabbitmq_port", 5672)
        self.rmq_user = getattr(self.config, "rabbitmq_user", "guest")
        self.rmq_pass = getattr(self.config, "rabbitmq_password", "guest")
        self.queue_name = getattr(self.config, "rabbitmq_queue_name", "order-hold-events")

        # Azure Service Bus params
        self.sb_connection_string = getattr(self.config, "service_bus_connection_string", "")
        self.sb_queue_name = getattr(self.config, "service_bus_queue_name", "order-hold-events")

        self.pika_available = False
        self.azure_available = False
        self._sb_client = None

        if self.broker_type == "rabbitmq":
            try:
                import pika
                self.pika_available = True
            except ImportError:
                logger.info("[EVENT PUBLISHER] 'pika' package not installed. Using fallback queue.")

        elif self.broker_type == "azure_service_bus" and self.sb_connection_string:
            try:
                from azure.servicebus import ServiceBusClient
                self._sb_client = ServiceBusClient.from_connection_string(conn_str=self.sb_connection_string)
                self.azure_available = True
            except (ImportError, Exception) as err:
                logger.info(f"[EVENT PUBLISHER] Azure Service Bus unavailable ({err}). Using fallback queue.")

    def publish_order_hold_event(
        self,
        order_id: str,
        booking_reference: str,
        total_amount: str,
        total_currency: str = "USD",
        passengers: Optional[list[dict[str, Any]]] = None,
        slices: Optional[list[dict[str, Any]]] = None,
        payment: Optional[dict[str, Any]] = None,
        payment_required_by: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Construct and publish an OrderHoldEvent payload.
        """
        payload = {
            "event_id": f"evt_{int(time.time() * 1000)}",
            "event_type": "ORDER_HOLD_CREATED",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "order_id": order_id,
            "booking_reference": booking_reference,
            "total_amount": str(total_amount),
            "total_currency": total_currency,
            "passengers": passengers or [],
            "slices": slices or [],
            "payment": payment or {"type": "balance", "amount": str(total_amount), "currency": total_currency},
            "payment_required_by": payment_required_by,
        }

        # 1. RabbitMQ Publishing
        if self.broker_type == "rabbitmq" and self.pika_available:
            try:
                import pika
                credentials = pika.PlainCredentials(self.rmq_user, self.rmq_pass)
                connection = pika.BlockingConnection(
                    pika.ConnectionParameters(host=self.rmq_host, port=self.rmq_port, credentials=credentials, connection_attempts=1, retry_delay=1)
                )
                channel = connection.channel()
                channel.queue_declare(queue=self.queue_name, durable=True)
                channel.basic_publish(
                    exchange="",
                    routing_key=self.queue_name,
                    body=json.dumps(payload),
                    properties=pika.BasicProperties(delivery_mode=2)  # Persistent
                )
                connection.close()
                print(f"[RABBITMQ PUBLISHER] Successfully published OrderHoldEvent for order '{order_id}' to queue '{self.queue_name}'.")
                return {"status": "published_rabbitmq", "queue": self.queue_name, "order_id": order_id}
            except Exception as rmq_err:
                print(f"[RABBITMQ NOTICE] Could not connect to RabbitMQ ({rmq_err}). Enqueueing event into fallback queue.")

        # 2. Azure Service Bus Publishing
        elif self.broker_type == "azure_service_bus" and self.azure_available and self._sb_client:
            try:
                from azure.servicebus import ServiceBusMessage
                sender = self._sb_client.get_queue_sender(queue_name=self.sb_queue_name)
                with sender:
                    sb_msg = ServiceBusMessage(json.dumps(payload))
                    sender.send_messages(sb_msg)
                print(f"[AZURE SERVICE BUS] Successfully published OrderHoldEvent for order '{order_id}'.")
                return {"status": "published_azure_service_bus", "queue": self.sb_queue_name, "order_id": order_id}
            except Exception as sb_err:
                print(f"[AZURE SERVICE BUS NOTICE] Failed to publish message: {sb_err}. Enqueueing into fallback queue.")

        # 3. Fallback Queue
        _IN_MEMORY_EVENT_QUEUE.put(payload)
        print(f"[SERVICE BUS FALLBACK] Enqueued OrderHoldEvent for order '{order_id}' into fallback queue.")
        return {"status": "queued_in_memory_fallback", "order_id": order_id, "payload": payload}

    def publish_booking_confirmed_event(
        self,
        booking_id: str,
        booking_reference: str,
        total_amount: str,
        total_currency: str = "USD",
        booking_type: str = "flight",
        recipient_email: str = "customer@example.com",
        passengers: Optional[list[dict[str, Any]]] = None,
        slices: Optional[list[dict[str, Any]]] = None,
        hotel: Optional[dict[str, Any]] = None,
        car: Optional[dict[str, Any]] = None,
        bundle_components: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        """
        Construct and publish a BookingConfirmedEvent when all components in a booking are fully confirmed.
        """
        payload = {
            "event_id": f"evt_conf_{int(time.time() * 1000)}",
            "event_type": "BOOKING_CONFIRMED",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "booking_id": booking_id,
            "order_id": booking_id,
            "booking_reference": booking_reference,
            "booking_type": booking_type,
            "total_amount": str(total_amount),
            "total_currency": total_currency,
            "recipient_email": recipient_email,
            "passengers": passengers or [],
            "slices": slices or [],
            "hotel": hotel or {},
            "car": car or {},
            "bundle_components": bundle_components or [],
        }

        # 1. RabbitMQ
        if self.broker_type == "rabbitmq" and self.pika_available:
            try:
                import pika
                credentials = pika.PlainCredentials(self.rmq_user, self.rmq_pass)
                connection = pika.BlockingConnection(
                    pika.ConnectionParameters(host=self.rmq_host, port=self.rmq_port, credentials=credentials, connection_attempts=1, retry_delay=1)
                )
                channel = connection.channel()
                channel.queue_declare(queue=self.queue_name, durable=True)
                channel.basic_publish(
                    exchange="",
                    routing_key=self.queue_name,
                    body=json.dumps(payload),
                    properties=pika.BasicProperties(delivery_mode=2),
                )
                connection.close()
                print(f"[RABBITMQ PUBLISHER] Published BookingConfirmedEvent for '{booking_id}' (PNR: {booking_reference}).")
                return {"status": "published_rabbitmq", "queue": self.queue_name, "booking_id": booking_id}
            except Exception as rmq_err:
                print(f"[RABBITMQ NOTICE] Could not connect to RabbitMQ ({rmq_err}). Enqueueing event into fallback queue.")

        # 2. Azure Service Bus
        elif self.broker_type == "azure_service_bus" and self.azure_available and self._sb_client:
            try:
                from azure.servicebus import ServiceBusMessage
                sender = self._sb_client.get_queue_sender(queue_name=self.sb_queue_name)
                with sender:
                    sender.send_messages(ServiceBusMessage(json.dumps(payload)))
                print(f"[AZURE SERVICE BUS] Published BookingConfirmedEvent for '{booking_id}' (PNR: {booking_reference}).")
                return {"status": "published_azure_service_bus", "queue": self.sb_queue_name, "booking_id": booking_id}
            except Exception as sb_err:
                print(f"[AZURE SERVICE BUS NOTICE] Failed to publish message: {sb_err}. Enqueueing into fallback queue.")

        # 3. Fallback in-memory queue
        _IN_MEMORY_EVENT_QUEUE.put(payload)
        print(f"[SERVICE BUS FALLBACK] Enqueued BookingConfirmedEvent for '{booking_id}' into fallback queue.")
        return {"status": "queued_in_memory_fallback", "booking_id": booking_id, "payload": payload}

    @staticmethod
    def pop_fallback_event(timeout: float = 0.5) -> Optional[dict[str, Any]]:
        """Pop an event from the fallback in-memory queue."""
        try:
            return _IN_MEMORY_EVENT_QUEUE.get(block=True, timeout=timeout)
        except Empty:
            return None


# Alias for backward compatibility
ServiceBusPublisher = EventPublisher
