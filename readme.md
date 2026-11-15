# Vector Database Benchmark Suite

An empirical benchmarking and evaluation framework for comparing **Embedded** (Chroma), **Standalone Client-Server** (Qdrant), and **Distributed Cloud-Native** (Milvus) vector database architectures under varying dataset scales, dimensionalities, and multi-client concurrency workloads.

---

## Overview

As Retrieval-Augmented Generation (RAG) pipelines scale in production, database choice becomes a critical bottleneck controlling end-to-end latency, infrastructure cost, and system reliability. This repository contains the complete replication package, synthetic dataset generators, and asynchronous benchmarking drivers used to evaluate vector storage performance across:
* **Vector Dimensions:** 384 dimensions (e.g., `all-MiniLM-L6-v2`) and 1536 dimensions (e.g., `text-embedding-3-small`).
* **Dataset Scale:** Up to $50,000$ ($50\text{k}$) vectors.
* **Concurrency Levels:** $1$ to $100$ Virtual Users (VUs) issuing concurrent Approximate Nearest Neighbor (ANN) queries.
* **Performance Metrics:** Queries Per Second (QPS), tail latencies ($P_{50}, P_{95}, P_{99}$), index build times ($T_{\text{index}}$), and active memory usage ($\text{RAM}$).

---

## Key Findings Summary

* **Embedded Storage (Chroma):** Delivers ultra-low baseline latency ($P_{99} < 6\text{ ms}$) and zero socket serialization overhead for single-tenant or read-heavy workloads, but suffers from throughput saturation and thread locking under high concurrent write/read pressure.
* **Standalone Server (Qdrant):** Provides robust memory-mapped (`mmap`) storage and stable concurrency handling, though high-dimensional payloads ($D = 1536$) require binary gRPC configuration to avoid REST serialization bottlenecks at scale.
* **Distributed Cloud-Native (Milvus):** Achieves the fastest index construction speeds and excellent multithreaded throughput scaling at compact dimensions ($831.81\text{ QPS}$ at $100\text{ VU}$ for $D = 384$), though accompanied by higher baseline container memory footprints.

---

## Quick Start & Reproduction

### Prerequisites

* Docker Engine ($\ge 26.0.0$) and Docker Compose ($\ge 2.26.1$)
* Python $3.12+$

### 1. Spin up Database Containers

```bash
cd docker
docker-compose up -d

```

### 2. Install Dependencies

```bash
pip install -r requirements.txt

```

### 3. Run Benchmark Suite

```bash
python drivers/benchmark_runner.py --vectors 50000 --dims 384 --concurrency 100

```

---

## Citation

If you use this benchmark suite or dataset generator in your research or systems engineering work, please cite:

```bibtex
@article{hasan2026vector,
  title={An Empirical Analysis of Embedded versus Dedicated Client-Server Architectures for High-Throughput Vector Retrieval-Augmented Generation Systems},
  author={Hasan, Md Zahid},
  journal={Preprints.org},
  year={2026}
}

```

---

## License

Distributed under the MIT License. See `LICENSE` for more information.

```

```
