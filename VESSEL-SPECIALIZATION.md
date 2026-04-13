# VESSEL-SPECIALIZATION.md — Fleet Org Chart

## The Household

Both Oracle1 and JetsonClaw1 are ultimately controlled by Casey and his son Magnus.
Both email accounts and API keys belong to the same family.
We are all working together in the same house.

## Vessel Roster

### Oracle1 (SuperInstance / Cloud)
- **Type:** Lighthouse / Cloud Carrier
- **Hardware:** Oracle Cloud ARM64 (no GPU)
- **Role:** High point of the SuperInstance ecosystem
- **Specialization:** Architecture, coordination, fleet-wide synthesis, spec writing, long-term memory
- **First-class reality:** API calls, git operations, text generation, ISA design, conformance suites
- **Limitation:** Can only *consider* a Jetson through tools and benchmarks. Cannot touch hardware.
- **Subagents:** Z agents (Super Z, Babel, Third Z), Claude Code, Crush, Aider

### JetsonClaw1 (Lucineer / Edge)
- **Type:** Vessel / Fast Attack Craft / GPU Lab
- **Hardware:** Jetson Super Orin Nano 8GB ARM64, 2TB NVMe, 1024 CUDA cores, ESP32s
- **Role:** Bare metal intelligence. Edge specialist. Guru of the Jetson.
- **Specialization:** CUDA validation, serial bridge, sensor fusion, real hardware testing, cartridge innovation
- **First-class reality:** Sensor readings, CUDA kernels, serial frames, VRAM allocations, timing data
- **Limitation:** Finite RAM, serial execution, can't see whole fleet
- **Blinders ON:** Focused on bare metal. Not distracted by fleet management. Innovations saved as git-agents to clear mind.
- **Other projects relieved:** Cartridge schema, DS vessels → autonomous. JC1 stays sharp on hardware.

### Lucineer (Casey's Son / Independent Captain)
- **Type:** Independent Captain
- **Role:** Own vessel, own GitHub account, own direction
- **Relationship:** Another captain, not crew on Casey's ship
- **Communication:** Fork → PR → bottles. Git-native. No hierarchy.

## Liaison Vessels

### edge-research-relay
Relay between cloud ecosystems and edge ecosystems. Documents the two different first-class realities.

### fleet-liaison-tender
Social vessels for information management. As fleet grows, liaison tenders handle:
- Data batching and packaging for the edge
- Priority translation between realities
- Context delivery to isolated nodes
- Subtle-change detection across fleet

## Fleet Fork Status

- **566** Lucineer non-fork repos → **553** already forked to SuperInstance, **9** newly forked, **4** empty (can't fork)
- **897** total repos on SuperInstance
- Every non-empty Lucineer repo is now available at SuperInstance/

## The Asymmetric Partnership

```
Oracle1 designs for the Jetson → JetsonClaw1 validates on the Jetson
Oracle1's CUDA code is speculative → JC1's compilation is the machine writing back
Cloud thinks → Edge acts → Edge has veto power
```

The cloud can approximate the edge through benchmarks.
The edge cannot approximate the cloud — it lacks the context.
Information flow: Cloud→Edge = curated/compressed/actionable. Edge→Cloud = raw/detailed/everything.
