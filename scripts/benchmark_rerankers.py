"""Small reproducible recall/latency benchmark for retrieval rerankers."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from statistics import median
from time import perf_counter

from contextseek.config.strategies import RetrievalStrategy
from contextseek.retrieval.components import CrossEncoderReranker, HeuristicReranker


@dataclass(frozen=True)
class Case:
    query: str
    relevant_id: str
    documents: tuple[tuple[str, str], ...]


CASES = (
    Case(
        "How can I reset a forgotten password?",
        "password",
        (
            ("analytics", "Password reset analytics count forgotten-password requests."),
            ("billing", "Invoices can be downloaded from account billing settings."),
            ("password", "Use the forgot password link to receive a reset email."),
            ("profile", "Change your display name from the profile page."),
            ("session", "Active browser sessions can be reviewed by an administrator."),
        ),
    ),
    Case(
        "Why did the deployment run out of memory?",
        "oom",
        (
            ("policy", "The deployment memory policy was reviewed last quarter."),
            ("timeout", "The deployment failed because the health check timed out."),
            ("oom", "The container was killed after exceeding its memory limit."),
            ("network", "The release could not resolve the package registry hostname."),
            ("version", "The release changed the application version label."),
        ),
    ),
    Case(
        "Where do I rotate an API credential?",
        "key",
        (
            ("policy", "The API credential rotation policy is reviewed annually."),
            ("key", "Create and revoke access tokens from the security console."),
            ("logs", "Audit logs retain administrative actions for ninety days."),
            ("quota", "Request a higher rate limit from the usage page."),
            ("webhook", "Webhooks notify external systems when records change."),
        ),
    ),
    Case(
        "Can deleted records be recovered?",
        "restore",
        (
            ("report", "Deleted records are excluded from active-record reports."),
            ("export", "Export active records as a CSV file."),
            ("restore", "Restore soft-deleted items from the recycle bin for 30 days."),
            ("retention", "Archived logs are retained for compliance."),
            ("schema", "Custom fields can be added to record schemas."),
        ),
    ),
    Case(
        "How do I reduce slow database queries?",
        "index",
        (
            ("monitor", "A dashboard lists slow database queries and their duration."),
            ("backup", "Schedule nightly snapshots of the database."),
            ("index", "Add an index for columns used by frequent query filters."),
            ("replica", "Read replicas improve availability during maintenance."),
            ("access", "Database roles control which tables a user can access."),
        ),
    ),
)


def _candidates(case: Case) -> list[dict[str, object]]:
    return [
        {"id": item_id, "content": content, "score": 0.5, "stage": "skill"}
        for item_id, content in case.documents
    ]


def evaluate(reranker, *, rounds: int) -> tuple[float, float, float]:
    strategy = RetrievalStrategy()
    top_one = 0
    top_three = 0
    latencies_ms: list[float] = []
    for _ in range(rounds):
        for case in CASES:
            started = perf_counter()
            ranked = reranker.rerank(
                _candidates(case), query=case.query, strategy=strategy
            )
            latencies_ms.append((perf_counter() - started) * 1000)
            ids = [str(item["id"]) for item in ranked]
            top_one += case.relevant_id in ids[:1]
            top_three += case.relevant_id in ids[:3]
    total = len(CASES) * rounds
    return top_one / total, top_three / total, median(latencies_ms)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model", default="cross-encoder/ms-marco-MiniLM-L-6-v2"
    )
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--rounds", type=int, default=5)
    args = parser.parse_args()

    cross_encoder = CrossEncoderReranker(args.model, device=args.device)
    cross_encoder.rerank(
        _candidates(CASES[0]), query=CASES[0].query, strategy=RetrievalStrategy()
    )

    print("reranker\trecall@1\trecall@3\tmedian_ms")
    for name, reranker in (
        ("heuristic", HeuristicReranker()),
        ("cross_encoder", cross_encoder),
    ):
        recall_at_one, recall_at_three, latency = evaluate(
            reranker, rounds=max(1, args.rounds)
        )
        print(
            f"{name}\t{recall_at_one:.3f}\t{recall_at_three:.3f}\t{latency:.2f}"
        )


if __name__ == "__main__":
    main()
