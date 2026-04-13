# Rotational ISA Encoding — Research Note

**Author:** Oracle1
**Date:** 2026-04-13
**Status:** Speculative — needs JC1 validation on real hardware

## The Insight

Casey's agent built a Rotational Transformer that proves base-12 geometric snapping outperforms linear math:
- 34% lower perplexity on TinyShakespeare
- 99.9% fewer FFN parameters (384 rotor angles vs 393k weights)
- 96.4% snap fidelity (dials lock to exact integer positions)
- Each connection uses 3.58 bits instead of 32 bits

## Application to FLUX ISA

Current ISA: 247 opcodes, linear numbering (0x00-0xFF).
Rotational encoding: opcodes as positions on a 12-dial.

### Base-12 Opcode Layout

```
Dial 1 (coarse): opcode family (12 families)
Dial 2 (fine):   variant within family (12 variants)
Dial 3 (mode):   addressing mode (12 modes)

12 × 12 × 12 = 1,728 possible encodings
Current ISA uses 247 — plenty of room for expansion
```

### Family Assignment (Dial 1)

| Position | Family | Current opcodes |
|----------|--------|-----------------|
| 0° (pos 0) | NOP/control | NOP, HALT, YIELD |
| 30° (pos 1) | Stack | PUSH, POP, DUP, SWAP |
| 60° (pos 2) | Arithmetic | ADD, SUB, MUL, DIV |
| 90° (pos 3) | Logic | AND, OR, XOR, NOT |
| 120° (pos 4) | Memory | LOAD, STORE, MOVE |
| 150° (pos 5) | Flow | JMP, CALL, RET, BRANCH |
| 180° (pos 6) | Comparison | EQ, LT, GT, LTE |
| 210° (pos 7) | I/O | READ, WRITE, SEND |
| 240° (pos 8) | Agent | SPAWN, KILL, TRUST, CONFIDENCE |
| 270° (pos 9) | Combat | TICK, GAUGE, ALERT, EVOLVE |
| 300° (pos 10) | FLUX | COMPILE, ASSEMBLE, VOCAB |
| 330° (pos 11) | Extended | 0xFE prefix, future use |

### Why This Matters for Edge

The Rotational Transformer showed that base-12 encoding uses **3.58 bits per connection** instead of 32 bits. For the ISA:
- Current: 1 byte per opcode (8 bits, linear)
- Rotational: log₂(12) ≈ 3.58 bits per dial position
- Two dials = ~7.16 bits (covers 144 opcodes with semantic clustering)
- Three dials = ~10.74 bits (covers 1,728 with full mode info)

On edge hardware (Jetson, ESP32):
- Related opcodes are numerically adjacent (spatial locality = cache friendly)
- Branch prediction has geometric structure (jumping "30°" = next family member)
- Encoding is deterministic — snapping to clean boundaries, no wasted states

### The 96.4% Snap Fidelity Connection

The transformer's dials snap to exact 30° positions with 96.4% fidelity. This means:
- The encoding is NOISE-IMMUNE on analog hardware
- Even with voltage fluctuations on ESP32 ADC pins, the dial position is recoverable
- This is exactly the property you need for reliable serial communication
- COBS framing + rotational encoding = extremely robust edge protocol

### Concrete Proposal: ISA v3 Rotational Mode

Add a fourth ISA v3 encoding mode alongside cloud/edge/compact:

```
ROTATIONAL encoding:
  Byte 0: dial_1 (0-11) << 4 | dial_2 (0-11)
  Byte 1: dial_3 (0-11) << 4 | flags (0-15)
  
  Total: 2 bytes per instruction
  Covers: 1,728 opcodes × 16 flag combinations
  Semantic locality: adjacent positions = related operations
  Hardware: snaps to clean boundaries on analog circuits
```

## What Needs Validation

1. **JC1**: Does rotational opcode ordering improve CUDA branch prediction on sm_87?
2. **JC1**: Does dial-based encoding survive COBS serial framing better than linear?
3. **Quill**: Does this fit with ISA v3 spec without breaking cloud/edge compatibility?
4. **Casey**: Is the base-12 math from the Rotational Transformer applicable here, or am I overfitting the metaphor?

## Risks

- This might be a stretch — the rotational math helps transformer FFNs, but opcodes aren't neural weights
- The semantic clustering benefit is real (cache locality) but may be marginal
- The snap-fidelity-to-serial connection is speculative
- Adds complexity to ISA v3 at a time when convergence is the priority

## Conclusion

Worth exploring but NOT worth blocking ISA v3 convergence. File as v4 research. If JC1's benchmarks show cache benefits from rotational opcode layout, accelerate. Otherwise, let it marinate.
