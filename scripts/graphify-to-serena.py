#!/usr/bin/env python3
"""Bridge: Graphify graph.json → Serena memories.

Reads the knowledge graph and writes structured summaries to Serena
memories that BMAD skills and other tools can query.

Usage:
    python scripts/graphify-to-serena.py [--graph-dir GRAPHIFY_OUT]
"""
import json
import sys
import argparse
from pathlib import Path
from collections import Counter, defaultdict


def load_graph(graph_dir: Path) -> dict:
    graph_file = graph_dir / "graph.json"
    if not graph_file.exists():
        print(f"ERROR: {graph_file} not found", file=sys.stderr)
        sys.exit(1)
    with open(graph_file) as f:
        return json.load(f)


def load_report(graph_dir: Path) -> str:
    report_file = graph_dir / "GRAPH_REPORT.md"
    if report_file.exists():
        return report_file.read_text()
    return ""


def extract_communities(data: dict) -> dict:
    communities = defaultdict(lambda: {"nodes": [], "node_count": 0, "labels": []})
    for node in data.get("nodes", []):
        cid = node.get("community", -1)
        communities[cid]["nodes"].append(node)
        communities[cid]["node_count"] += 1
        communities[cid]["labels"].append(node.get("label", ""))
    return dict(communities)


def extract_god_nodes(data: dict, top_n: int = 15) -> list:
    edge_counts = Counter()
    for link in data.get("links", []):
        edge_counts[link.get("source", "")] += 1
        edge_counts[link.get("target", "")] += 1
    return [
        {"id": node_id, "edges": count}
        for node_id, count in edge_counts.most_common(top_n)
    ]


def extract_cross_community_edges(data: dict) -> list:
    node_community = {}
    for node in data.get("nodes", []):
        node_community[node.get("id", "")] = node.get("community", -1)
    cross = []
    for link in data.get("links", []):
        src = link.get("source", "")
        tgt = link.get("target", "")
        src_comm = node_community.get(src, -1)
        tgt_comm = node_community.get(tgt, -1)
        if src_comm != tgt_comm and src_comm != -1 and tgt_comm != -1:
            cross.append({
                "source": src,
                "source_community": src_comm,
                "target": tgt,
                "target_community": tgt_comm,
                "relation": link.get("relation", ""),
                "confidence": link.get("confidence", ""),
            })
    return cross


def extract_hyperedges(data: dict) -> list:
    return data.get("hyperedges", [])


def parse_surprising_connections(report: str) -> list:
    connections = []
    in_section = False
    for line in report.splitlines():
        if line.startswith("## Surprising Connections"):
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if in_section and line.startswith("- `"):
            connections.append(line.lstrip("- ").strip())
    return connections


def format_communities_summary(communities: dict) -> str:
    lines = ["# Graphify Communities Summary", ""]
    for cid in sorted(communities.keys()):
        c = communities[cid]
        labels = c["labels"][:5]
        more = f" (+{c['node_count'] - 5} more)" if c["node_count"] > 5 else ""
        lines.append(f"- Community {cid}: {c['node_count']} nodes — {', '.join(labels)}{more}")
    lines.append("")
    lines.append(f"Total communities: {len(communities)}")
    lines.append(f"Total nodes: {sum(c['node_count'] for c in communities.values())}")
    return "\n".join(lines)


def format_god_nodes(god_nodes: list, data: dict) -> str:
    id_to_label = {n.get("id", ""): n.get("label", n.get("id", "")) for n in data.get("nodes", [])}
    lines = ["# Graphify God Nodes (High Connectivity)", ""]
    for i, gn in enumerate(god_nodes, 1):
        label = id_to_label.get(gn["id"], gn["id"])
        lines.append(f"{i}. `{label}` — {gn['edges']} edges")
    return "\n".join(lines)


def format_cross_community(cross: list, data: dict) -> str:
    id_to_label = {n.get("id", ""): n.get("label", n.get("id", "")) for n in data.get("nodes", [])}
    lines = ["# Cross-Community Dependencies", ""]
    for edge in cross[:30]:
        src_label = id_to_label.get(edge["source"], edge["source"])
        tgt_label = id_to_label.get(edge["target"], edge["target"])
        lines.append(
            f"- `{src_label}` (C{edge['source_community']}) "
            f"--{edge['relation']}--> "
            f"`{tgt_label}` (C{edge['target_community']}) "
            f"[{edge['confidence']}]"
        )
    if len(cross) > 30:
        lines.append(f"\n... and {len(cross) - 30} more cross-community edges")
    return "\n".join(lines)


def format_surprising(connections: list) -> str:
    if not connections:
        return "# Surprising Connections\n\nNo surprising connections found."
    lines = ["# Surprising Connections", ""]
    for conn in connections:
        lines.append(f"- {conn}")
    return "\n".join(lines)


def format_hyperedges(hyperedges: list) -> str:
    if not hyperedges:
        return "# Hyperedges\n\nNo hyperedges found."
    lines = ["# Hyperedges (Group Relationships)", ""]
    for he in hyperedges:
        lines.append(f"- **{he.get('label', 'Unknown')}** — {len(he.get('nodes', []))} nodes [{he.get('confidence', '')} {he.get('confidence_score', '')}]")
    return "\n".join(lines)


def write_serena_memory(memory_name: str, content: str):
    memory_dir = Path(".serena/memories")
    memory_dir.mkdir(parents=True, exist_ok=True)
    safe_name = memory_name.replace("/", "_")
    mem_file = memory_dir / f"{safe_name}.md"
    mem_file.write_text(content)
    print(f"  Written: {mem_file}")


def main():
    parser = argparse.ArgumentParser(description="Graphify → Serena memory bridge")
    parser.add_argument("--graph-dir", type=str, default="graphify-out", help="Graphify output directory")
    args = parser.parse_args()

    graph_dir = Path(args.graph_dir)
    print(f"Graphify → Serena Bridge")
    print(f"Reading graph from: {graph_dir.resolve()}")

    data = load_graph(graph_dir)
    report = load_report(graph_dir)

    communities = extract_communities(data)
    god_nodes = extract_god_nodes(data)
    cross_community = extract_cross_community_edges(data)
    hyperedges = extract_hyperedges(data)
    surprising = parse_surprising_connections(report)

    print(f"  Communities: {len(communities)}")
    print(f"  God nodes: {len(god_nodes)}")
    print(f"  Cross-community edges: {len(cross_community)}")
    print(f"  Hyperedges: {len(hyperedges)}")
    print(f"  Surprising connections: {len(surprising)}")
    print()

    write_serena_memory("graphify_communities", format_communities_summary(communities))
    write_serena_memory("graphify_god-nodes", format_god_nodes(god_nodes, data))
    write_serena_memory("graphify_dependencies", format_cross_community(cross_community, data))
    write_serena_memory("graphify_surprising", format_surprising(surprising))
    write_serena_memory("graphify_hyperedges", format_hyperedges(hyperedges))

    stats = {
        "last_sync": __import__("datetime").datetime.now().isoformat(),
        "communities": len(communities),
        "god_nodes": len(god_nodes),
        "cross_community_edges": len(cross_community),
        "hyperedges": len(hyperedges),
        "total_nodes": len(data.get("nodes", [])),
        "total_links": len(data.get("links", [])),
    }
    write_serena_memory("integration_sync-log", f"# Sync Log\n\n```json\n{json.dumps(stats, indent=2)}\n```")

    print("\nDone. All graphify insights written to Serena memories.")


if __name__ == "__main__":
    main()
