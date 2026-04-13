#!/usr/bin/env python3
"""
Targeted tests for coverage gaps identified by pytest-cov.

Covers lines missed in relay.py, bandwidth.py, and tender_types.py:
- BandwidthMessage.from_dict (bandwidth:35)
- process_overflow "still can't fit" branch (bandwidth:153-155)
- process_overflow "drop exceeds capacity" branch (bandwidth:156-164)
- ResearchQuery.to_dict / from_dict (relay:188, 199)
- EdgeFinding.to_dict / from_dict (relay:220, 231)
- _strip_for_edge list cap at 20 (relay:416)
- compress_query hard-truncation for oversized sentence (tender_types:59-60)
"""

import json
import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from relay import (
    ResearchRelay, ResearchQuery, EdgeFinding, RelayMessage,
    MessageDirection, MessagePriority,
)
from bandwidth import BandwidthBudget, BandwidthMessage
from tender_types import ResearchTender


# ═══════════════════════════════════════════════════════════════════════════
# BandwidthMessage.from_dict — covers bandwidth.py:35
# ═══════════════════════════════════════════════════════════════════════════

class TestBandwidthMessageRoundTrip:
    def test_from_dict_basic(self):
        """BandwidthMessage.from_dict reconstructs a message correctly."""
        data = {
            "message_id": "bw-msg-001",
            "payload_size": 512,
            "priority": 1,
            "tender_type": "research",
            "created_at": 1700000000.0,
        }
        msg = BandwidthMessage.from_dict(data)
        assert msg.message_id == "bw-msg-001"
        assert msg.payload_size == 512
        assert msg.priority == 1
        assert msg.tender_type == "research"
        assert msg.created_at == 1700000000.0

    def test_from_dict_defaults(self):
        """from_dict fills in default values when keys are missing."""
        msg = BandwidthMessage.from_dict({"message_id": "minimal"})
        assert msg.payload_size == 0
        assert msg.priority == 2
        assert msg.tender_type == "general"
        assert msg.created_at > 0  # defaults to now

    def test_to_dict_round_trip(self):
        """to_dict → from_dict preserves all fields."""
        original = BandwidthMessage("rt-01", payload_size=256, priority=0, tender_type="priority")
        d = original.to_dict()
        restored = BandwidthMessage.from_dict(d)
        assert restored.message_id == original.message_id
        assert restored.payload_size == original.payload_size
        assert restored.priority == original.priority
        assert restored.tender_type == original.tender_type


# ═══════════════════════════════════════════════════════════════════════════
# process_overflow — covers bandwidth.py:153-164
# ═══════════════════════════════════════════════════════════════════════════

class TestProcessOverflowBranches:
    def test_overflow_still_cant_fit_stays_in_queue(self):
        """Message in overflow that still exceeds per-tender allocation
        but fits within total_bps stays in the queue."""
        b = BandwidthBudget(total_bps=200)
        # context tender gets 10% = 20 bytes. Queue a 100-byte message.
        msg = BandwidthMessage("ctx-01", payload_size=100, tender_type="context")
        result = b.allocate("context", msg)
        assert result["status"] == "queued"
        assert len(b.overflow_queue) == 1

        # process_overflow without boosting — still can't fit in 20 bytes,
        # but 100 <= 200 total_bps → stays in queue
        delivered = b.process_overflow(max_messages=5)
        assert len(delivered) == 0
        assert len(b.overflow_queue) == 1  # still queued

    def test_overflow_drop_exceeds_total_capacity(self):
        """Message in overflow that exceeds total_bps gets dropped during
        process_overflow."""
        b = BandwidthBudget(total_bps=100)
        # Manually inject a message larger than total_bps into overflow
        big_msg = BandwidthMessage("huge-01", payload_size=500, tender_type="research")
        b.overflow_queue = [big_msg]
        b.queued_bytes = 500

        delivered = b.process_overflow(max_messages=5)
        assert len(delivered) == 0
        assert len(b.overflow_queue) == 0
        assert len(b.dropped_messages) == 1
        assert b.dropped_messages[0]["reason"] == "exceeds_total_capacity"
        assert b.dropped_messages[0]["size"] == 500

    def test_overflow_mixed_results(self):
        """Multiple messages in overflow: some deliver, some stay, some drop."""
        b = BandwidthBudget(total_bps=200)
        # research gets 30% = 60 bytes
        small_research = BandwidthMessage("r-small", payload_size=30, tender_type="research")
        big_research = BandwidthMessage("r-big", payload_size=400, tender_type="research")
        b.overflow_queue = [small_research, big_research]
        b.queued_bytes = 430

        delivered = b.process_overflow(max_messages=5)
        assert len(delivered) == 1
        assert delivered[0]["status"] == "delivered"
        assert len(b.dropped_messages) == 1
        assert b.dropped_messages[0]["message_id"] == "r-big"


