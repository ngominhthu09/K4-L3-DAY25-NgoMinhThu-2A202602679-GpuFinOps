"""M2 — Inference Cost Levers: $/1M-token, batch x cache x cascade (deck §7).

Run: python missions/m2_inference_levers.py
"""
from __future__ import annotations
import math
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from missions._common import load_csv, num
from finops import pricing, sustainability

# $/1M tokens (input, output) — illustrative 2026.
MODEL_PRICES = {"small": (0.20, 0.40), "large": (3.00, 15.00)}


def run(verbose: bool = True) -> dict:
    rows = load_csv("token_usage.csv")
    base_cost = opt_cost = 0.0
    cascade_cost = cache_cost = 0.0
    total_tokens = 0
    reasoning = []
    reasoning_spend = non_reasoning_spend = 0.0
    reasoning_wh = non_reasoning_wh = 0.0
    reasoning_tokens = non_reasoning_tokens = 0
    reasoning_requests = non_reasoning_requests = 0
    for r in rows:
        inp, out = int(num(r["input_tokens"])), int(num(r["output_tokens"]))
        cached = int(num(r["cached_input_tokens"]))
        is_batch = bool(int(num(r["is_batch"])))
        total_tokens += inp + out
        # BASELINE: naive deployment — everything on the large model, no cache, no batch
        lin, lout = MODEL_PRICES["large"]
        base_cost += pricing.request_cost(inp, out, lin, lout)
        # OPTIMIZED: cascade (route_tier), prompt caching, batch API
        pin, pout = MODEL_PRICES[r["route_tier"]]
        cascade_cost += pricing.request_cost(inp, out, pin, pout)
        cache_cost += pricing.request_cost(inp, out, pin, pout, cached_in=cached)
        request_opt_cost = pricing.request_cost(
            inp, out, pin, pout, cached_in=cached, batch=is_batch
        )
        opt_cost += request_opt_cost
        is_reasoning = bool(int(num(r["is_reasoning"])))
        query_wh = sustainability.wh_per_query(inp + out, is_reasoning=is_reasoning)
        if is_reasoning:
            reasoning_spend += request_opt_cost
            reasoning_wh += query_wh
            reasoning_tokens += inp + out
            reasoning_requests += 1
            reasoning.append({"output_tokens": out, "tokens": inp + out, "wh": query_wh})
        else:
            non_reasoning_spend += request_opt_cost
            non_reasoning_wh += query_wh
            non_reasoning_tokens += inp + out
            non_reasoning_requests += 1

    base_pm = pricing.dollars_per_million(base_cost, total_tokens)
    opt_pm = pricing.dollars_per_million(opt_cost, total_tokens)
    savings_pct = (1 - opt_cost / base_cost) * 100 if base_cost else 0.0
    lever_breakdown = {
        "cascade": base_cost - cascade_cost,
        "cache": cascade_cost - cache_cost,
        "batch": cache_cost - opt_cost,
    }

    # Keep reasoning for the requests with the largest outputs when enforcing a
    # 10% request budget. The synthetic price catalog does not add an API price
    # premium for reasoning, so dollar impact below is electricity cost only.
    reasoning_cap_pct = 10.0
    cap_count = math.floor(len(rows) * reasoning_cap_pct / 100.0)
    retained_reasoning = sorted(
        reasoning, key=lambda item: item["output_tokens"], reverse=True
    )[:cap_count]
    retained_wh = sum(item["wh"] for item in retained_reasoning)
    reasoning_wh_if_plain = sum(
        item["wh"] / sustainability.REASONING_ENERGY_MULTIPLIER
        for item in reasoning
    )
    incremental_reasoning_wh = reasoning_wh - reasoning_wh_if_plain
    capped_reasoning_wh = retained_wh + sum(
        item["wh"] / sustainability.REASONING_ENERGY_MULTIPLIER
        for item in sorted(reasoning, key=lambda item: item["output_tokens"], reverse=True)[cap_count:]
    )
    ordered_reasoning = sorted(
        reasoning, key=lambda item: item["output_tokens"], reverse=True
    )
    capped_reasoning_tokens = sum(item["tokens"] for item in ordered_reasoning[:cap_count])
    capped_reasoning_count = min(len(reasoning), cap_count)
    capped_energy_savings_wh = reasoning_wh - capped_reasoning_wh
    electricity_rate = sustainability.REGION_PRICE_KWH["us-east-1"]
    reasoning_analysis = {
        "request_count": len(rows),
        "reasoning_count": len(reasoning),
        "reasoning_tokens": reasoning_tokens,
        "reasoning_request_share_pct": (len(reasoning) / len(rows) * 100) if rows else 0.0,
        "reasoning_spend": reasoning_spend,
        "reasoning_spend_share_pct": (reasoning_spend / opt_cost * 100) if opt_cost else 0.0,
        "reasoning_wh": reasoning_wh,
        "reasoning_total_energy_wh": reasoning_wh + non_reasoning_wh,
        "non_reasoning_count": non_reasoning_requests,
        "non_reasoning_tokens": non_reasoning_tokens,
        "non_reasoning_spend": non_reasoning_spend,
        "non_reasoning_wh": non_reasoning_wh,
        "reasoning_incremental_wh": incremental_reasoning_wh,
        "reasoning_incremental_electricity_usd": incremental_reasoning_wh / 1000 * electricity_rate,
        "cap_request_count": cap_count,
        "cap_pct": reasoning_cap_pct,
        "reasoning_count_after_cap": capped_reasoning_count,
        "reasoning_tokens_after_cap": capped_reasoning_tokens,
        "capped_reasoning_wh": capped_reasoning_wh,
        "total_energy_after_cap_wh": non_reasoning_wh + capped_reasoning_wh,
        "api_cost_before_cap": opt_cost,
        "api_cost_after_cap": opt_cost,
        "api_cost_savings_from_cap": 0.0,
        "cap_energy_savings_wh": capped_energy_savings_wh,
        "cap_electricity_savings_usd": capped_energy_savings_wh / 1000 * electricity_rate,
    }

    if verbose:
        print("== M2 Inference Cost Levers ==")
        print(f"requests={len(rows)}  tokens={total_tokens:,}")
        print(f"baseline  : ${base_cost:,.2f}/day   ${base_pm:.3f}/1M-token")
        print(f"optimized : ${opt_cost:,.2f}/day   ${opt_pm:.3f}/1M-token")
        print(f"savings   : {savings_pct:.1f}%  (cascade + caching + batch)")
        print("sequential lever savings (per day): "
              + ", ".join(f"{name} ${amount:,.2f}" for name, amount in lever_breakdown.items()))
        print(f"discount stack (batch + 100% cache): {pricing.discount_stack(batch=True, cache_hit_frac=1.0):.3f} of naive")
        print("reasoning budget:")
        print(f"  traffic={reasoning_analysis['reasoning_request_share_pct']:.1f}%  "
              f"optimized-spend-share={reasoning_analysis['reasoning_spend_share_pct']:.1f}%")
        print(f"  tokens={reasoning_tokens:,}  API spend=${reasoning_spend:.2f} "
              f"(non-reasoning ${non_reasoning_spend:.2f})")
        print(f"  energy={reasoning_wh:,.1f} Wh; incremental electricity="
              f"${reasoning_analysis['reasoning_incremental_electricity_usd']:.4f}")
        print(f"  cap at {reasoning_cap_pct:.0f}%: save {capped_energy_savings_wh:,.1f} Wh / "
              f"${reasoning_analysis['cap_electricity_savings_usd']:.4f} electricity")
        print(f"  API spend after cap=${reasoning_analysis['api_cost_after_cap']:.2f} "
              f"(API savings ${reasoning_analysis['api_cost_savings_from_cap']:.2f})")

    return {
        "baseline_daily": round(base_cost, 2), "optimized_daily": round(opt_cost, 2),
        "baseline_per_m": round(base_pm, 3), "optimized_per_m": round(opt_pm, 3),
        "savings_pct": round(savings_pct, 1), "total_tokens": total_tokens,
        "reasoning_analysis": reasoning_analysis, "lever_breakdown": lever_breakdown,
    }


if __name__ == "__main__":
    run()
