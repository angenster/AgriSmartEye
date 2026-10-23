"""
检索质量评测 —— 对比「仅 FTS」「混合 RRF」「混合 + 重排」三种模式的 top-1 与 Recall@5。

对应方案 §10.2 的 RAG 指标要求。这里的评测集是自建的 12 条查询，
覆盖三种提问方式：精确病名 / 症状描述 / 口语化描述，
后者最贴近农户实际输入，也是最能区分检索质量的一类。

用法：
    python -m rag.eval_retrieval                 # 关闭重排
    RAG_RERANK=bge python -m rag.eval_retrieval  # 开启重排
"""
from typing import Dict, List, Tuple

from rag import retriever

# (查询, 期望命中的病虫害名, 提问方式)
CASES: List[Tuple[str, str, str]] = [
    ("芒果炭疽病",                                              "芒果炭疽病",   "精确病名"),
    ("香蕉黑星病",                                              "香蕉黑星病",   "精确病名"),
    ("咖啡锈病",                                                "咖啡锈病",     "精确病名"),
    ("叶片上出现褐色圆形病斑，湿度大的时候长出粉红色黏黏的孢子堆",   "芒果炭疽病",   "症状描述"),
    ("香蕉叶子发黄枯萎，切开茎里面是黑褐色的",                     "香蕉枯萎病",   "症状描述"),
    ("槟榔树整株慢慢黄化，新叶变小，最后枯死",                     "槟榔黄化病",   "症状描述"),
    ("植株心叶基部烂掉，一提整棵就拔出来了",                       "菠萝心腐病",   "症状描述"),
    ("叶子背面有橙黄色的粉状孢子堆，严重的时候叶子掉光",            "咖啡锈病",     "症状描述"),
    ("芒果嫩叶卷曲皱缩，叶背有银灰色锉伤痕",                       "芒果蓟马",     "症状描述"),
    ("果实表面凹下去一块块黑斑，潮湿时长出粉红色霉",                "芒果炭疽病",   "口语化"),
    ("树干切开里面一圈是红褐色的，有股臭味",                       "椰子红环腐病", "口语化"),
    ("新叶长出来是花的，一片片黄色，树也长不高",                   "木瓜花叶病",   "口语化"),
]


def evaluate(top_k: int = 5) -> Dict:
    hits_top1 = 0
    hits_topk = 0
    rows = []

    for query, expect, style in CASES:
        result = retriever.search(query, top_k=top_k)
        titles = [c["title"] for c in result["chunks"]]
        # title 形如 "芒果·芒果炭疽病（真菌病害）"，用包含匹配
        rank = next((i + 1 for i, t in enumerate(titles) if expect in t), None)
        hits_top1 += (rank == 1)
        hits_topk += (rank is not None)
        rows.append({
            "query": query,
            "style": style,
            "expect": expect,
            "rank": rank,
            "top1": titles[0] if titles else None,
            "mode": result["mode"],
        })

    n = len(CASES)
    return {
        "queries": n,
        "top1_accuracy": round(hits_top1 / n, 4),
        "recall_at_k": round(hits_topk / n, 4),
        "top_k": top_k,
        "mode": rows[0]["mode"] if rows else None,
        "rows": rows,
    }


def main() -> None:
    import json

    report = evaluate()
    print(f"检索模式: {report['mode']}   （重排开关 RAG_RERANK={__import__('os').environ.get('RAG_RERANK', 'off')}）")
    print(f"样例数 {report['queries']} | top-1 准确率 {report['top1_accuracy']:.1%} | Recall@{report['top_k']} {report['recall_at_k']:.1%}")
    print()
    print(f"{'提问方式':<10} {'期望':<12} {'实际名次':<8} top1")
    for r in report["rows"]:
        mark = "✓" if r["rank"] == 1 else ("—" if r["rank"] else "✗")
        rank = f"第{r['rank']}名" if r["rank"] else "未命中"
        print(f"  {r['style']:<8} {r['expect']:<12} {rank:<8} {mark}  {r['query'][:26]}")

    # 分提问方式统计，精确病名与口语化的差距最能说明问题
    print()
    for style in ("精确病名", "症状描述", "口语化"):
        subset = [r for r in report["rows"] if r["style"] == style]
        if not subset:
            continue
        acc = sum(1 for r in subset if r["rank"] == 1) / len(subset)
        print(f"  {style}: top-1 {acc:.0%}  ({len(subset)} 条)")

    print()
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