# ═══════════════════════════════════════════════════════════════════════════
# ResearchQuery.to_dict / from_dict — covers relay.py:188, 199
# ═══════════════════════════════════════════════════════════════════════════

class TestResearchQuerySerialization:
    def test_to_dict(self):
        q = ResearchQuery(
            query_id="q-001",
            query_text="Benchmark CUDA kernels",
            source_id="oracle1",
            priority=MessagePriority.HIGH,
            created_at=1700000000.0,
            status="completed",
        )
        d = q.to_dict()
        assert d["query_id"] == "q-001"
        assert d["query_text"] == "Benchmark CUDA kernels"
        assert d["source_id"] == "oracle1"
        assert d["priority"] == 1  # HIGH.value
        assert d["created_at"] == 1700000000.0
        assert d["status"] == "completed"

    def test_from_dict_round_trip(self):
        original = ResearchQuery(
            query_id="q-002",
            query_text="Test latency",
            source_id="cloud-src",
            priority=MessagePriority.CRITICAL,
            status="sent",
        )
        d = original.to_dict()
        restored = ResearchQuery.from_dict(d)
        assert restored.query_id == "q-002"
        assert restored.query_text == "Test latency"
        assert restored.source_id == "cloud-src"
        assert restored.priority == MessagePriority.CRITICAL
        assert restored.status == "sent"

    def test_from_dict_defaults(self):
        """from_dict fills defaults for missing optional fields."""
        d = {"query_id": "q-003", "query_text": "hello", "source_id": "src"}
        q = ResearchQuery.from_dict(d)
        assert q.priority == MessagePriority.MEDIUM  # default
        assert q.status == "pending"  # default
        assert q.created_at > 0

    def test_from_dict_all_priorities(self):
        """from_dict correctly parses each MessagePriority value."""
        for prio in MessagePriority:
            d = {
                "query_id": f"q-{prio.value}",
                "query_text": "test",
                "source_id": "s",
                "priority": prio.value,
            }
            q = ResearchQuery.from_dict(d)
            assert q.priority == prio


# ═══════════════════════════════════════════════════════════════════════════
# EdgeFinding.to_dict / from_dict — covers relay.py:220, 231
# ═══════════════════════════════════════════════════════════════════════════

class TestEdgeFindingSerialization:
    def test_to_dict(self):
        f = EdgeFinding(
            finding_id="f-001",
            node_id="jetson1",
            data={"latency_ms": 2.1, "pass": True},
            query_id="q-001",
            priority=MessagePriority.CRITICAL,
            created_at=1700000000.0,
        )
        d = f.to_dict()
        assert d["finding_id"] == "f-001"
        assert d["node_id"] == "jetson1"
        assert d["data"]["latency_ms"] == 2.1
        assert d["query_id"] == "q-001"
        assert d["priority"] == 0  # CRITICAL.value
        assert d["created_at"] == 1700000000.0

    def test_from_dict_round_trip(self):
        original = EdgeFinding(
            finding_id="f-002",
            node_id="j2",
            data={"result": 42},
            query_id="q-002",
            priority=MessagePriority.LOW,
        )
        d = original.to_dict()
        restored = EdgeFinding.from_dict(d)
        assert restored.finding_id == "f-002"
        assert restored.node_id == "j2"
        assert restored.data == {"result": 42}
        assert restored.query_id == "q-002"
        assert restored.priority == MessagePriority.LOW

    def test_from_dict_defaults(self):
        """from_dict fills defaults for missing optional fields."""
        d = {"finding_id": "f-003", "node_id": "j3", "data": None}
        f = EdgeFinding.from_dict(d)
        assert f.query_id is None
        assert f.priority == MessagePriority.MEDIUM  # default
        assert f.created_at > 0

    def test_from_dict_with_null_data(self):
        """from_dict handles null data gracefully."""
        d = {"finding_id": "f-004", "node_id": "j4", "data": None}
        f = EdgeFinding.from_dict(d)
        assert f.data is None


# ═══════════════════════════════════════════════════════════════════════════
# _strip_for_edge list cap at 20 — covers relay.py:416
# ═══════════════════════════════════════════════════════════════════════════

