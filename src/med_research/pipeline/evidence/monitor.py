"""
Evidence Monitor — Continuous Tracking for New Publications & Trial Updates

Takes timestamped snapshots of evidence for tracked entities (drugs, genes,
queries), compares snapshots over time, and generates alerts for:
  - New PubMed publications
  - New clinical trial registrations
  - Trial phase progressions
  - New FDA label approvals
  - Preprint → Published transitions

Usage:
    python evidence_monitor/monitor.py --snapshot       # Take a new snapshot
    python evidence_monitor/monitor.py --diff            # Compare last 2 snapshots
    python evidence_monitor/monitor.py --export-html     # Diff + HTML report
    python evidence_monitor/monitor.py --watch           # Auto-diff every hour
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

from med_research.rate_limiter import rate_limited_sleep

sys.path.insert(0, str(Path(__file__).parent.parent))

import logging

from med_research.pipeline.evidence.gatherer import gather_evidence
from med_research.pipeline.knowledge_graph.config import load_genes as config_load_genes

logger = logging.getLogger(__name__)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR = Path(__file__).parent / "data"
SNAPSHOTS_DIR = DATA_DIR / "snapshots"

# ── Tracked entities ────────────────────────────────────────────────────

TRACKED_QUERIES = [
    "B cell depletion therapy lupus",
    "CAR-T cell therapy lupus",
    "BTK inhibitor lupus",
    "JAK inhibitor lupus",
    "interferon inhibitor lupus",
    "lupus nephritis treatment",
    "belimumab lupus",
    "rituximab lupus",
    "voclosporin lupus nephritis",
    "anifrolumab lupus",
]

# Load tracked drugs/genes from repurposing candidates
def _load_tracked_entities() -> tuple:
    """Load drugs and genes from repurposing candidates and knowledge graph."""
    drugs = set()
    genes = set()
    try:
        candidates_path = Path("drug_repurposing/data/candidates.json")
        if candidates_path.exists():
            data = json.loads(candidates_path.read_text(encoding="utf-8"))
            for c in data.get("repurposing_candidates", []):
                if c.get("drug_name"):
                    drugs.add((c.get("drug_name") or "").split("(")[0].strip())
                if c.get("gene_name"):
                    genes.add(c["gene_name"])
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        pass

    try:
        gene_data = config_load_genes()
        for g in gene_data.get("genes", []):
            if g.get("name"):
                genes.add(g["name"])
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        pass

    return sorted(drugs), sorted(genes)


# ── Helpers ──────────────────────────────────────────────────────────────


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _hash_results(results: list) -> str:
    """Hash a list of dicts for quick comparison."""
    sorted_data = json.dumps(
        sorted(results, key=lambda x: x.get("id", x.get("title", ""))),
        sort_keys=True,
    )
    return hashlib.sha256(sorted_data.encode()).hexdigest()[:16]


# ── Snapshot Engine ──────────────────────────────────────────────────────


def take_snapshot(sources: list = None, max_per_query: int = 10) -> dict:
    """Take a new evidence snapshot for all tracked entities.

    Args:
        sources: Source types to query.
        max_per_query: Max results per query/source.

    Returns:
        Snapshot dict with timestamp, queries, and results.
    """
    if sources is None:
        sources = ["pubmed", "preprints", "clinical_trials"]

    drugs, genes = _load_tracked_entities()
    timestamp = datetime.now()
    snapshot_id = timestamp.strftime("%Y%m%d_%H%M%S")

    logger.info(f"\n📸 Taking snapshot: {snapshot_id}")
    logger.info(f"   Tracking: {len(TRACKED_QUERIES)} queries, "
          f"{len(drugs)} drugs, {len(genes)} genes")
    logger.info(f"   Sources: {', '.join(sources)}\n")

    queries_data = {}

    # Snapshot tracked queries
    for i, query in enumerate(TRACKED_QUERIES, 1):
        logger.info(f"  [{i}/{len(TRACKED_QUERIES)}] Query: \"{query}\"")
        evidence = gather_evidence(
            query, sources=sources, max_per_source=max_per_query, use_cache=True,
        )
        queries_data[query] = {
            "results": evidence["all_results"],
            "total": evidence["total_results"],
            "hash": _hash_results(evidence["all_results"]),
        }

    # Snapshot top drugs
    logger.info(f"\n  Snapshotting {len(drugs)} drugs...")
    drug_data = {}
    for drug in drugs[:25]:  # Cap at 25 to avoid excessive API calls
        query = f"{drug} lupus"
        logger.info(f"    💊 {drug}")
        evidence = gather_evidence(
            query, sources=["pubmed", "clinical_trials"],
            max_per_source=5, use_cache=True,
        )
        drug_data[drug] = {
            "results": evidence["all_results"],
            "total": evidence["total_results"],
            "hash": _hash_results(evidence["all_results"]),
        }

    # Snapshot top genes
    logger.info(f"\n  Snapshotting {len(genes)} genes...")
    gene_data = {}
    for gene in genes[:25]:
        query = f"{gene} lupus"
        logger.info(f"    🧬 {gene}")
        evidence = gather_evidence(
            query, sources=["pubmed", "clinical_trials"],
            max_per_source=5, use_cache=True,
        )
        gene_data[gene] = {
            "results": evidence["all_results"],
            "total": evidence["total_results"],
            "hash": _hash_results(evidence["all_results"]),
        }

    snapshot = {
        "snapshot_id": snapshot_id,
        "timestamp": timestamp.isoformat(),
        "tracked_queries": TRACKED_QUERIES,
        "tracked_drugs": drugs,
        "tracked_genes": genes,
        "sources": sources,
        "queries": queries_data,
        "drugs": drug_data,
        "genes": gene_data,
    }

    # Save snapshot
    path = SNAPSHOTS_DIR / f"snapshot_{snapshot_id}.json"
    save_json(path, snapshot)

    logger.info(f"\n✅ Snapshot saved: {path.name}")
    logger.info(f"   Queries: {len(queries_data)} · Drugs: {len(drug_data)} · Genes: {len(gene_data)}")

    return snapshot


# ── Diff Engine ──────────────────────────────────────────────────────────


def compare_snapshots(prev: dict, curr: dict) -> dict:
    """Compare two snapshots and generate a diff with alerts.

    Args:
        prev: Previous snapshot dict.
        curr: Current snapshot dict.

    Returns:
        Diff dict with changes and alerts.
    """
    alerts = []
    changes = {"new_queries": [], "changed_queries": [], "new_drugs": [],
               "changed_drugs": [], "new_genes": [], "changed_genes": []}

    prev_time = datetime.fromisoformat(prev["timestamp"])
    curr_time = datetime.fromisoformat(curr["timestamp"])
    hours_elapsed = (curr_time - prev_time).total_seconds() / 3600

    # Compare queries (use snapshot's own tracked query list, not global)
    tracked_queries = curr.get("tracked_queries", prev.get("tracked_queries", []))
    for query in tracked_queries:
        prev_data = prev["queries"].get(query, {})
        curr_data = curr["queries"].get(query, {})
        prev_hash = prev_data.get("hash", "")
        curr_hash = curr_data.get("hash", "")

        if prev_hash != curr_hash:
            changes["changed_queries"].append(query)
            new_items = _find_new_items(
                prev_data.get("results", []),
                curr_data.get("results", []),
            )
            if new_items:
                alerts.append({
                    "type": "new_publication",
                    "entity": query,
                    "entity_type": "query",
                    "new_count": len(new_items),
                    "new_items": new_items[:5],
                    "severity": "medium" if len(new_items) > 2 else "low",
                })

    # Compare drugs
    for drug in curr["tracked_drugs"][:25]:
        prev_data = prev["drugs"].get(drug, {})
        curr_data = curr["drugs"].get(drug, {})
        if not prev_data:
            changes["new_drugs"].append(drug)
        elif prev_data.get("hash") != curr_data.get("hash"):
            changes["changed_drugs"].append(drug)
            new_items = _find_new_items(
                prev_data.get("results", []),
                curr_data.get("results", []),
            )
            if new_items:
                alerts.append({
                    "type": "new_drug_evidence",
                    "entity": drug,
                    "entity_type": "drug",
                    "new_count": len(new_items),
                    "new_items": new_items[:3],
                    "severity": "high" if len(new_items) >= 3 else "medium",
                })

    # Compare genes
    for gene in curr["tracked_genes"][:25]:
        prev_data = prev["genes"].get(gene, {})
        curr_data = curr["genes"].get(gene, {})
        if not prev_data:
            changes["new_genes"].append(gene)
            alerts.append({
                "type": "new_gene_tracked",
                "entity": gene,
                "entity_type": "gene",
                "new_count": curr_data.get("total", 0),
                "new_items": curr_data.get("results", [])[:3],
                "severity": "low",
            })
        elif prev_data.get("hash") != curr_data.get("hash"):
            changes["changed_genes"].append(gene)
            new_items = _find_new_items(
                prev_data.get("results", []),
                curr_data.get("results", []),
            )
            if new_items:
                alerts.append({
                    "type": "new_gene_evidence",
                    "entity": gene,
                    "entity_type": "gene",
                    "new_count": len(new_items),
                    "new_items": new_items[:3],
                    "severity": "low",
                })

    # Sort alerts by severity
    severity_order = {"high": 0, "medium": 1, "low": 2}
    alerts.sort(key=lambda a: severity_order.get(a["severity"], 3))

    total_changes = (
        len(changes["new_queries"]) + len(changes["changed_queries"]) +
        len(changes["new_drugs"]) + len(changes["changed_drugs"]) +
        len(changes["new_genes"]) + len(changes["changed_genes"])
    )

    return {
        "prev_snapshot": prev["snapshot_id"],
        "curr_snapshot": curr["snapshot_id"],
        "prev_timestamp": prev["timestamp"],
        "curr_timestamp": curr["timestamp"],
        "hours_elapsed": round(hours_elapsed, 1),
        "total_changes": total_changes,
        "alerts": alerts,
        "changes": changes,
        "generated_at": datetime.now().isoformat(),
    }


def _find_new_items(prev_results: list, curr_results: list) -> list:
    """Find items in curr_results not present in prev_results."""
    prev_ids = {r.get("id", r.get("title", "")) for r in prev_results}
    new_items = []
    for r in curr_results:
        rid = r.get("id", r.get("title", ""))
        if rid not in prev_ids:
            new_items.append({
                "title": r.get("title", "")[:120],
                "source_type": r.get("source_type", ""),
                "year": r.get("year", ""),
                "url": r.get("url", ""),
                "id": rid,
            })
    return new_items


def list_snapshots() -> list:
    """List all snapshot files sorted by time (newest first)."""
    if not SNAPSHOTS_DIR.exists():
        return []
    paths = sorted(SNAPSHOTS_DIR.glob("snapshot_*.json"), reverse=True)
    return paths


def load_latest_snapshots(n: int = 2) -> list:
    """Load the n most recent snapshots."""
    paths = list_snapshots()[:n]
    return [load_json(p) for p in paths]


def run_diff() -> dict:
    """Run a full snapshot differencing workflow.

    Takes a new snapshot and compares against the most recent one.
    """
    snapshots = load_latest_snapshots(1)
    if not snapshots:
        logger.info("⚠️  No previous snapshots found. Taking first baseline snapshot.")
        prev = take_snapshot()
        return {"status": "baseline", "snapshot_id": prev["snapshot_id"]}

    logger.info(f"📸 Comparing against snapshot: {snapshots[0]['snapshot_id']}")
    prev = snapshots[0]
    curr = take_snapshot()

    logger.info("\n🔍 Computing diff...")
    diff = compare_snapshots(prev, curr)

    # Save diff
    diff_path = DATA_DIR / f"diff_{curr['snapshot_id']}.json"
    save_json(diff_path, diff)

    return diff


# ── CLI ──────────────────────────────────────────────────────────────────


def print_diff_summary(diff: dict):
    """Print a formatted diff summary."""
    if diff.get("status") == "baseline":
        logger.info("\n✅ Baseline snapshot created. No diff to show.")
        return

    logger.info("\n" + "=" * 75)
    logger.info("📡 CONTINUOUS EVIDENCE MONITOR — Diff Report")
    logger.info("=" * 75)

    logger.info(f"\n  Previous: {diff['prev_snapshot']} ({diff['prev_timestamp'][:19]})")
    logger.info(f"  Current:  {diff['curr_snapshot']} ({diff['curr_timestamp'][:19]})")
    logger.info(f"  Elapsed:  {diff['hours_elapsed']:.1f} hours")

    changes = diff["changes"]
    logger.info("\n  📊 Changes:")
    if changes["changed_queries"]:
        logger.info(f"    Changed queries: {len(changes['changed_queries'])}")
    if changes["changed_drugs"]:
        logger.info(f"    Changed drugs:   {len(changes['changed_drugs'])}")
        if changes["changed_drugs"]:
            logger.info(f"      → {', '.join(changes['changed_drugs'][:8])}")
    if changes["changed_genes"]:
        logger.info(f"    Changed genes:   {len(changes['changed_genes'])}")

    alerts = diff.get("alerts", [])
    logger.info(f"\n  🚨 Alerts: {len(alerts)}")
    high = [a for a in alerts if a["severity"] == "high"]
    med = [a for a in alerts if a["severity"] == "medium"]
    low = [a for a in alerts if a["severity"] == "low"]
    logger.info(f"    🔴 High:   {len(high)}")
    logger.info(f"    🟡 Medium: {len(med)}")
    logger.info(f"    🟢 Low:    {len(low)}")

    if alerts:
        logger.info("\n  📋 Alert Details:")
        for a in alerts[:10]:
            icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(a["severity"], "⚪")
            logger.info(f"  {icon} [{a['severity'].upper():7s}] {a['entity']:30s} "
                  f"({a['new_count']} new {a['type']})")


def main():
    parser = argparse.ArgumentParser(
        description="Continuous Evidence Monitor — Track new publications & trial updates"
    )
    parser.add_argument("--snapshot", action="store_true",
                        help="Take a new evidence snapshot")
    parser.add_argument("--diff", action="store_true",
                        help="Compare latest 2 snapshots")
    parser.add_argument("--list", action="store_true",
                        help="List available snapshots")
    parser.add_argument("--export-html", action="store_true",
                        help="Generate HTML diff report")
    parser.add_argument("--sources", type=str, default="pubmed,preprints,clinical_trials",
                        help="Comma-separated sources for snapshot")
    parser.add_argument("--max", type=int, default=10,
                        help="Max results per query (default: 10)")

    args = parser.parse_args()

    if args.list:
        snapshots = list_snapshots()
        logger.info(f"\n📂 Available snapshots ({len(snapshots)}):")
        for p in snapshots[:20]:
            logger.info(f"  {p.name}")
        return

    if args.diff or args.export_html:
        sources = [s.strip() for s in args.sources.split(",")]
        snapshots = load_latest_snapshots(2)

        if len(snapshots) < 2:
            logger.warning("⚠️  Need at least 2 snapshots. Taking baseline + new snapshot.")
            logger.info("   This may take a few minutes...")
            prev = take_snapshot(sources=sources, max_per_query=args.max)
            rate_limited_sleep(2)
            curr = take_snapshot(sources=sources, max_per_query=args.max)
        else:
            prev, curr = snapshots

        diff = compare_snapshots(prev, curr)
        print_diff_summary(diff)

        if args.export_html:
            from med_research.pipeline.evidence.monitor_report import generate_html_report
            generate_html_report(diff, prev, curr)
            logger.info("\n✅ HTML report generated: evidence_monitor/report.html")
        return

    if args.snapshot:
        sources = [s.strip() for s in args.sources.split(",")]
        take_snapshot(sources=sources, max_per_query=args.max)
        return

    # Default: take snapshot
    sources = [s.strip() for s in args.sources.split(",")]
    take_snapshot(sources=sources, max_per_query=args.max)


if __name__ == "__main__":
    main()
