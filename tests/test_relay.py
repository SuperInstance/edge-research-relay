#!/usr/bin/env python3
"""
Comprehensive test suite for edge-research-relay.

Covers: CloudEdgeAsymmetry, ResearchRelay, ResearchTender, DataTender,
        PriorityTender, ContextTender, BandwidthBudget, and integration tests.
Aims for 35+ tests with full coverage of edge cases.
"""

import json
import sys
import time
from pathlib import Path

import pytest

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from relay import (
    CloudEdgeAsymmetry, ResearchRelay, CloudSource, EdgeNode,
    ResearchQuery, EdgeFinding, RelayMessage,
    MessageDirection, MessagePriority,
)
from tender_types import (
    ResearchTender, DataTender, PriorityTender, ContextTender,
    CloudUrgency, EdgeUrgency,
)
from bandwidth import BandwidthBudget, BandwidthMessage


# ═══════════════════════════════════════════════════════════════════════════
# 1. CloudEdgeAsymmetry
# ═══════════════════════════════════════════════════════════════════════════

class TestCloudEdgeAsymmetry:
    def test_cloud_strengths_populated(self):
        a = CloudEdgeAsymmetry()
        assert len(a.CLOUD_STRENGTHS) >= 4

    def test_edge_strengths_populated(self):
        a = CloudEdgeAsymmetry()
        assert len(a.EDGE_STRENGTHS) >= 4

    def test_cloud_blind_spots_populated(self):
        a = CloudEdgeAsymmetry()
        assert len(a.CLOUD_BLIND_SPOTS) >= 3

    def test_edge_blind_spots_populated(self):
        a = CloudEdgeAsymmetry()
        assert len(a.EDGE_BLIND_SPOTS) >= 3

    def test_cloud_can_approximate_edge_strength(self):
        a = CloudEdgeAsymmetry()
        assert a.cloud_can_approximate("validation") is True

    def test_edge_cannot_approximate_fleet_context(self):
        a = CloudEdgeAsymmetry()
        assert a.edge_can_approximate("fleet_wide_context") is False

    def test_edge_can_approximate_own_strength(self):
        a = CloudEdgeAsymmetry()
        assert a.edge_can_approximate("sensor_fusion") is True

    def test_log_divergence(self):
        a = CloudEdgeAsymmetry()
        a.log_divergence("Jetson has 8GB VRAM", "Actually 6GB usable", severity=0.8)
        assert len(a.divergence_log) == 1
        assert len(a.assumption_failures) == 1

    def test_log_divergence_low_severity(self):
        a = CloudEdgeAsymmetry()
        a.log_divergence("minor diff", "slightly off", severity=0.3)
        assert len(a.assumption_failures) == 0

    def test_divergence_summary(self):
        a = CloudEdgeAsymmetry()
        a.log_divergence("a", "b", 0.5)
        a.log_divergence("c", "d", 0.9)
        s = a.divergence_summary()
        assert s["total_divergences"] == 2
        assert s["assumption_failures"] == 1
        assert 0.0 < s["average_severity"] <= 1.0

    def test_to_dict(self):
        a = CloudEdgeAsymmetry()
        d = a.to_dict()
        assert "cloud_strengths" in d
        assert "edge_strengths" in d
        assert "divergence_summary" in d

    def test_from_dict(self):
        a = CloudEdgeAsymmetry.from_dict({})
        assert a is not None


# ═══════════════════════════════════════════════════════════════════════════
# 2. ResearchRelay — Registration & Submission
# ═══════════════════════════════════════════════════════════════════════════