class TestStripForEdgeListCap:
    def test_list_capped_at_20_items(self):
        """_strip_for_edge caps lists at 20 items."""
        r = ResearchRelay()
        stripped = r._strip_for_edge(list(range(50)))
        assert len(stripped) == 20
        assert stripped == list(range(20))

    def test_list_exactly_20_not_capped(self):
        """A list of exactly 20 items should not be truncated."""
        r = ResearchRelay()
        data = {"items": list(range(20))}
        result = r.compress_for_edge(data, bandwidth_limit=10000)
        assert len(result["compressed"]["items"]) == 20

    def test_nested_list_capped(self):
        """Nested lists are also capped at 20 items."""
        r = ResearchRelay()
        stripped = r._strip_for_edge({"outer": {"inner": list(range(30))}})
        assert len(stripped["outer"]["inner"]) == 20

    def test_multiple_lists_all_capped(self):
        """Multiple lists in the data are all independently capped."""
        r = ResearchRelay()
        stripped = r._strip_for_edge({"a": list(range(25)), "b": list(range(25))})
        assert len(stripped["a"]) == 20
        assert len(stripped["b"]) == 20


# ═══════════════════════════════════════════════════════════════════════════
# compress_query hard-truncation — covers tender_types.py:59-60
# ═══════════════════════════════════════════════════════════════════════════

class TestCompressQueryHardTruncation:
    def test_single_oversized_sentence_hard_truncated(self):
        """When a single sentence exceeds bandwidth_limit, it gets hard-truncated."""
        t = ResearchTender()
        # One very long sentence with no period separator — exceeds 50 bytes
        long_sentence = "A" * 200
        result = t.compress_query(long_sentence, bandwidth_limit=50)
        assert result["truncated"] is True
        assert len(result["compressed_query"].encode("utf-8")) <= 50
        assert result["compressed_query"] == "A" * 50

    def test_hard_truncation_with_newlines(self):
        """Newlines are treated as sentence separators."""
        t = ResearchTender()
        text = "Line one\nLine two\nLine three"
        result = t.compress_query(text, bandwidth_limit=20)
        assert result["compressed_query"] != ""
        assert result["compressed_size"] <= 20

    def test_hard_truncation_preserves_some_content(self):
        """Hard truncation preserves at least bandwidth_limit bytes."""
        t = ResearchTender()
        text = "This is a single long sentence without any periods that goes on and on"
        limit = 30
        result = t.compress_query(text, bandwidth_limit=limit)
        assert len(result["compressed_query"]) > 0
        assert len(result["compressed_query"].encode("utf-8")) <= limit

    def test_hard_truncation_empty_result(self):
        """Empty string returns empty compressed_query."""
        t = ResearchTender()
        result = t.compress_query("", bandwidth_limit=100)
        assert result["compressed_query"] == ""
        assert result["original_size"] == 0
        assert result["compressed_size"] == 0
        assert result["truncated"] is False


# ═══════════════════════════════════════════════════════════════════════════
# Additional deep coverage tests
# ═══════════════════════════════════════════════════════════════════════════

class TestCloudEdgeAsymmetryDeep:
    def test_cloud_can_approximate_unknown(self):
        """Unknown aspect is not approximable by cloud."""
        from relay import CloudEdgeAsymmetry
        a = CloudEdgeAsymmetry()
        assert a.cloud_can_approximate("completely_unknown_aspect") is False

    def test_edge_can_approximate_unknown(self):
        """Unknown aspect is not approximable by edge."""
        from relay import CloudEdgeAsymmetry
        a = CloudEdgeAsymmetry()
        assert a.edge_can_approximate("completely_unknown_aspect") is False

    def test_log_divergence_severity_clamped_high(self):
        """Severity > 1.0 is clamped to 1.0."""
        from relay import CloudEdgeAsymmetry
        a = CloudEdgeAsymmetry()
        a.log_divergence("a", "b", severity=5.0)
        assert a.divergence_log[0]["severity"] == 1.0
        assert len(a.assumption_failures) == 1

    def test_log_divergence_severity_clamped_low(self):
        """Severity < 0.0 is clamped to 0.0."""
        from relay import CloudEdgeAsymmetry
        a = CloudEdgeAsymmetry()
        a.log_divergence("a", "b", severity=-1.0)
        assert a.divergence_log[0]["severity"] == 0.0
        assert len(a.assumption_failures) == 0

    def test_divergence_summary_empty(self):
        """Summary of zero divergences returns zero averages."""
        from relay import CloudEdgeAsymmetry
        a = CloudEdgeAsymmetry()
        s = a.divergence_summary()
        assert s["total_divergences"] == 0
        assert s["assumption_failures"] == 0
        assert s["average_severity"] == 0.0
        assert s["recent"] == []

    def test_divergence_summary_recent_capped_at_10(self):
        """Summary 'recent' field is capped at 10 entries."""
        from relay import CloudEdgeAsymmetry
        a = CloudEdgeAsymmetry()
        for i in range(15):
            a.log_divergence(f"cloud_{i}", f"edge_{i}", severity=0.5)
        s = a.divergence_summary()
        assert s["total_divergences"] == 15
        assert len(s["recent"]) == 10

    def test_divergence_summary_exact_severity_threshold(self):
        """Severity exactly 0.7 is counted as a failure."""
        from relay import CloudEdgeAsymmetry
        a = CloudEdgeAsymmetry()
        a.log_divergence("a", "b", severity=0.7)
        assert len(a.assumption_failures) == 1


