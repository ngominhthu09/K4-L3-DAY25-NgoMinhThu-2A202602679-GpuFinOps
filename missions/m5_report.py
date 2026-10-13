"""M5 — Optimization Report: combine M1-M4 into baseline-vs-optimized (deck §1/§11).

Run: python missions/m5_report.py   ->  outputs/report.md + outputs/savings.png
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import os
from missions._common import num, catalog_by_type, ROOT
from finops import report, sustainability
from missions import m1_efficiency_audit, m2_inference_levers, m3_purchasing, carbon_schedule

DAYS = 30
# one tier down for over-provisioned ("util-lie") GPUs
RIGHTSIZE_MAP = {"H100": "A100", "H200": "H100", "A100": "A10G", "A10G": "L4", "L4": "L4"}


def run(verbose: bool = True) -> dict:
    r1 = m1_efficiency_audit.run(verbose=False)
    r2 = m2_inference_levers.run(verbose=False)
    r3 = m3_purchasing.run(verbose=False)
    rcarbon = carbon_schedule.run(verbose=False)
    cat = catalog_by_type()

    # --- buckets ---
    infer_savings = (r2["baseline_daily"] - r2["optimized_daily"]) * DAYS
    purchasing_savings = r3["on_demand_monthly"] - r3["optimized_monthly"]

    idle_savings = r1["idle_waste_daily"] * DAYS
    rightsize_savings = 0.0
    for lie in r1["lies"]:
        cur = lie["gpu_type"]
        tgt = RIGHTSIZE_MAP.get(cur, cur)
        delta = num(cat[cur]["on_demand_hr"]) - num(cat[tgt]["on_demand_hr"])
        rightsize_savings += max(0.0, delta) * 24 * DAYS

    levers = {
        "Inference (cascade/cache/batch)": round(infer_savings),
        "Purchasing (spot/reserved)": round(purchasing_savings),
        "Right-size util-lies": round(rightsize_savings),
        "Kill idle GPUs": round(idle_savings),
    }
    baseline = r2["baseline_daily"] * DAYS + r3["on_demand_monthly"]
    optimized = baseline - sum(levers.values())
    total_pct = sum(levers.values()) / baseline * 100 if baseline else 0.0

    # --- sustainability snapshot ---
    median_tokens = 800
    wh = sustainability.wh_per_query(median_tokens)
    sust = {
        "wh_per_query": wh,
        "carbon_g": sustainability.carbon_g(wh, "us-east-1"),
        "best_region": min(sustainability.REGION_CARBON, key=sustainability.REGION_CARBON.get),
    }

    reasoning = r2["reasoning_analysis"]
    carbon_job_lines = [
        "| Job | us-east-1 (gCO2e) | europe-north1 (gCO2e) | Saved (gCO2e) |",
        "|---|---:|---:|---:|",
    ]
    carbon_job_lines.extend(
        f"| {job['job_id']} | {job['base_carbon_g']:,.0f} | "
        f"{job['clean_carbon_g']:,.0f} | {job['carbon_saved_g']:,.0f} |"
        for job in rcarbon["job_rows"]
    )
    carbon_region_lines = [
        "| Region | $/kWh | gCO2/kWh | Electricity cost ($) | Carbon (gCO2e) |",
        "|---|---:|---:|---:|---:|",
    ]
    carbon_region_lines.extend(
        f"| {region['region']} | {region['price_usd_per_kwh']:.3f} | "
        f"{region['carbon_g_per_kwh']:.0f} | {region['electricity_usd']:,.2f} | "
        f"{region['carbon_g']:,.0f} |"
        for region in rcarbon["region_rows"]
    )
    extension_results = {
        "Reasoning budget": [
            f"Reasoning: {reasoning['reasoning_count']:,} requests, {reasoning['reasoning_tokens']:,} tokens, "
            f"${reasoning['reasoning_spend']:,.2f} optimized API cost, {reasoning['reasoning_wh']:,.1f} Wh.",
            f"Non-reasoning: {reasoning['non_reasoning_count']:,} requests, "
            f"{reasoning['non_reasoning_tokens']:,} tokens, ${reasoning['non_reasoning_spend']:,.2f} "
            f"optimized API cost, {reasoning['non_reasoning_wh']:,.1f} Wh.",
            f"Reasoning is {reasoning['reasoning_request_share_pct']:.1f}% of requests and "
            f"{reasoning['reasoning_spend_share_pct']:.1f}% of optimized API cost. Its extra energy "
            f"over the same requests run as plain queries is {reasoning['reasoning_incremental_wh']:,.1f} Wh "
            f"(estimated ${reasoning['reasoning_incremental_electricity_usd']:.4f} electricity at us-east-1).",
            f"At the {reasoning['cap_pct']:.0f}% traffic cap, before/after API cost is "
            f"${reasoning['api_cost_before_cap']:,.2f}/${reasoning['api_cost_after_cap']:,.2f}; "
            f"total energy is {reasoning['reasoning_total_energy_wh']:,.1f}/"
            f"{reasoning['total_energy_after_cap_wh']:,.1f} Wh and energy saved is "
            f"{reasoning['cap_energy_savings_wh']:,.1f} Wh. Existing traffic is already below the cap, "
            "so the policy makes no routing changes.",
            "The model does not price reasoning tokens separately; API-cost savings from this cap are $0. "
            "Electricity estimates use the lab's energy model and us-east-1 rate.",
        ],
        "Carbon-aware scheduling": [
            rcarbon["period_note"],
            "Each interruptible job: us-east-1 baseline compared with the cleanest region (europe-north1):",
            "",
            *carbon_job_lines,
            "",
            "Same workload total compared across all five regions:",
            "",
            *carbon_region_lines,
            "",
            f"Cheapest: {rcarbon['cheapest_region']}; cleanest: {rcarbon['clean_region']}. "
            f"Moving interruptible jobs from us-east-1 to europe-north1 saves "
            f"{rcarbon['carbon_saved_g']:,.0f} gCO2e ({rcarbon['carbon_saved_pct']:.1f}%) and "
            f"${rcarbon['electricity_savings_usd']:,.2f} electricity.",
            "Assumes jobs can move without changing GPU-hours; latency and data residency are not modeled.",
        ],
    }
    md = report.build_report(
        baseline, optimized, levers, sustainability=sust,
        unit_economics=r2, extensions=extension_results,
    )
    out_md = os.path.join(ROOT, "outputs", "report.md")
    os.makedirs(os.path.dirname(out_md), exist_ok=True)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(md)
    png = report.savings_waterfall(levers, os.path.join(ROOT, "outputs", "savings.png"))

    if verbose:
        print("== M5 Optimization Report ==")
        print(md)
        print(f"\nWritten: outputs/report.md" + (f" + outputs/savings.png" if png else " (matplotlib absent: PNG skipped)"))

    return {"baseline_monthly": round(baseline), "optimized_monthly": round(optimized),
            "levers": levers, "total_savings_pct": round(total_pct, 1)}


if __name__ == "__main__":
    run()