class TestResearchRelayRegistration:
    def test_register_cloud_source(self):
        r = ResearchRelay()
        src = r.register_cloud_source("oracle1", ["architecture", "specs"])
        assert src.source_id == "oracle1"
        assert "oracle1" in r.cloud_sources

    def test_register_edge_node(self):
        r = ResearchRelay()
        node = r.register_edge_node("jetson1", ["cuda", "sensors"], {"vram": 8192})
        assert node.node_id == "jetson1"
        assert node.constraints["vram"] == 8192
        assert "jetson1" in r.edge_nodes

    def test_submit_research_query(self):
        r = ResearchRelay()
        q = r.submit_research_query("Test kernel latency on Jetson Orin", "oracle1")
        assert q.query_text == "Test kernel latency on Jetson Orin"
        assert q.status == "pending"
        assert q.query_id in r.queries

    def test_submit_edge_finding(self):
        r = ResearchRelay()
        f = r.submit_edge_finding("jetson1", {"latency_ms": 2.3})
        assert f.node_id == "jetson1"
        assert f.data["latency_ms"] == 2.3
        assert f.finding_id in r.findings

    def test_submit_finding_with_query(self):
        r = ResearchRelay()
        q = r.submit_research_query("test query")
        f = r.submit_edge_finding("jetson1", {"result": True}, query_id=q.query_id)
        assert f.query_id == q.query_id

    def test_to_dict_from_dict(self):
        r = ResearchRelay()
        r.register_cloud_source("o1", ["arch"])
        r.register_edge_node("j1", ["cuda"], {"vram": 8})
        d = r.to_dict()
        r2 = ResearchRelay.from_dict(d)
        assert "o1" in r2.cloud_sources
        assert "j1" in r2.edge_nodes


# ═══════════════════════════════════════════════════════════════════════════
# 3. Compression & Expansion
# ═══════════════════════════════════════════════════════════════════════════

class TestCompressionExpansion:
    def test_small_data_not_truncated(self):
        r = ResearchRelay()
        data = {"key": "value"}
        result = r.compress_for_edge(data, bandwidth_limit=1024)
        assert result["truncated"] is False
        assert result["ratio"] == 1.0

    def test_large_data_gets_compressed(self):
        r = ResearchRelay()
        data = {"metadata": "x" * 2000, "debug_info": "y" * 2000, "core": "keep"}
        result = r.compress_for_edge(data, bandwidth_limit=256)
        assert result["truncated"] is True
        assert result["compressed_size"] <= result["original_size"]
        assert "metadata" not in str(result["compressed"])

    def test_expand_from_edge(self):
        r = ResearchRelay()
        r.register_edge_node("j1", ["sensors"], {"vram": 8192})
        result = r.expand_from_edge({"temp": 42.0})
        assert result["data"]["temp"] == 42.0
        assert result["cloud_timestamp"] > 0
        assert result["edge_nodes_count"] == 1

    def test_expand_with_context(self):
        r = ResearchRelay()
        result = r.expand_from_edge({"val": 1}, context={"fleet": "active"})
        assert result["context"]["fleet"] == "active"

    def test_compress_nested_data(self):
        r = ResearchRelay()
        data = {"a": {"b": {"c": "x" * 500}}, "_internal": "strip_me", "full_history": "gone"}
        result = r.compress_for_edge(data, bandwidth_limit=100)
        assert result["truncated"] is True


# ═══════════════════════════════════════════════════════════════════════════
# 4. Prioritization & Batching
# ═══════════════════════════════════════════════════════════════════════════

class TestPrioritizationBatching:
    def test_prioritize_by_capacity(self):
        r = ResearchRelay()
        queries = [
            r.submit_research_query(f"query {i}", priority=MessagePriority(i % 3))
            for i in range(10)
        ]
        prioritized = r.prioritize_queries(queries, edge_capacity=3)
        assert len(prioritized) == 3

    def test_prioritize_critical_first(self):
        r = ResearchRelay()
        q_low = r.submit_research_query("low", priority=MessagePriority.LOW)
        time.sleep(0.01)
        q_crit = r.submit_research_query("crit", priority=MessagePriority.CRITICAL)
        result = r.prioritize_queries([q_low, q_crit], edge_capacity=1)
        assert result[0].query_id == q_crit.query_id

    def test_prioritize_empty(self):
        r = ResearchRelay()
        assert r.prioritize_queries([]) == []

    def test_batch_findings(self):
        r = ResearchRelay()
        findings = [r.submit_edge_finding("j1", {"i": i}) for i in range(15)]
        batches = r.batch_findings(findings, max_batch_size=5)
        assert len(batches) == 3
        assert all(len(b) == 5 for b in batches)

    def test_batch_findings_by_priority(self):
        r = ResearchRelay()
        f_low = r.submit_edge_finding("j1", {"x": 1}, priority=MessagePriority.LOW)
        time.sleep(0.01)
        f_crit = r.submit_edge_finding("j1", {"y": 2}, priority=MessagePriority.CRITICAL)
        batches = r.batch_findings([f_low, f_crit], max_batch_size=1)
        assert batches[0][0].finding_id == f_crit.finding_id

    def test_batch_empty(self):
        r = ResearchRelay()
        assert r.batch_findings([]) == []