class TestRelayMessageAllDirections:
    def test_all_direction_values(self):
        """Every MessageDirection enum value is a valid string."""
        for d in MessageDirection:
            msg = RelayMessage(
                message_id=f"msg-{d.value}",
                payload={},
                direction=d,
                source="src",
                destination="dst",
            )
            d2 = msg.to_dict()
            restored = RelayMessage.from_dict(d2)
            assert restored.direction == d

    def test_message_size_bytes(self):
        """size_bytes is preserved through serialization."""
        msg = RelayMessage("m1", {}, MessageDirection.INTERNAL, "s", "d", size_bytes=999)
        d = msg.to_dict()
        assert d["size_bytes"] == 999
        restored = RelayMessage.from_dict(d)
        assert restored.size_bytes == 999

    def test_message_with_all_priorities(self):
        """Messages can be created with every priority level."""
        for p in MessagePriority:
            msg = RelayMessage("m", {}, MessageDirection.INTERNAL, "s", "d", priority=p)
            assert msg.priority == p
            assert msg.to_dict()["priority"] == p.value


class TestBandwidthRemoveNonexistentSession:
    def test_remove_nonexistent_session_no_error(self):
        """Removing a session that doesn't exist doesn't raise."""
        b = BandwidthBudget(total_bps=100)
        b.remove_active_session("ghost-session")
        assert len(b.active_sessions) == 0


class TestBandwidthAllocateUnknownTender:
    def test_unknown_tender_uses_default_fraction(self):
        """Unknown tender type falls back to 5% allocation."""
        b = BandwidthBudget(total_bps=1000)
        # 5% of 1000 = 50 bytes
        msg = BandwidthMessage("m1", payload_size=30, tender_type="unknown_tender")
        result = b.allocate("unknown_tender", msg)
        assert result["status"] == "delivered"
        assert result["available"] == 50

    def test_unknown_tender_exceeds_default(self):
        """Unknown tender type: message larger than 5% allocation gets queued."""
        b = BandwidthBudget(total_bps=1000)
        msg = BandwidthMessage("m1", payload_size=100, tender_type="unknown_tender")
        result = b.allocate("unknown_tender", msg)
        assert result["status"] == "queued"


class TestPriorityTenderAllMappings:
    def test_all_cloud_to_edge_default_mappings(self):
        """Every default cloud→edge mapping is correct."""
        from tender_types import PriorityTender, CloudUrgency, EdgeUrgency
        from tender_types import DEFAULT_CLOUD_TO_EDGE
        t = PriorityTender()
        for cloud, expected_edge in DEFAULT_CLOUD_TO_EDGE.items():
            r = t.cloud_to_edge_urgency(cloud)
            assert r["edge_urgency"] == expected_edge.value, (
                f"{cloud} should map to {expected_edge.value}"
            )

    def test_all_edge_to_cloud_default_mappings(self):
        """Every default edge→cloud mapping is correct."""
        from tender_types import PriorityTender, EdgeUrgency, CloudUrgency
        from tender_types import DEFAULT_EDGE_TO_CLOUD
        t = PriorityTender()
        for edge, expected_cloud in DEFAULT_EDGE_TO_CLOUD.items():
            r = t.edge_to_cloud_urgency(edge)
            assert r["cloud_urgency"] == expected_cloud.value, (
                f"{edge} should map to {expected_cloud.value}"
            )

    def test_deferral_escalation_medium_urgency(self):
        """MEDIUM urgency maps to QUEUED, not DEFERRED, so no escalation."""
        from tender_types import PriorityTender, CloudUrgency
        t = PriorityTender()
        ctx = "med-test"
        for _ in range(5):
            t.record_deferral(ctx)
        r = t.cloud_to_edge_urgency(CloudUrgency.MEDIUM, context_id=ctx)
        assert r["edge_urgency"] == "queued"
        assert r["escalated"] is False  # was already queued, not deferred


