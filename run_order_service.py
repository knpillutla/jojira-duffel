"""
Executable CLI runner for Jojira Order Service & Background Event Worker.
Reads order hold events, executes Duffel payment requests, updates DB order lifecycle, and sends confirmation emails.
"""

import argparse
import sys
import time

from src.duffel import DuffelClient
from src.duffel.processor import OrderProcessor


def main():
    parser = argparse.ArgumentParser(description="Jojira Order Service & Async Event Worker")
    parser.add_argument("--once", action="store_true", help="Process currently enqueued events once and exit.")
    parser.add_argument("--interval", type=float, default=3.0, help="Polling interval in seconds (default: 3.0)")
    args = parser.parse_args()

    print("=" * 70)
    print("  JOJIRA TRAVEL - ORDER SERVICE & ASYNC EVENT WORKER")
    print("=" * 70)

    client = DuffelClient()
    processor = OrderProcessor(client=client)

    broker_type = processor.publisher.broker_type.upper()
    if processor.publisher.pika_available:
        broker_status = f"RabbitMQ ({processor.publisher.rmq_host}:{processor.publisher.rmq_port})"
    elif processor.publisher.azure_available:
        broker_status = "Azure Service Bus (Connected)"
    else:
        broker_status = "Local In-Memory Event Fallback"

    print(f"  * Message Broker Mode    : {broker_type}")
    print(f"  * Broker Status          : {broker_status}")
    print(f"  * Queue / Topic Name     : {processor.publisher.queue_name}")
    print(f"  * Email Confirmation     : {'Enabled' if processor.email_service.enabled else 'Disabled'}")
    print(f"  * SMTP Host / Port       : {processor.email_service.smtp_host}:{processor.email_service.smtp_port}")
    print("=" * 70 + "\n")

    if args.once:
        print("[+] Processing pending order hold events...")
        results = processor.process_pending_events(max_messages=10)
        print(f"[+] Processed {len(results)} order hold events successfully.")
        return

    print("[+] Order Service worker started. Listening for order hold events... (Press Ctrl+C to stop)\n")
    try:
        while True:
            processed = processor.process_pending_events(max_messages=10)
            if processed:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Processed {len(processed)} order hold events.")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n[+] Order Service worker shutdown cleanly.")
        sys.exit(0)


if __name__ == "__main__":
    main()