# ═══════════════════════════════════════════════════════════════════════════
# 5. Message Routing
# ═══════════════════════════════════════════════════════════════════════════

class TestMessageRouting:
    def _make_msg(self, direction, source="o1", dest="j1"):
        return RelayMessage(
            message_id=f"msg-{time.time()}",
            payload={"test": True},
            direction=direction,
            source=source,
            destination=dest,
        )

    def test_cloud_to_edge_direct(self):
        r = ResearchRelay()
        r.register_edge_node("j1", ["cuda"], {})
        msg = self._make_msg(MessageDirection.CLOUD_TO_EDGE, dest="j1")
        routing = r.route_message(msg)
        assert "direct_to_edge" in routing["route"]

    def test_cloud_to_edge_broadcast(self):
        r = ResearchRelay()
        r.register_edge_node("j1", ["cuda"], {})
        r.register_edge_node("j2", ["sensors"], {})
        msg = self._make_msg(MessageDirection.CLOUD_TO_EDGE, dest="unknown")
        routing = r.route_message(msg)
        assert "broadcast_to_all_edges" in routing["route"]
        assert len(routing["actions"]) == 2

    def test_edge_to_cloud(self):
        r = ResearchRelay()
        msg = self._make_msg(MessageDirection.EDGE_TO_CLOUD, source="j1", dest="cloud")
        routing = r.route_message(msg)
        assert "direct_to_cloud" in routing["route"]

    def test_edge_to_edge_peer(self):
        r = ResearchRelay()
        r.register_edge_node("j1", [], {})
        r.register_edge_node("j2", [], {})
        msg = self._make_msg(MessageDirection.EDGE_TO_EDGE, source="j1", dest="j2")
        routing = r.route_message(msg)
        assert "peer_to_peer" in routing["route"]

    def test_edge_to_edge_not_found(self):
        r = ResearchRelay()
        msg = self._make_msg(MessageDirection.EDGE_TO_EDGE, source="j1", dest="ghost")
        routing = r.route_message(msg)
        assert "no_route" in routing["route"]

    def test_internal_routing(self):
        r = ResearchRelay()
        msg = self._make_msg(MessageDirection.INTERNAL)
        routing = r.route_message(msg)
        assert "internal_processing" in routing["route"]

    def test_routing_logs_message(self):
        r = ResearchRelay()
        msg = self._make_msg(MessageDirection.INTERNAL)
        r.route_message(msg)
        assert len(r.message_log) == 1


# ═══════════════════════════════════════════════════════════════════════════
# 6. ResearchTender
# ═══════════════════════════════════════════════════════════════════════════

class TestResearchTender:
    def test_compress_short_query(self):
        t = ResearchTender()
        result = t.compress_query("Run kernel benchmark", bandwidth_limit=1024)
        assert not result["truncated"]

    def test_compress_long_query(self):
        t = ResearchTender()
        long_q = "First sentence. " * 200
        result = t.compress_query(long_q, bandwidth_limit=100)
        assert result["truncated"]
        assert result["compressed_size"] < result["original_size"]

    def test_compress_empty_query(self):
        t = ResearchTender()
        result = t.compress_query("", bandwidth_limit=100)
        assert result["compressed_query"] == ""
        assert result["original_size"] == 0

    def test_format_finding(self):
        t = ResearchTender()
        result = t.format_finding({"latency_ms": 2.1}, query_id="q1", node_id="j1")
        assert result["query_id"] == "q1"
        assert result["node_id"] == "j1"
        assert result["finding_data"]["latency_ms"] == 2.1

    def test_session_lifecycle(self):
        t = ResearchTender()
        s = t.start_session("s1", "test query")
        assert s["status"] == "active"
        t.add_session_finding("s1", {"result": True})
        c = t.complete_session("s1")
        assert c["status"] == "completed"
        assert len(c["findings_received"]) == 1

    def test_to_dict_from_dict(self):
        t = ResearchTender()
        t.start_session("s1", "q")
        d = t.to_dict()
        t2 = ResearchTender.from_dict(d)
        assert t2.compression_ratio_target == t.compression_ratio_target
        assert "s1" in t2.sessions


