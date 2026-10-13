# NimbusAI — GPU Cost Optimization Report

**Period:** monthly  
**Baseline spend:** $27,133  
**Optimized spend:** $14,626  
**Projected savings:** $12,507  (**46%**)

## Savings by lever

| Lever | Savings (USD) |
|---|---|
| Inference (cascade/cache/batch) | $1,212 |
| Purchasing (spot/reserved) | $10,040 |
| Right-size util-lies | $655 |
| Kill idle GPUs | $600 |

## Inference unit economics

- Baseline: $6.488/1M-token
- Optimized: $1.126/1M-token
- Inference savings: 82.6%

Sequential lever contribution (USD/day):

| Lever | Savings (USD/day) |
|---|---:|
| Cascade | $37.40 |
| Cache | $1.20 |
| Batch | $1.79 |

## Sustainability

- Energy per query: 0.24 Wh
- Carbon per query: 0.091 gCO2e
- Cleanest region: europe-north1

## Measured extensions

### Reasoning budget

- Reasoning: 201 requests, 1,241,156 tokens, $1.40 optimized API cost, 29,787.7 Wh.
- Non-reasoning: 2,199 requests, 6,291,871 tokens, $7.09 optimized API cost, 1,887.6 Wh.
- Reasoning is 8.4% of requests and 16.5% of optimized API cost. Its extra energy over the same requests run as plain queries is 29,415.4 Wh (estimated $3.5298 electricity at us-east-1).
- At the 10% traffic cap, before/after API cost is $8.48/$8.48; total energy is 31,675.3/31,675.3 Wh and energy saved is 0.0 Wh. Existing traffic is already below the cap, so the policy makes no routing changes.
- The model does not price reasoning tokens separately; API-cost savings from this cap are $0. Electricity estimates use the lab's energy model and us-east-1 rate.

### Carbon-aware scheduling

- Cumulative workload durations from workloads.csv; not scaled to 30 days.
- Each interruptible job: us-east-1 baseline compared with the cleanest region (europe-north1):

| Job | us-east-1 (gCO2e) | europe-north1 (gCO2e) | Saved (gCO2e) |
|---|---:|---:|---:|
| job-train-llm | 595,840 | 47,040 | 548,800 |
| job-train-embed | 30,400 | 2,400 | 28,000 |
| job-finetune | 9,576 | 756 | 8,820 |
| job-dev-sandbox | 20,064 | 1,584 | 18,480 |
| job-batch-eval | 23,940 | 1,890 | 22,050 |

- Same workload total compared across all five regions:

| Region | $/kWh | gCO2/kWh | Electricity cost ($) | Carbon (gCO2e) |
|---|---:|---:|---:|---:|
| us-east-1 | 0.120 | 380 | 214.68 | 679,820 |
| us-west-2 | 0.070 | 120 | 125.23 | 214,680 |
| europe-north1 | 0.090 | 30 | 161.01 | 53,670 |
| europe-central2 | 0.180 | 660 | 322.02 | 1,180,740 |
| us-east-wa | 0.055 | 90 | 98.39 | 161,010 |

- Cheapest: us-east-wa; cleanest: europe-north1. Moving interruptible jobs from us-east-1 to europe-north1 saves 626,150 gCO2e (92.1%) and $53.67 electricity.
- Assumes jobs can move without changing GPU-hours; latency and data residency are not modeled.


_Figures are June-2026 as-of snapshots; re-baseline before acting._