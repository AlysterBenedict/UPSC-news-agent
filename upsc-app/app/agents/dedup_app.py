"""
UPSC Daily Digest — Deduplication & Clustering Agent
=====================================================
Groups similar articles using local embeddings + agglomerative clustering.
Preserves all source provenance.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Optional

import numpy as np
from sklearn.cluster import AgglomerativeClustering

from app.models.schemas_app import ArticleCluster
from app.services.embedding_client_app import EmbeddingClient
from app.utils.logging_app import get_logger

log = get_logger(__name__)

# Singleton embedding client
_embedding_client: Optional[EmbeddingClient] = None


def get_embedding_client() -> EmbeddingClient:
    global _embedding_client
    if _embedding_client is None:
        _embedding_client = EmbeddingClient()
    return _embedding_client


def deduplicate_articles(state: dict) -> dict:
    """
    Dedup & Clustering Agent: Group similar articles across sources.

    Uses sentence-transformer embeddings on title + first 500 chars,
    then agglomerative clustering with cosine distance threshold.
    Selects longest article as primary, others as supporting.
    """
    articles = state.get("articles_normalized", [])
    run_id = state.get("run_id", "unknown")

    log.info("dedup_start", run_id=run_id, article_count=len(articles))

    if not articles:
        return {"article_clusters": [], "current_phase": "clustered"}

    if len(articles) == 1:
        cluster = ArticleCluster(
            cluster_id="cluster_0001",
            primary_article_id=articles[0]["article_id"],
            representative_title=articles[0]["title"],
            combined_text=articles[0]["clean_text"],
            sources=[articles[0]["source"]],
            categories=[articles[0]["category"]],
            gs_papers=articles[0]["gs_papers"],
            article_count=1,
        )
        return {"article_clusters": [cluster.model_dump()], "current_phase": "clustered"}

    # Build embedding texts: title + first 500 chars of clean text
    embed_texts = []
    for art in articles:
        title = art.get("title", "")
        text = art.get("clean_text", "")[:500]
        embed_texts.append(f"{title}. {text}")

    # Compute embeddings
    client = get_embedding_client()
    embeddings = client.embed(embed_texts)

    if len(embeddings) == 0:
        log.warning("embedding_failed", article_count=len(articles))
        # Fall back: treat each article as its own cluster
        clusters = []
        for i, art in enumerate(articles):
            cluster = ArticleCluster(
                cluster_id=f"cluster_{i:04d}",
                primary_article_id=art["article_id"],
                representative_title=art["title"],
                combined_text=art["clean_text"],
                sources=[art["source"]],
                categories=[art["category"]],
                gs_papers=art["gs_papers"],
                article_count=1,
            )
            clusters.append(cluster.model_dump())
        return {"article_clusters": clusters, "current_phase": "clustered"}

    # Agglomerative clustering with cosine distance
    # distance_threshold=0.25 means articles with cosine similarity > 0.75 are grouped
    distance_matrix = 1 - client.cosine_similarity_matrix(embeddings)
    # Clip to avoid numerical issues
    distance_matrix = np.clip(distance_matrix, 0, 2)

    clustering = AgglomerativeClustering(
        n_clusters=None,
        distance_threshold=0.25,
        metric="precomputed",
        linkage="average",
    )
    labels = clustering.fit_predict(distance_matrix)

    # Group articles by cluster label
    cluster_groups: dict[int, list[int]] = defaultdict(list)
    for idx, label in enumerate(labels):
        cluster_groups[label].append(idx)

    # Build cluster objects
    clusters = []
    for cluster_label, indices in sorted(cluster_groups.items()):
        cluster_articles = [articles[i] for i in indices]

        # Select primary article: longest clean text
        primary = max(cluster_articles, key=lambda a: a.get("char_count", 0))
        supporting = [a for a in cluster_articles if a["article_id"] != primary["article_id"]]

        # Combine texts (primary first, then unique content from supporting)
        combined_parts = [primary["clean_text"]]
        for s in supporting:
            # Only add if substantially different
            if len(s.get("clean_text", "")) > 200:
                combined_parts.append(
                    f"\n\n[Additional source: {s['source']}]\n{s['clean_text']}"
                )

        combined_text = "\n".join(combined_parts)

        # Merge metadata
        all_sources = list(set(a["source"] for a in cluster_articles))
        all_categories = list(set(a["category"] for a in cluster_articles))
        all_gs = list(set(g for a in cluster_articles for g in a.get("gs_papers", [])))

        # Compute average similarity within cluster
        if len(indices) > 1:
            sim_scores = []
            for i in range(len(indices)):
                for j in range(i + 1, len(indices)):
                    sim_scores.append(1 - distance_matrix[indices[i]][indices[j]])
            avg_sim = float(np.mean(sim_scores))
        else:
            avg_sim = 1.0

        cluster = ArticleCluster(
            cluster_id=f"cluster_{cluster_label:04d}",
            primary_article_id=primary["article_id"],
            supporting_article_ids=[a["article_id"] for a in supporting],
            representative_title=primary["title"],
            combined_text=combined_text,
            sources=all_sources,
            categories=all_categories,
            gs_papers=all_gs,
            similarity_score=avg_sim,
            article_count=len(cluster_articles),
        )
        clusters.append(cluster.model_dump())

    log.info(
        "dedup_complete",
        run_id=run_id,
        input_articles=len(articles),
        clusters_formed=len(clusters),
        multi_article_clusters=sum(1 for c in clusters if c["article_count"] > 1),
    )

    return {
        "article_clusters": clusters,
        "current_phase": "clustered",
    }