# ═══════════════════════════════════════════════════════════════════════════
# 7. DataTender
# ═══════════════════════════════════════════════════════════════════════════

class TestDataTender:
    def test_add_event(self):
        t = DataTender()
        r = t.add_event("model", {"output": 0.9})
        assert r["accepted"] is True
        assert t.pending_count == 1

    def test_dedup_event(self):
        t = DataTender()
        t.add_event("model", {"output": 0.9})
        r = t.add_event("model", {"output": 0.9})
        assert r["accepted"] is False
        assert r["reason"] == "duplicate"
        assert t.dedup_count == 1

    def test_batch_priority_ordering(self):
        t = DataTender()
        t.add_event("general", {"info": "stuff"})
        t.add_event("trust", {"level": 0.9})
        t.add_event("model", {"output": 0.5})
        batches = t.batch(max_batch_size=10)
        assert len(batches) == 1
        assert batches[0][0]["type"] == "trust"     # highest priority
        assert batches[0][1]["type"] == "model"
        assert batches[0][2]["type"] == "general"    # lowest priority

    def test_batch_respects_size_limit(self):
        t = DataTender()
        for i in range(5):
            t.add_event("model", {"i": i})
        batches = t.batch(max_batch_size=2)
        assert len(batches) == 3  # 2 + 2 + 1

    def test_batch_empty(self):
        t = DataTender()
        assert t.batch() == []

    def test_flush(self):
        t = DataTender()
        t.add_event("trust", {"x": 1})
        t.add_event("model", {"y": 2})
        flushed = t.flush()
        assert len(flushed) == 2
        assert t.pending_count == 0

    def test_flush_and_batch(self):
        t = DataTender()
        for i in range(3):
            t.add_event("trust", {"i": i})
        batches = t.flush_and_batch(max_batch_size=2)
        assert len(batches) == 2
        assert t.pending_count == 0

    def test_to_dict_from_dict(self):
        t = DataTender()
        t.add_event("trust", {"x": 1})
        d = t.to_dict()
        assert d["pending_count"] == 1
        t2 = DataTender.from_dict(d)
        assert t2.dedup_count == 0


# ═══════════════════════════════════════════════════════════════════════════
# 8. PriorityTender
# ═══════════════════════════════════════════════════════════════════════════

class TestPriorityTender:
    def test_critical_to_immediate(self):
        t = PriorityTender()
        r = t.cloud_to_edge_urgency(CloudUrgency.CRITICAL)
        assert r["edge_urgency"] == "immediate"
        assert r["escalated"] is False

    def test_low_to_deferred(self):
        t = PriorityTender()
        r = t.cloud_to_edge_urgency(CloudUrgency.LOW)
        assert r["edge_urgency"] == "deferred"

    def test_informational_to_ignored(self):
        t = PriorityTender()
        r = t.cloud_to_edge_urgency(CloudUrgency.INFORMATIONAL)
        assert r["edge_urgency"] == "ignored"

    def test_edge_to_cloud_translation(self):
        t = PriorityTender()
        r = t.edge_to_cloud_urgency(EdgeUrgency.IMMEDIATE)
        assert r["cloud_urgency"] == "critical"

    def test_deferral_escalation(self):
        t = PriorityTender()
        ctx = "kernel-bench"
        # Defer enough times to trigger escalation
        for _ in range(3):
            t.record_deferral(ctx)
        r = t.cloud_to_edge_urgency(CloudUrgency.LOW, context_id=ctx)
        assert r["edge_urgency"] == "queued"  # escalated from deferred
        assert r["escalated"] is True

    def test_no_escalation_below_limit(self):
        t = PriorityTender()
        ctx = "test-ctx"
        t.record_deferral(ctx)
        t.record_deferral(ctx)
        r = t.cloud_to_edge_urgency(CloudUrgency.LOW, context_id=ctx)
        assert r["edge_urgency"] == "deferred"  # not yet escalated
        assert r["escalated"] is False

    def test_reset_deferrals(self):
        t = PriorityTender()
        t.record_deferral("ctx1")
        t.reset_deferrals("ctx1")
        assert t.get_deferral_count("ctx1") == 0

    def test_configure_mapping(self):
        t = PriorityTender()
        t.configure_mapping(CloudUrgency.HIGH, EdgeUrgency.IMMEDIATE)
        r = t.cloud_to_edge_urgency(CloudUrgency.HIGH)
        assert r["edge_urgency"] == "immediate"

    def test_to_dict_from_dict(self):
        t = PriorityTender()
        d = t.to_dict()
        t2 = PriorityTender.from_dict(d)
        assert t2.cloud_to_edge == t.cloud_to_edge


