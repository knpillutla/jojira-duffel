"""
Service Bus & Event Publisher service module for Jojira Duffel Integration.
Maintains backward compatibility by exposing EventPublisher as ServiceBusPublisher.
"""

from .event_publisher import EventPublisher, ServiceBusPublisher

__all__ = ["EventPublisher", "ServiceBusPublisher"]
