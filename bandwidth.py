"""
Bandwidth Management — Edge device bandwidth constraints.

Edge devices have limited bandwidth. This module manages allocation,
adaptive distribution, overflow queuing, and priority-based preemption.
"""

import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


# ─── BandwidthMessage ─────────────────────────────────────────────────────────

@dataclass
class BandwidthMessage:
    """A message with bandwidth metadata."""
    message_id: str
    payload_size: int  # bytes
    priority: int = 2  # 0=critical, 1=high, 2=medium, 3=low, 4=info
    tender_type: str = "general"
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "message_id": self.message_id,
            "payload_size": self.payload_size,
            "priority": self.priority,
            "tender_type": self.tender_type,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'BandwidthMessage':
        return cls(
            message_id=data["message_id"],
            payload_size=data.get("payload_size", 0),
            priority=data.get("priority", 2),
            tender_type=data.get("tender_type", "general"),
            created_at=data.get("created_at", time.time()),
        )


# ─── BandwidthBudget ──────────────────────────────────────────────────────────

class BandwidthBudget:
    """Manages edge device bandwidth allocation and enforcement.

    Features:
    - Total bandwidth limit (bytes/sec)
    - Per-tender allocation
    - Adaptive allocation (more bandwidth for active research sessions)
    - Overflow queue (queue messages when bandwidth exceeded)
    - Priority-based preemption (drop low-priority when overloaded)
    """

    def __init__(self, total_bps: int = 1024):
        self.total_bps = total_bps
        self.base_allocations: Dict[str, float] = {
            "research": 0.30,
            "data": 0.25,
            "priority": 0.25,
            "context": 0.10,
            "general": 0.10,
        }
        self.active_sessions: Dict[str, float] = {}  # session_id → boost factor
        self.overflow_queue: List[BandwidthMessage] = []
        self.dropped_messages: List[dict] = []
        self.delivered_bytes: int = 0
        self.queued_bytes: int = 0

    def allocate(self, tender_type: str, message: BandwidthMessage) -> dict:
        """Try to allocate bandwidth for a message.

        Returns allocation result with whether it was accepted, queued, or dropped.
        """
        fraction = self.base_allocations.get(tender_type, 0.05)
        # Apply adaptive boost for active research sessions
        if tender_type == "research" and self.active_sessions:
            boost = min(sum(self.active_sessions.values()), 2.0)
            fraction = min(fraction * (1.0 + boost), 0.80)

        available = int(self.total_bps * fraction)
        needed = message.payload_size

        if needed <= available:
            self.delivered_bytes += needed
            return {
                "status": "delivered",
                "bytes": needed,
                "available": available,
                "tender_type": tender_type,
            }
        elif needed <= self.total_bps:
            # Queue it — might fit later
            self.overflow_queue.append(message)
            self.queued_bytes += needed
            return {
                "status": "queued",
                "bytes": needed,
                "available": available,
                "queue_position": len(self.overflow_queue),
            }
        else:
            # Message exceeds total capacity — drop it
            self.dropped_messages.append({
                "message_id": message.message_id,
                "reason": "exceeds_total_capacity",
                "size": needed,
                "timestamp": time.time(),
            })
            return {
                "status": "dropped",
                "bytes": needed,
                "reason": "exceeds_total_capacity",
            }

    def add_active_session(self, session_id: str, boost: float = 0.5):
        """Register an active research session for adaptive allocation."""
        self.active_sessions[session_id] = boost

    def remove_active_session(self, session_id: str):
        """Remove an active research session."""
        self.active_sessions.pop(session_id, None)

    def process_overflow(self, max_messages: int = 5) -> List[dict]:
        """Try to deliver queued messages from overflow.

        Processes up to max_messages, returns delivery results.
        Does NOT re-queue via allocate() — manages queue directly.
        """
        results = []
        to_process = self.overflow_queue[:max_messages]
        rest = self.overflow_queue[max_messages:]

        for msg in to_process:
            fraction = self.base_allocations.get(msg.tender_type, 0.05)
            if msg.tender_type == "research" and self.active_sessions:
                boost = min(sum(self.active_sessions.values()), 2.0)
                fraction = min(fraction * (1.0 + boost), 0.80)
            available = int(self.total_bps * fraction)
            needed = msg.payload_size

            if needed <= available:
                self.delivered_bytes += needed
                self.queued_bytes -= needed
                results.append({
                    "status": "delivered",
                    "bytes": needed,
                    "available": available,
                    "tender_type": msg.tender_type,
                })
            elif needed <= self.total_bps:
                # Still can't fit, keep in queue
                rest.append(msg)
            else:
                # Drop — exceeds total capacity
                self.dropped_messages.append({
                    "message_id": msg.message_id,
                    "reason": "exceeds_total_capacity",
                    "size": needed,
                    "timestamp": time.time(),
                })
                self.queued_bytes -= needed

        self.overflow_queue = rest
        return results

    def preempt(self, max_priority: int = 3) -> List[dict]:
        """Drop low-priority messages from overflow when overloaded.

        Drops messages with priority >= max_priority.
        """
        dropped = []
        kept = []
        for msg in self.overflow_queue:
            if msg.priority >= max_priority:
                self.dropped_messages.append({
                    "message_id": msg.message_id,
                    "reason": "preempted",
                    "size": msg.payload_size,
                    "timestamp": time.time(),
                })
                self.queued_bytes -= msg.payload_size
                dropped.append(msg.to_dict())
            else:
                kept.append(msg)
        self.overflow_queue = kept
        return dropped

    def set_allocation(self, tender_type: str, fraction: float):
        """Set custom per-tender allocation fraction."""
        self.base_allocations[tender_type] = max(0.0, min(1.0, fraction))

    def available_bandwidth(self) -> dict:
        """Get current bandwidth availability snapshot."""
        used = self.delivered_bytes
        return {
            "total_bps": self.total_bps,
            "allocated_tenders": dict(self.base_allocations),
            "active_sessions": len(self.active_sessions),
            "overflow_queue_size": len(self.overflow_queue),
            "queued_bytes": self.queued_bytes,
            "delivered_bytes": self.delivered_bytes,
            "dropped_count": len(self.dropped_messages),
        }

    def to_dict(self) -> dict:
        return self.available_bandwidth()

    @classmethod
    def from_dict(cls, data: dict) -> 'BandwidthBudget':
        budget = cls(total_bps=data.get("total_bps", 1024))
        for tt, frac in data.get("allocated_tenders", {}).items():
            budget.base_allocations[tt] = frac
        return budget
