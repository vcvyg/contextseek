# Reranker benchmark

This smoke benchmark compares the built-in heuristic and cross-encoder paths on
five small support/operations queries. Each query has five recalled candidates
and one labeled relevant candidate. It measures ranking recall and reranking
latency only; model download and startup are excluded.

Run it with:

```bash
uv run --extra rerank python scripts/benchmark_rerankers.py --device cpu --rounds 5
```

The fixture is intentionally small and deterministic, so it is useful for
regression checks rather than as a general model-quality claim. Replace the
cases in the script with domain-specific labeled candidates before selecting a
production model.

## Reference result

Results will vary by CPU, device, model cache, and candidate length. The table
below records a five-round run using Python 3.13 on a Windows x86-64 CPU with
`cross-encoder/ms-marco-MiniLM-L-6-v2` after one warm-up batch.

| Reranker | Recall@1 | Recall@3 | Median latency/query |
|----------|----------|----------|----------------------|
| Heuristic | 0.000 | 0.600 | 0.08 ms |
| Cross-encoder | 0.200 | 1.000 | 15.83 ms |
