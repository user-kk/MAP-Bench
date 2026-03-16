#!/usr/bin/env python3
"""
ANN Recall@K 测试 & 配置推荐脚本
自动搜索 recall ≈ target 的 HNSW / IVF-FLAT 配置
用法:
  python test_recall.py --index hnsw
  python test_recall.py --index ivfflat
  python test_recall.py --index hnsw --k 100 --target 0.95 --n_queries 300
"""
import argparse
import numpy as np
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.context import Context
from pymilvus import Collection


# ============ 候选建索引配置 ============
HNSW_CONFIGS = [
    {"M": 8,  "efConstruction": 64},
    {"M": 16,  "efConstruction": 128},
]

IVF_CONFIGS = [
    {"nlist": 2048},
    {"nlist": 4096},
    {"nlist": 8192},
]


def sample_query_vectors(coll, n_queries: int, seed: int = 42):
    """采样 query 向量（兼容任意当前索引类型）"""
    np.random.seed(seed)
    dim = 384

    # 自动探测当前索引可用的搜索参数
    probe_params = [
        {"metric_type": "L2", "ef": 64},
        {"metric_type": "L2", "nprobe": 32},
        {"metric_type": "L2"},
    ]
    working = None
    for p in probe_params:
        try:
            rand_vec = np.random.randn(dim).astype(np.float32).tolist()
            coll.search(data=[rand_vec], anns_field="vec", param=p, limit=1)
            working = p
            break
        except Exception:
            continue
    if not working:
        raise RuntimeError("无法在当前索引上执行搜索，请检查集合状态")

    print(f"[Phase 1] Sampling {n_queries} query vectors ...")
    query_ids, query_vecs, seen = [], [], set()

    while len(query_ids) < n_queries:
        rand_vec = np.random.randn(dim).astype(np.float32).tolist()
        hits = coll.search(
            data=[rand_vec], anns_field="vec",
            param=working, limit=50
        )[0]
        for h in hits:
            hid = int(h.id)
            if hid in seen:
                continue
            seen.add(hid)
            res = coll.query(expr=f"id == {hid}", output_fields=["id", "vec"])
            if res:
                query_ids.append(res[0]["id"])
                query_vecs.append(res[0]["vec"])
            if len(query_ids) >= n_queries:
                break
        if len(query_ids) % 50 == 0 and query_ids:
            print(f"  sampled {len(query_ids)}/{n_queries}")

    print(f"  done, {len(query_ids)} vectors sampled")
    return query_ids, query_vecs


def rebuild_index(coll, index_type: str, build_params: dict):
    """删除旧索引 → 建新索引 → load"""
    coll.release()
    coll.drop_index()
    coll.create_index(
        field_name="vec",
        index_params={
            "index_type": index_type,
            "metric_type": "L2",
            "params": build_params,
        },
    )
    coll.load()
    time.sleep(2)  # 等待 load 稳定


def compute_ground_truth(coll, query_ids, query_vecs, k):
    """用 FLAT 索引算精确 top-k（ground truth）"""
    print("[Phase 2] Building FLAT index for ground truth ...")
    rebuild_index(coll, "FLAT", {})

    gt = {}
    t0 = time.perf_counter()
    for i, (qid, qvec) in enumerate(zip(query_ids, query_vecs)):
        hits = coll.search(
            data=[qvec], anns_field="vec",
            param={"metric_type": "L2"},
            limit=k + 1, expr=f"id != {qid}",
        )[0]
        gt[qid] = set(int(h.id) for h in hits[:k])
        if (i + 1) % 50 == 0:
            print(f"  GT [{i+1}/{len(query_ids)}] "
                  f"elapsed={time.perf_counter() - t0:.1f}s")

    print(f"  ground truth done ({time.perf_counter() - t0:.1f}s)")
    return gt


def measure_recall(coll, query_ids, query_vecs, gt, k, search_params):
    """在当前索引上测 recall@k"""
    recalls = []
    for qid, qvec in zip(query_ids, query_vecs):
        hits = coll.search(
            data=[qvec], anns_field="vec",
            param=search_params,
            limit=k + 1, expr=f"id != {qid}",
        )[0]
        ann_ids = set(int(h.id) for h in hits[:k])
        recalls.append(len(gt[qid] & ann_ids) / k)
    return float(np.mean(recalls))


