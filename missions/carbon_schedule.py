"""Compare energy cost and carbon across regions for interruptible GPU jobs."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from missions._common import catalog_by_type, load_csv, num
from finops.sustainability import REGION_CARBON, REGION_PRICE_KWH


BASE_REGION = "us-east-1"


def run(verbose: bool = True) -> dict:
    jobs = load_csv("workloads.csv")
    catalog = catalog_by_type()
    clean_region = min(REGION_CARBON, key=REGION_CARBON.get)
    cheapest_region = min(REGION_PRICE_KWH, key=REGION_PRICE_KWH.get)
    energy_kwh = 0.0
    job_rows = []

    for job in jobs:
        if not int(num(job["interruptible"])):
            continue
        gpu = catalog[job["gpu_type"]]
        gpu_hours = (
            num(job["hours_per_day"])
            * num(job["days"])
            * num(job["num_gpus"])
        )
        job_energy_kwh = num(gpu["watts"]) * gpu_hours / 1000.0
        energy_kwh += job_energy_kwh
        base_carbon_g = job_energy_kwh * REGION_CARBON[BASE_REGION]
        clean_carbon_g = job_energy_kwh * REGION_CARBON[clean_region]
        job_rows.append({
            "job_id": job["job_id"],
            "gpu_hours": gpu_hours,
            "energy_kwh": job_energy_kwh,
            "base_carbon_g": base_carbon_g,
            "clean_carbon_g": clean_carbon_g,
            "carbon_saved_g": base_carbon_g - clean_carbon_g,
        })

    region_rows = {
        region: {
            "region": region,
            "price_usd_per_kwh": REGION_PRICE_KWH[region],
            "carbon_g_per_kwh": REGION_CARBON[region],
            "electricity_usd": energy_kwh * REGION_PRICE_KWH[region],
            "carbon_g": energy_kwh * REGION_CARBON[region],
        }
        for region in REGION_CARBON
    }
    base_carbon_g = region_rows[BASE_REGION]["carbon_g"]
    clean_carbon_g = region_rows[clean_region]["carbon_g"]
    base_electricity_usd = region_rows[BASE_REGION]["electricity_usd"]
    clean_electricity_usd = region_rows[clean_region]["electricity_usd"]
    result = {
        "base_region": BASE_REGION,
        "clean_region": clean_region,
        "cheapest_region": cheapest_region,
        "interruptible_energy_kwh": energy_kwh,
        "base_carbon_g": base_carbon_g,
        "clean_carbon_g": clean_carbon_g,
        "carbon_saved_g": base_carbon_g - clean_carbon_g,
        "carbon_saved_pct": (1 - clean_carbon_g / base_carbon_g) * 100 if base_carbon_g else 0,
        "base_electricity_usd": base_electricity_usd,
        "clean_electricity_usd": clean_electricity_usd,
        "electricity_savings_usd": base_electricity_usd - clean_electricity_usd,
        "job_rows": job_rows,
        "region_rows": list(region_rows.values()),
        "period_note": "Cumulative workload durations from workloads.csv; not scaled to 30 days.",
    }

    if verbose:
        print("== Carbon-aware Scheduling Extension ==")
        print(f"Interruptible workload energy: {energy_kwh:,.1f} kWh")
        print("Job comparison: us-east-1 -> cleanest region")
        print(f"{'job':20} {'GPU-h':>9} {'before gCO2e':>15} {'after gCO2e':>15} {'saved':>12}")
        for job in job_rows:
            print(f"{job['job_id']:20} {job['gpu_hours']:9.1f} {job['base_carbon_g']:15,.0f} "
                  f"{job['clean_carbon_g']:15,.0f} {job['carbon_saved_g']:12,.0f}")
        print("\nRegion comparison for the same interruptible workload")
        print(f"{'region':20} {'$/kWh':>8} {'gCO2/kWh':>10} {'electricity $':>16} {'carbon gCO2e':>16}")
        for region in region_rows.values():
            print(f"{region['region']:20} {region['price_usd_per_kwh']:8.3f} "
                  f"{region['carbon_g_per_kwh']:10.0f} {region['electricity_usd']:16,.2f} "
                  f"{region['carbon_g']:16,.0f}")
        print(f"Cheapest region: {cheapest_region}; cleanest region: {clean_region}.")
        print(f"Clean-region savings vs {BASE_REGION}: {result['carbon_saved_g']:,.0f} gCO2e "
              f"({result['carbon_saved_pct']:.1f}%), electricity ${result['electricity_savings_usd']:,.2f}.")
        print(result["period_note"])
        print("Assumption: jobs can move regions without changing GPU-hours; latency and residency are not modeled.")

    return result


if __name__ == "__main__":
    run()
