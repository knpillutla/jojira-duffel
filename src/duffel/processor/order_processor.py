"""
Azure Service Bus Flight Order Hold Event Processor Module.
Reads order hold events from Azure Service Bus queue (or fallback queue),
invokes Duffel Payments API to ticket/confirm seats, and sends customer confirmation emails.
"""

import json
import logging
import os
import time
from typing import Any, Optional

from ..client import DuffelClient
from ..config import DuffelConfig
from ..services.email_service import EmailService
from ..services.event_publisher import EventPublisher, ServiceBusPublisher

logger = logging.getLogger(__name__)


class OrderProcessor:
    """Worker processor that consumes OrderHoldEvent messages, executes payment, and delivers emails."""

    def __init__(self, client: Optional[DuffelClient] = None):
        if client:
            self.client = client
        else:
            token = os.environ.get("DUFFEL_API_TOKEN", "")
            self.client = DuffelClient(api_token=token)

        self.config = self.client.config
        self.publisher = ServiceBusPublisher(self.config)
        self.email_service = EmailService(self.config)

    def process_order_hold_event(self, event_data: dict[str, Any]) -> dict[str, Any]:
        """
        Process a single OrderHoldEvent payload:
        1. Extract order details & payment info.
        2. Invoke Duffel Payments API (POST /air/orders/{order_id}/payments).
        3. Trigger Email Confirmation Service upon payment confirmation.
        """
        order_id = event_data.get("order_id")
        if not order_id:
            raise ValueError("OrderHoldEvent missing required 'order_id' field.")

        booking_ref = event_data.get("booking_reference") or order_id
        total_amount = event_data.get("total_amount", "0.00")
        total_currency = event_data.get("total_currency", "USD")
        passengers = event_data.get("passengers", [])
        slices = event_data.get("slices", [])
        payment_input = event_data.get("payment", {"type": "balance", "amount": total_amount, "currency": total_currency})

        print(f"\n[ORDER PROCESSOR] Processing OrderHoldEvent for Order '{order_id}' (PNR: {booking_ref})...")

        # Step 1: Execute Duffel Order Payment via POST /air/orders/{order_id}/payments
        try:
            pay_res = self.client.flights.pay_order(
                order_id=order_id,
                payment=payment_input,
                amount=total_amount,
                currency=total_currency
            )
            print(f"[ORDER PROCESSOR] Duffel Payments API response for order '{order_id}': {pay_res}")
        except Exception as pay_err:
            print(f"[ORDER PROCESSOR ERROR] Failed Duffel payment invocation for order '{order_id}': {pay_err}")
            pay_res = {"status": "payment_failed", "error": str(pay_err)}

        # Step 2: Extract primary customer email address
        recipient_email = "customer@example.com"
        for p in passengers:
            p_email = p.get("email")
            if p_email and "@" in p_email:
                recipient_email = p_email
                break

        # Step 3: Trigger Confirmation Email Service (Hold vs Confirmed)
        is_paid = isinstance(pay_res, dict) and pay_res.get("status") in ["paid", "confirmed"]
        pay_req_by = event_data.get("payment_required_by")
        email_res = self.email_service.send_booking_confirmation(
            order_id=order_id,
            booking_reference=booking_ref,
            total_amount=total_amount,
            total_currency=total_currency,
            passengers=passengers,
            slices=slices,
            recipient_email=recipient_email,
            is_hold=not is_paid,
            payment_required_by=pay_req_by,
        )

        # Step 4: Update Order DAO (Database) record with confirmed status, payment_status, and email_confirmation_status
        pay_status = "paid" if isinstance(pay_res, dict) and pay_res.get("status") in ["paid", "confirmed"] else "failed"
        email_status = email_res.get("status", "sent")
        order_status = "confirmed" if pay_status == "paid" else "hold"

        try:
            from ..db.order_dao import OrderDAO
            order_dao = OrderDAO(config=self.config)
            order_dao.update_order_status(
                duffel_order_id=order_id,
                status=order_status,
                payment_status=pay_status,
                email_confirmation_status=email_status,
                payment_details=pay_res if isinstance(pay_res, dict) else {},
                email_recipient=recipient_email
            )
        except Exception as db_update_err:
            print(f"[ORDER PROCESSOR NOTICE] OrderDAO update notice for '{order_id}': {db_update_err}")

        return {
            "status": "completed",
            "order_id": order_id,
            "booking_reference": booking_ref,
            "payment_details": pay_res,
            "email_confirmation": email_res,
            "processed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

    def process_booking_confirmed_event(self, event_data: dict[str, Any]) -> dict[str, Any]:
        """
        Process a BOOKING_CONFIRMED event:
        Delivers the confirmed booking email notification directly to the customer.
        """
        booking_id = event_data.get("booking_id") or event_data.get("order_id", "")
        booking_ref = event_data.get("booking_reference") or booking_id
        recipient_email = event_data.get("recipient_email", "customer@example.com")
        total_amount = event_data.get("total_amount", "0.00")
        total_currency = event_data.get("total_currency", "USD")
        passengers = event_data.get("passengers", [])
        slices = event_data.get("slices", [])

        print(f"[ORDER PROCESSOR] Processing BookingConfirmedEvent for '{booking_id}' (PNR: {booking_ref}, Recipient: {recipient_email})...")
        email_res = self.email_service.send_booking_confirmation(
            order_id=booking_id,
            booking_reference=booking_ref,
            total_amount=total_amount,
            total_currency=total_currency,
            passengers=passengers,
            slices=slices,
            recipient_email=recipient_email,
        )
        return {
            "status": "completed",
            "event_type": "BOOKING_CONFIRMED",
            "booking_id": booking_id,
            "booking_reference": booking_ref,
            "email_confirmation": email_res,
            "processed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

    def process_pending_events(self, max_messages: int = 10) -> list[dict[str, Any]]:
        """
        Polls and processes pending events from RabbitMQ, Azure Service Bus, or fallback queue.
        """
        results = []

        def _dispatch_event(event_data: dict[str, Any]) -> dict[str, Any]:
            ev_type = event_data.get("event_type", "ORDER_HOLD_CREATED")
            if ev_type == "BOOKING_CONFIRMED":
                return self.process_booking_confirmed_event(event_data)
            return self.process_order_hold_event(event_data)

        # 1. RabbitMQ Consumer
        if self.publisher.broker_type == "rabbitmq" and self.publisher.pika_available:
            try:
                import pika
                credentials = pika.PlainCredentials(self.publisher.rmq_user, self.publisher.rmq_pass)
                connection = pika.BlockingConnection(
                    pika.ConnectionParameters(host=self.publisher.rmq_host, port=self.publisher.rmq_port, credentials=credentials, connection_attempts=1, retry_delay=1)
                )
                channel = connection.channel()
                channel.queue_declare(queue=self.publisher.queue_name, durable=True)

                count = 0
                while count < max_messages:
                    method_frame, header_frame, body = channel.basic_get(queue=self.publisher.queue_name, auto_ack=False)
                    if method_frame:
                        try:
                            event_data = json.loads(body.decode("utf-8"))
                            res = _dispatch_event(event_data)
                            channel.basic_ack(method_frame.delivery_tag)
                            results.append(res)
                            count += 1
                        except Exception as msg_err:
                            print(f"[ORDER PROCESSOR ERROR] Error processing RabbitMQ message: {msg_err}")
                            channel.basic_nack(method_frame.delivery_tag, requeue=False)
                    else:
                        break
                connection.close()
                if results:
                    return results
            except Exception as rmq_recv_err:
                print(f"[ORDER PROCESSOR NOTICE] Could not connect to RabbitMQ ({rmq_recv_err}). Polling fallback queue.")

        # 2. Azure Service Bus Consumer
        if self.publisher.broker_type == "azure_service_bus" and self.publisher.azure_available and self.publisher._sb_client:
            try:
                from azure.servicebus import ServiceBusClient
                receiver = self.publisher._sb_client.get_queue_receiver(queue_name=self.publisher.sb_queue_name)
                with receiver:
                    received_msgs = receiver.receive_messages(max_message_count=max_messages, max_wait_time=3)
                    for msg in received_msgs:
                        try:
                            body_str = str(msg)
                            event_data = json.loads(body_str)
                            res = _dispatch_event(event_data)
                            receiver.complete_message(msg)
                            results.append(res)
                        except Exception as msg_err:
                            print(f"[ORDER PROCESSOR ERROR] Error processing SB message: {msg_err}")
                if results:
                    return results
            except Exception as sb_recv_err:
                print(f"[ORDER PROCESSOR ERROR] Failed reading Azure Service Bus queue: {sb_recv_err}")

        # 3. Fallback Queue Consumer
        count = 0
        while count < max_messages:
            event = EventPublisher.pop_fallback_event(timeout=0.2)
            if not event:
                break
            res = _dispatch_event(event)
            results.append(res)
            count += 1

        return results