def binary_search_param(coll, query_ids, query_vecs, gt, k,
                        param_name, lo, hi, target):
    """二分查找满足 recall ≈ target 的最小搜索参数值"""
    best_val, best_recall = None, 0.0
    history = []

    while lo <= hi:
        mid = (lo + hi) // 2
        sp = {"metric_type": "L2", param_name: mid}
        recall = measure_recall(coll, query_ids, query_vecs, gt, k, sp)
        history.append((mid, recall))
        print(f"    {param_name}={mid:>5d}  recall@{k}={recall:.4f}")

        if recall >= target:
            best_val, best_recall = mid, recall
            hi = mid - 1
        else:
            lo = mid + 1

    return best_val, best_recall, history


def run(args):
    ctx = Context("127.0.0.1")
    ctx.use("openalex_middle")
    coll = ctx.get_milvus_collection(args.collection)
    total = coll.num_entities
    print(f"Collection: {args.collection}  entities: {total}\n")

    # --- Phase 1 ---
    query_ids, query_vecs = sample_query_vectors(coll, args.n_queries)

    # --- Phase 2 ---
    gt = compute_ground_truth(coll, query_ids, query_vecs, args.k)

    # --- Phase 3 ---
    if args.index == "hnsw":
        configs = HNSW_CONFIGS
        index_type = "HNSW"
        param_name = "ef"
    else:
        configs = IVF_CONFIGS
        index_type = "IVF_FLAT"
        param_name = "nprobe"

    results = []
    print(f"\n[Phase 3] Testing {index_type} configurations ...\n")

    for cfg in configs:
        print(f"  === Build config: {cfg} ===")
        rebuild_index(coll, index_type, cfg)

        if args.index == "hnsw":
            lo = args.k + 2        # ef 必须 > limit = k+1
            hi = 1024
        else:
            lo = 16
            hi = cfg["nlist"]      # nprobe 不能超过 nlist

        val, recall, hist = binary_search_param(
            coll, query_ids, query_vecs, gt, args.k,
            param_name, lo, hi, args.target,
        )
        if val is not None:
            results.append({"build": cfg, param_name: val,
                            "recall": recall, "detail": hist})
        else:
            print(f"    ⚠  recall@{args.k} 未能达到 {args.target}")
            # 记录最高值
            if hist:
                best = max(hist, key=lambda x: x[1])
                results.append({"build": cfg, param_name: best[0],
                                "recall": best[1], "detail": hist,
                                "below_target": True})
        print()

    # --- Phase 4: Report ---
    print("\n" + "=" * 64)
    print(f"  RESULTS  —  {index_type}  recall@{args.k} ≈ {args.target}")
    print("=" * 64)

    qualified = [r for r in results if not r.get("below_target")]
    if qualified:
        # 按搜索参数从小到大（越小越快）
        qualified.sort(key=lambda r: r[param_name])
        rec = qualified[0]
        print(f"\n  ★ RECOMMENDED CONFIG:")
        print(f"    Index build : {rec['build']}")
        print(f"    {param_name:12s} : {rec[param_name]}")
        print(f"    recall@{args.k}  : {rec['recall']:.4f}")
    else:
        print(f"\n  ⚠ 所有配置均未达到 recall@{args.k} ≥ {args.target}")

    print(f"\n  ALL RESULTS:")
    for r in results:
        tag = "  ✓" if not r.get("below_target") else "  ✗"
        print(f"  {tag} build={r['build']}  "
              f"{param_name}={r[param_name]}  "
              f"recall={r['recall']:.4f}")

    # 还原一个通用索引（可选）
    print(f"\n[Cleanup] Rebuilding default HNSW index ...")
    rebuild_index(coll, "HNSW", {"M": 16, "efConstruction": 128})
    print("Done.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--index", choices=["hnsw", "ivfflat"], required=True,
                   help="要测试的索引类型")
    p.add_argument("--collection", default="work_vec")
    p.add_argument("--k", type=int, default=100)
    p.add_argument("--n_queries", type=int, default=200)
    p.add_argument("--target", type=float, default=0.95,
                   help="目标 recall (default: 0.95)")
    run(p.parse_args())