class TestContextTenderKeyAdditionAndRemoval:
    def test_adding_new_key_in_update(self):
        """Adding a new key in an update shows it in diff."""
        from tender_types import ContextTender
        t = ContextTender()
        t.update_context("j1", {"a": 1})
        diff = t.update_context("j1", {"a": 1, "b": 2})
        assert "b" in diff["changed_keys"]
        assert diff["diff"]["b"]["old"] is None
        assert diff["diff"]["b"]["new"] == 2

    def test_removing_key_in_update(self):
        """Removing a key in an update shows old value in diff."""
        from tender_types import ContextTender
        t = ContextTender()
        t.update_context("j1", {"a": 1, "b": 2})
        diff = t.update_context("j1", {"a": 1})
        assert "b" in diff["changed_keys"]
        assert diff["diff"]["b"]["old"] == 2
        assert diff["diff"]["b"]["new"] is None

    def test_conflict_nonexistent_node(self):
        """detect_conflict on a node with no stored context returns None
        (incoming_version >= stored_version of 0)."""
        from tender_types import ContextTender
        t = ContextTender()
        assert t.detect_conflict("ghost", 0, {"x": 1}) is None

    def test_to_dict_conflict_count(self):
        """to_dict reports correct conflict count."""
        from tender_types import ContextTender
        t = ContextTender()
        t.update_context("j1", {"v": 1})
        t.update_context("j1", {"v": 2})
        t.detect_conflict("j1", 1, {"v": "old"})
        d = t.to_dict()
        assert d["conflict_count"] == 1


class TestIntegrationPriorityAndBandwidth:
    def test_priority_drives_bandwidth_allocation(self):
        """High-priority messages get more bandwidth headroom."""
        b = BandwidthBudget(total_bps=100)
        # priority tender gets 25% = 25 bytes
        high_msg = BandwidthMessage("h1", payload_size=20, tender_type="priority")
        result = b.allocate("priority", high_msg)
        assert result["status"] == "delivered"
        assert result["bytes"] == 20

        # Same size but context (10% = 10 bytes) gets queued
        ctx_msg = BandwidthMessage("c1", payload_size=20, tender_type="context")
        result2 = b.allocate("context", ctx_msg)
        assert result2["status"] == "queued"


class TestTruncateToFitEdgeCase:
    def test_truncate_empty_string(self):
        """_truncate_to_fit with empty string returns empty."""
        result = ResearchRelay._truncate_to_fit("", 100)
        assert result == ""

    def test_truncate_no_braces(self):
        """_truncate_to_fit on JSON without braces doesn't add extras."""
        result = ResearchRelay._truncate_to_fit('"hello world"', 10)
        assert result == '"hello wor'  # no braces to close

    def test_truncate_balanced_braces(self):
        """If braces are balanced in truncated portion, no extras added."""
        result = ResearchRelay._truncate_to_fit('{"a":1}', 7)
        # 7 chars = '{"a":1}' which is balanced
        assert result == '{"a":1}'

    def test_truncate_within_limit_after_closing(self):
        """Closing braces are appended after truncation."""
        result = ResearchRelay._truncate_to_fit('{"a":', 6)
        # '{"a":' is 6 chars: 1 open brace, 0 closed → adds 1 '}'
        # 'rstrip()' removes trailing whitespace, then '}' appended, then [:6]
        assert result == '{"a":}'


class TestResearchTenderSessionCompleteness:
    def test_session_has_all_fields(self):
        """start_session populates all expected fields."""
        t = ResearchTender()
        s = t.start_session("s-full", "query text")
        assert "session_id" in s
        assert "query" in s
        assert "started_at" in s
        assert s["status"] == "active"
        assert s["findings_received"] == []
        assert s["query_sent"] is False
        assert s["completed_at"] is None

    def test_completed_session_has_timestamp(self):
        """Completing a session sets completed_at."""
        t = ResearchTender()
        t.start_session("s-ts", "q")
        time.sleep(0.01)
        c = t.complete_session("s-ts")
        assert c["completed_at"] is not None
        assert c["completed_at"] > 0

    def test_active_sessions_count_in_to_dict(self):
        """to_dict correctly counts active sessions."""
        t = ResearchTender()
        t.start_session("s1", "q1")
        t.start_session("s2", "q2")
        t.complete_session("s1")
        d = t.to_dict()
        assert d["active_sessions"] == 1  # only s2 still active
