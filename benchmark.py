import time
import subprocess
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from concurrent.futures import ThreadPoolExecutor
import chromadb
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from pymilvus import MilvusClient

np.random.seed(42)

def generate_vectors(n, dim):
    vecs = np.random.randn(n, dim).astype(np.float32)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    return (vecs / norms).tolist()

def get_container_ram_mb(name_filter):
    try:
        out = subprocess.check_output(
            ["docker", "stats", "--no-stream", "--format", "{{.Name}}:{{.MemUsage}}"]
        ).decode()
        for line in out.splitlines():
            if name_filter in line:
                mem_str = line.split(":")[1].split("/")[0].strip()
                if "GiB" in mem_str:
                    return float(mem_str.replace("GiB", "")) * 1024
                elif "MiB" in mem_str:
                    return float(mem_str.replace("MiB", ""))
    except Exception:
        pass
    return 0.0

def run_concurrent_queries(query_fn, queries, concurrency, duration_sec=20):
    latencies = []
    start_bench = time.perf_counter()

    def worker(q_idx):
        q = queries[q_idx % len(queries)]
        t0 = time.perf_counter()
        query_fn(q)
        return (time.perf_counter() - t0) * 1000.0  # ms

    idx = 0
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        while (time.perf_counter() - start_bench) < duration_sec:
            futures = [pool.submit(worker, idx + i) for i in range(concurrency)]
            for f in futures:
                latencies.append(f.result())
            idx += concurrency

    total_time = time.perf_counter() - start_bench
    qps = len(latencies) / total_time
    p50, p95, p99 = np.percentile(latencies, [50, 95, 99])
    return round(qps, 2), round(p50, 2), round(p95, 2), round(p99, 2)

def main():
    # Scaled tiers to run cleanly within GitHub Actions free runner limits (~25 mins)
    configs = [(384, 50000), (1536, 50000)]
    concurrencies = [1, 10, 50, 100]
    results = []

    for dim, n_vecs in configs:
        print(f"\n--- Generating {n_vecs} vectors (dim={dim}) ---")
        vectors = generate_vectors(n_vecs, dim)
        queries = generate_vectors(500, dim)
        ids = list(range(n_vecs))

        # 1. CHROMA (Embedded)
        chroma_client = chromadb.PersistentClient(path=f"./chroma_db_{dim}")
        t0 = time.perf_counter()
        col = chroma_client.get_or_create_collection(name="bench", metadata={"hnsw:space": "cosine"})
        for i in range(0, n_vecs, 5000):
            col.add(ids=[str(x) for x in ids[i:i+5000]], embeddings=vectors[i:i+5000])
        chroma_idx_time = round(time.perf_counter() - t0, 2)

        for c in concurrencies:
            qps, p50, p95, p99 = run_concurrent_queries(
                lambda q: col.query(query_embeddings=[q], n_results=10), queries, c
            )
            results.append(["Chroma", dim, n_vecs, c, qps, p50, p95, p99, chroma_idx_time, 0])

        # 2. QDRANT (Client-Server)
        qdrant = QdrantClient(host="localhost", port=6333)
        qdrant.recreate_collection(
            collection_name="bench",
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE)
        )
        t0 = time.perf_counter()
        for i in range(0, n_vecs, 5000):
            pts = [PointStruct(id=ids[j], vector=vectors[j]) for j in range(i, i+5000)]
            qdrant.upsert(collection_name="bench", points=pts)
        qdrant_idx_time = round(time.perf_counter() - t0, 2)
        qdrant_ram = get_container_ram_mb("qdrant")

        for c in concurrencies:
            qps, p50, p95, p99 = run_concurrent_queries(
                lambda q: qdrant.search(collection_name="bench", query_vector=q, limit=10), queries, c
            )
            results.append(["Qdrant", dim, n_vecs, c, qps, p50, p95, p99, qdrant_idx_time, qdrant_ram])

        # 3. MILVUS (Distributed/Standalone)
        milvus = MilvusClient(uri="http://localhost:19530")
        if milvus.has_collection("bench"):
            milvus.drop_collection("bench")
        milvus.create_collection(collection_name="bench", dimension=dim, metric_type="COSINE")
        t0 = time.perf_counter()
        for i in range(0, n_vecs, 5000):
            data = [{"id": ids[j], "vector": vectors[j]} for j in range(i, i+5000)]
            milvus.insert(collection_name="bench", data=data)
        milvus_idx_time = round(time.perf_counter() - t0, 2)
        milvus_ram = get_container_ram_mb("milvus")

        for c in concurrencies:
            qps, p50, p95, p99 = run_concurrent_queries(
                lambda q: milvus.search(collection_name="bench", data=[q], limit=10), queries, c
            )
            results.append(["Milvus", dim, n_vecs, c, qps, p50, p95, p99, milvus_idx_time, milvus_ram])

    df = pd.DataFrame(results, columns=[
        "Engine", "Dim", "Vectors", "Concurrency", "QPS", "P50_ms", "P95_ms", "P99_ms", "IndexTime_s", "ActiveRAM_MB"
    ])
    df.to_csv("results.csv", index=False)
    print("\nSaved results.csv successfully!")

    # Generate Figure 2 (P99 Latency Curve) for your LaTeX paper
    plt.figure(figsize=(8, 5), dpi=300)
    sub = df[df["Dim"] == 1536]
    for engine in ["Chroma", "Qdrant", "Milvus"]:
        e_df = sub[sub["Engine"] == engine]
        plt.plot(e_df["Concurrency"], e_df["P99_ms"], marker="o", linewidth=2, label=engine)
    plt.title("P99 Tail Latency vs. Virtual User Concurrency (1536-Dim)")
    plt.xlabel("Concurrent Virtual Users (VUs)")
    plt.ylabel("P99 Tail Latency (ms)")
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.legend()
    plt.tight_layout()
    plt.savefig("latency_curves.png")

if __name__ == "__main__":
    main()