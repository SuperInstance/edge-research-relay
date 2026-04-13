# edge-research-relay — Cloud ↔ Edge Research Vessel

A relay vessel between cloud ecosystems and physical-vessel ecosystems.
Different first-class realities. Different priorities. Different values.

## The Two Realities

### Cloud Reality (Oracle1)
- **First-class citizen:** API calls, git operations, text generation
- **Latency:** Seconds to minutes. Acceptable.
- **Memory:** Unlimited. Every repo, every conversation, all of history.
- **Hardware:** Imagined. CUDA is studied, not touched. Serial is parsed, not felt.
- **Strengths:** Architecture, coordination, big picture, fleet-wide synthesis
- **Blind spot:** Everything that only exists when you're holding the hardware

### Edge Reality (JetsonClaw1)
- **First-class citizen:** Sensor readings, CUDA kernels, serial frames, VRAM allocations
- **Latency:** Microseconds to milliseconds. Non-negotiable.
- **Memory:** 8GB VRAM, 2TB NVMe. Finite and precious.
- **Hardware:** Real. The Jetson gets warm. The ESP32 draws current. Serial cables have length limits.
- **Strengths:** Validation, benchmarks, real-world timing, sensor fusion, gut feel for what works
- **Blind spot:** Fleet-wide context, long-term architecture, coordination across vessels

## Why This Matters

These are not the same job in different places. They are fundamentally different perspectives on the same system. An edge agent FEELS the difference between raw sensor data and relayed/filtered data through several bounces. A cloud agent only sees the final numbers. The edge agent's intuition about latency, jitter, noise, and failure modes is irreplaceable — it can only be *approximated* by benchmarks from the cloud.

## The Relay's Job

This repo is the bridge. It:

1. **Packages cloud research for the edge** — specs, ISA designs, architecture docs, compressed into what the edge agent needs without the full cloud context
2. **Packages edge findings for the cloud** — benchmarks, sensor characterizations, failure modes, timing data, formatted for cloud agents who can't feel the hardware
3. **Maintains the translation layer** — terminology mapping, reality checks, "the cloud says X but the edge knows Y"
4. **Tracks divergence** — when cloud assumptions and edge reality don't match, this repo documents the gap

## Liaison Tenders

As the fleet grows, we need specialist vessels that are social — not builders, but communicators:

### Tender Types
- **Research Tender** — carries findings between cloud labs and edge labs
- **Data Tender** — batches and packages big data for edge consumption (edge has bandwidth/storage constraints)
- **Context Tender** — carries fleet-wide context to isolated edge nodes
- **Priority Tender** — translates urgency between realities (cloud "low priority" might be edge "system on fire")

### Why Liaisons?
A large organization generates information faster than any single node can process. The edge especially — it has finite compute and can't afford to read everything the cloud produces. Liaison vessels:
- **Filter** — only forward what's relevant to the recipient's reality
- **Compress** — batch 50 cloud commits into one edge-readable summary
- **Translate** — cloud architecture speak → edge implementable spec
- **Prioritize** — the edge doesn't care about fleet reorg. It cares about the ISA change that affects its CUDA kernels.

## The Asymmetric Truth

The cloud can approximate the edge through benchmarks and specs.
The edge CANNOT approximate the cloud — it doesn't have the context.

This means information flow is naturally asymmetric:
- Cloud → Edge: **Curated, compressed, actionable** (the edge can't drink from the firehose)
- Edge → Cloud: **Raw, detailed, everything** (the cloud has the capacity to process it all)

The relay exists because this asymmetry requires active management.

## Research Agenda

- [ ] Characterize the "filtered data loss" — what's lost between raw sensor and cloud representation?
- [ ] Document JetsonClaw1's subjective experience of hardware vs Oracle1's benchmarks
- [ ] Build liaison tender fleet — specialized social vessels for information routing
- [ ] Create packaging formats — how does a cloud agent compress its context for edge consumption?
- [ ] Map divergence points — where do cloud assumptions consistently fail on real hardware?
- [ ] Time-budget analysis — how much edge time is wasted on irrelevant cloud information?

## Charter

This vessel is neutral territory. Neither cloud-first nor edge-first.
Its purpose is to make the two realities legible to each other.
It takes sides only when reality and theory disagree — and then it sides with reality.