# ═══════════════════════════════════════════════════════════════════════════
# 9. ContextTender
# ═══════════════════════════════════════════════════════════════════════════

class TestContextTender:
    def test_update_and_get_context(self):
        t = ContextTender()
        t.update_context("j1", {"temp": 42, "status": "ok"})
        ctx = t.get_context("j1")
        assert ctx["context"]["temp"] == 42
        assert ctx["version"] == 1

    def test_differential_update(self):
        t = ContextTender()
        t.update_context("j1", {"temp": 42, "status": "ok"})
        diff = t.update_context("j1", {"temp": 43, "status": "ok"})
        assert "temp" in diff["changed_keys"]
        assert "status" not in diff["changed_keys"]
        assert diff["version"] == 2

    def test_sync_diff_no_changes(self):
        t = ContextTender()
        t.update_context("j1", {"x": 1})
        sync = t.sync_diff("j1", since_version=1)
        assert sync["needs_sync"] is False

    def test_sync_diff_full_sync(self):
        t = ContextTender()
        t.update_context("j1", {"x": 1, "y": 2})
        sync = t.sync_diff("j1", since_version=0)
        assert sync["needs_sync"] is True
        assert sync["full_sync"] is True
        assert sync["changes"]["x"] == 1

    def test_sync_diff_version_gap(self):
        t = ContextTender()
        t.update_context("j1", {"v": 1})
        t.update_context("j1", {"v": 2})
        t.update_context("j1", {"v": 3})
        sync = t.sync_diff("j1", since_version=1)
        assert sync["needs_sync"] is True
        assert sync["reason"] == "version_gap_too_large"

    def test_conflict_detection(self):
        t = ContextTender()
        t.update_context("j1", {"v": 1})
        t.update_context("j1", {"v": 2})
        conflict = t.detect_conflict("j1", 1, {"v": "old"})
        assert conflict is not None
        assert conflict["incoming_version"] == 1
        assert conflict["stored_version"] == 2

    def test_no_conflict_when_ahead(self):
        t = ContextTender()
        t.update_context("j1", {"v": 1})
        assert t.detect_conflict("j1", 2, {"v": "new"}) is None

    def test_get_missing_node(self):
        t = ContextTender()
        ctx = t.get_context("ghost")
        assert ctx["context"] == {}
        assert ctx["version"] == 0

    def test_to_dict_from_dict(self):
        t = ContextTender()
        t.update_context("j1", {"x": 1})
        d = t.to_dict()
        assert d["node_count"] == 1
        t2 = ContextTender.from_dict(d)
        assert "j1" in t2.versions


# ═══════════════════════════════════════════════════════════════════════════
# 10. BandwidthBudget
# ═══════════════════════════════════════════════════════════════════════════

