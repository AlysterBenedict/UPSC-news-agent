"""Dry-run test: Ingest → Normalize → Cluster on real scraper data."""
import sys
sys.path.insert(0, ".")

from app.agents.ingestion import ingest_articles
from app.agents.normalize import normalize_articles
from app.agents.dedup import deduplicate_articles

# Stage 1: Ingest
state = {"run_date": "2026-06-09", "scraper_output_dir": "../", "run_id": "test_dry"}
state.update(ingest_articles(state))
print(f"[INGEST] {state['metrics']['articles_ingested']} articles ingested")

# Stage 2: Normalize
state.update(normalize_articles(state))
print(f"[NORMALIZE] {len(state['articles_normalized'])} articles normalized")

# Stage 3: Cluster
state.update(deduplicate_articles(state))
clusters = state["article_clusters"]
print(f"[CLUSTER] {len(clusters)} clusters formed")
multi = sum(1 for c in clusters if c["article_count"] > 1)
print(f"  Multi-article clusters: {multi}")
print(f"  Single-article clusters: {len(clusters) - multi}")

# Show top clusters by article count
top = sorted(clusters, key=lambda c: c["article_count"], reverse=True)[:5]
for c in top:
    print(f"  [{c['article_count']} articles] {c['representative_title'][:80]}")

print("\nDRY RUN COMPLETE")