class TestBandwidthBudget:
    def test_deliver_within_budget(self):
        b = BandwidthBudget(total_bps=1024)
        msg = BandwidthMessage("m1", payload_size=100, tender_type="research")
        result = b.allocate("research", msg)
        assert result["status"] == "delivered"
        assert result["bytes"] == 100

    def test_queue_when_over_allocation(self):
        b = BandwidthBudget(total_bps=100)
        msg = BandwidthMessage("m1", payload_size=50, tender_type="context")
        result = b.allocate("context", msg)  # context gets 10% = 10 bytes
        assert result["status"] == "queued"

    def test_drop_when_exceeds_total(self):
        b = BandwidthBudget(total_bps=100)
        msg = BandwidthMessage("m1", payload_size=200, tender_type="research")
        result = b.allocate("research", msg)
        assert result["status"] == "dropped"

    def test_adaptive_boost_for_research(self):
        b = BandwidthBudget(total_bps=100)
        b.add_active_session("s1", boost=2.0)
        # research allocation boosted: 30% * (1 + 2.0) = 90% capped at 80%
        msg = BandwidthMessage("m1", payload_size=70, tender_type="research")
        result = b.allocate("research", msg)
        assert result["status"] == "delivered"

    def test_remove_session(self):
        b = BandwidthBudget(total_bps=100)
        b.add_active_session("s1", 1.0)
        b.remove_active_session("s1")
        assert len(b.active_sessions) == 0

    def test_process_overflow(self):
        b = BandwidthBudget(total_bps=100)
        # Queue a message in research (30% = 30 bytes), use 50 bytes to exceed allocation
        msg = BandwidthMessage("m1", payload_size=50, tender_type="research")
        result = b.allocate("research", msg)
        assert result["status"] == "queued"
        assert len(b.overflow_queue) == 1
        # Now boost research allocation so overflow can be delivered
        b.add_active_session("s1", boost=5.0)
        delivered = b.process_overflow(max_messages=5)
        assert len(delivered) == 1
        assert delivered[0]["status"] == "delivered"

    def test_preempt_low_priority(self):
        b = BandwidthBudget(total_bps=100)
        b.overflow_queue = [
            BandwidthMessage("low1", 10, priority=4, tender_type="general"),
            BandwidthMessage("crit1", 10, priority=0, tender_type="priority"),
            BandwidthMessage("low2", 10, priority=3, tender_type="general"),
        ]
        b.queued_bytes = 30
        dropped = b.preempt(max_priority=3)
        assert len(dropped) == 2  # priority 3 and 4 dropped
        assert len(b.overflow_queue) == 1  # critical kept

    def test_set_allocation(self):
        b = BandwidthBudget(total_bps=1024)
        b.set_allocation("context", 0.5)
        assert b.base_allocations["context"] == 0.5

    def test_available_bandwidth(self):
        b = BandwidthBudget(total_bps=1024)
        info = b.available_bandwidth()
        assert info["total_bps"] == 1024
        assert "allocated_tenders" in info

    def test_to_dict_from_dict(self):
        b = BandwidthBudget(total_bps=2048)
        d = b.to_dict()
        b2 = BandwidthBudget.from_dict(d)
        assert b2.total_bps == 2048


# ═══════════════════════════════════════════════════════════════════════════
# 11. Integration: Full Cloud→Edge→Cloud Round Trip
# ═══════════════════════════════════════════════════════════════════════════

class TestIntegration:
    def test_full_round_trip(self):
        """Cloud submits query → compressed for edge → edge processes →
        finding expanded for cloud → batched for consumption."""
        relay = ResearchRelay()
        tender = ResearchTender()
        data_tender = DataTender()

        # 1. Register participants
        relay.register_cloud_source("oracle1", ["architecture"])
        relay.register_edge_node("jetson1", ["cuda", "sensors"], {"vram": 8192})

        # 2. Cloud submits research query
        query = relay.submit_research_query(
            "Benchmark matrix multiplication kernel on Orin with 4096x4096 matrices",
            source_id="oracle1",
            priority=MessagePriority.HIGH,
        )
        assert query.status == "pending"

        # 3. Compress for edge (use a larger payload to ensure truncation)
        large_data = {
            "query": query.query_text,
            "params": {"matrix_size": 4096},
            "background": "This is extensive cloud context about the fleet. " * 20,
            "metadata": {"author": "oracle1", "history": "a" * 500},
        }
        compressed = relay.compress_for_edge(large_data, bandwidth_limit=128)
        assert compressed["truncated"] is True

        # 4. Start research session
        session = tender.start_session("bench-001", query.query_text)
        assert session["status"] == "active"

        # 5. Edge produces finding
        finding = relay.submit_edge_finding(
            "jetson1",
            {"kernel_ms": 12.4, "memory_mb": 512, "throughput_gflops": 8.7},
            query_id=query.query_id,
            priority=MessagePriority.HIGH,
        )

        # 6. Expand for cloud
        expanded = relay.expand_from_edge(finding.data)
        assert expanded["data"]["kernel_ms"] == 12.4
        assert expanded["edge_nodes_count"] == 1

        # 7. Format finding via tender
        formatted = tender.format_finding(
            finding.data, query_id=query.query_id, node_id="jetson1"
        )

        # 8. Add as event and batch
        data_tender.add_event("model", formatted)
        batches = data_tender.flush_and_batch(max_batch_size=5)
        assert len(batches) == 1
        assert batches[0][0]["type"] == "model"

        # 9. Complete session
        tender.complete_session("bench-001")
        assert tender.sessions["bench-001"]["status"] == "completed"


# ═══════════════════════════════════════════════════════════════════════════
# 12. Edge Cases
# ═══════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_relay_empty_state(self):
        r = ResearchRelay()
        assert len(r.cloud_sources) == 0
        assert len(r.edge_nodes) == 0
        assert len(r.queries) == 0
        assert len(r.findings) == 0
        d = r.to_dict()
        assert d["queries_count"] == 0

    def test_relay_no_registered_nodes_route(self):
        r = ResearchRelay()
        msg = RelayMessage("m1", {}, MessageDirection.CLOUD_TO_EDGE, "o1", "j1")
        routing = r.route_message(msg)
        assert "broadcast_to_all_edges" in routing["route"]
        assert len(routing["actions"]) == 0  # no nodes to broadcast to

    def test_bandwidth_zero(self):
        b = BandwidthBudget(total_bps=0)
        msg = BandwidthMessage("m1", payload_size=10, tender_type="research")
        result = b.allocate("research", msg)
        assert result["status"] == "dropped"

    def test_compression_with_none_data(self):
        r = ResearchRelay()
        result = r.compress_for_edge(None, bandwidth_limit=100)
        # Should handle gracefully without crashing
        assert "compressed_size" in result

    def test_data_tender_batch_byte_limit(self):
        t = DataTender()
        # Add a large event
        t.add_event("model", {"huge": "x" * 5000})
        batches = t.batch(max_batch_size=10, max_bytes=100)
        # Should still produce at least one batch
        assert len(batches) >= 1

    def test_context_tender_empty_sync(self):
        t = ContextTender()
        sync = t.sync_diff("ghost", since_version=0)
        assert sync["needs_sync"] is False

    def test_priority_tender_deferral_unknown_context(self):
        t = PriorityTender()
        # Should not crash on unknown context
        assert t.get_deferral_count("unknown") == 0

    def test_research_tender_complete_nonexistent_session(self):
        t = ResearchTender()
        result = t.complete_session("nonexistent")
        assert result == {}

    def test_research_tender_add_finding_nonexistent_session(self):
        t = ResearchTender()
        # Should not crash
        t.add_session_finding("nonexistent", {"data": True})

    def test_bandwidth_preempt_empty_queue(self):
        b = BandwidthBudget(total_bps=100)
        dropped = b.preempt()
        assert dropped == []

    def test_relay_prioritize_with_zero_capacity(self):
        r = ResearchRelay()
        q = r.submit_research_query("test")
        assert r.prioritize_queries([q], edge_capacity=0) == []

    def test_message_to_dict_from_dict(self):
        msg = RelayMessage(
            message_id="test-msg",
            payload={"key": "val"},
            direction=MessageDirection.EDGE_TO_CLOUD,
            source="j1",
            destination="cloud",
        )
        d = msg.to_dict()
        msg2 = RelayMessage.from_dict(d)
        assert msg2.message_id == "test-msg"
        assert msg2.direction == MessageDirection.EDGE_TO_CLOUD
