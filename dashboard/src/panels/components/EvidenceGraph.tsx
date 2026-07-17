import dagre from "@dagrejs/dagre";
import {
  Background,
  Controls,
  MarkerType,
  MiniMap,
  type Edge,
  type Node,
  ReactFlow,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useMemo, useState } from "react";

import { useI18n } from "@/lib/i18n";
import type { LinkGraph, LinkGraphNode, LinkType, Stage } from "@/lib/types";

const STAGE_COLOR: Record<Stage, string> = {
  raw: "#cbd5e1",
  extracted: "#7dd3fc",
  knowledge: "#6ee7b7",
  skill: "#c4b5fd",
};

const RELATION_COLOR: Record<LinkType, string> = {
  derived_from: "#2563eb",
  supported_by: "#16a34a",
  refuted_by: "#e11d48",
  supersedes: "#d97706",
  merged_from: "#7c3aed",
  distilled_into: "#4f46e5",
  related_to: "#64748b",
  requires: "#0891b2",
  synthesized_from: "#db2777",
};

const NODE_W = 190;
const NODE_H = 66;

function layout(graph: LinkGraph): { nodes: Node[]; edges: Edge[] } {
  const dag = new dagre.graphlib.Graph();
  dag.setGraph({ rankdir: "LR", nodesep: 36, ranksep: 100 });
  dag.setDefaultEdgeLabel(() => ({}));

  for (const node of graph.nodes) {
    dag.setNode(node.item_id, { width: NODE_W, height: NODE_H });
  }
  for (const edge of graph.edges) {
    if (dag.hasNode(edge.source_id) && dag.hasNode(edge.target_id)) {
      dag.setEdge(edge.source_id, edge.target_id);
    }
  }
  dagre.layout(dag);

  const nodes: Node[] = graph.nodes.map((node) => {
    const position = dag.node(node.item_id);
    return {
      id: node.item_id,
      position: {
        x: (position?.x ?? 0) - NODE_W / 2,
        y: (position?.y ?? 0) - NODE_H / 2,
      },
      data: {
        label: (
          <div className="text-left text-slate-900">
            <div className="truncate font-mono text-[10px] opacity-70">{node.item_id}</div>
            <div className="text-xs font-semibold">{node.stage}</div>
            <div className="text-[10px]">
              confidence {node.confidence.toFixed(2)}
              {node.is_missing && " · missing"}
            </div>
          </div>
        ),
      },
      style: {
        width: NODE_W,
        height: NODE_H,
        borderRadius: 8,
        padding: 8,
        background: node.is_missing ? "#fff" : STAGE_COLOR[node.stage],
        border: node.is_root
          ? "3px solid #0f172a"
          : node.is_missing
            ? "2px dashed #94a3b8"
            : "1px solid #94a3b8",
        opacity: node.is_missing ? 0.65 : 1,
      },
    };
  });

  const edges: Edge[] = graph.edges.map((edge, index) => {
    const color = RELATION_COLOR[edge.relation];
    return {
      id: `${edge.source_id}->${edge.target_id}-${edge.relation}-${index}`,
      source: edge.source_id,
      target: edge.target_id,
      label: `${edge.relation} · ${edge.strength.toFixed(2)}`,
      animated: edge.relation === "refuted_by" || edge.relation === "supersedes",
      markerEnd: { type: MarkerType.ArrowClosed, color },
      style: { stroke: color, strokeWidth: 2 },
      labelStyle: { fontSize: 10, fontWeight: 600, fill: color },
      labelBgStyle: { fill: "var(--background)", fillOpacity: 0.9 },
      labelBgPadding: [5, 3],
      labelBgBorderRadius: 4,
    };
  });

  return { nodes, edges };
}

export function EvidenceGraph({ graph }: { graph: LinkGraph }) {
  const { t } = useI18n();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const { nodes, edges } = useMemo(() => layout(graph), [graph]);
  const selected = graph.nodes.find((node) => node.item_id === selectedId);

  if (graph.nodes.length === 0) {
    return <div className="p-6 text-sm text-muted-foreground">{t("evidence.noNodes")}</div>;
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
        <span>
          {t("evidence.graphSummary", {
            nodes: graph.nodes.length,
            edges: graph.edges.length,
          })}
        </span>
        <span>{t("evidence.selectNode")}</span>
      </div>

      {graph.truncated && (
        <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-100">
          {t("evidence.graphTruncated", { count: graph.max_nodes })}
        </div>
      )}

      <div className="flex flex-wrap gap-x-4 gap-y-1 rounded-md border bg-muted/30 px-3 py-2">
        {(Object.entries(RELATION_COLOR) as [LinkType, string][]).map(([relation, color]) => (
          <span key={relation} className="flex items-center gap-1.5 text-[11px]">
            <span className="h-0.5 w-4" style={{ backgroundColor: color }} />
            {relation}
          </span>
        ))}
      </div>

      <div className="h-[520px] w-full rounded-md border bg-background">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodesDraggable={false}
          fitView
          fitViewOptions={{ padding: 0.2, maxZoom: 1.2 }}
          minZoom={0.1}
          maxZoom={2}
          nodesConnectable={false}
          onNodeClick={(_, node) => setSelectedId(node.id)}
        >
          <Background />
          <Controls showInteractive={false} />
          {graph.nodes.length > 12 && (
            <MiniMap
              pannable
              zoomable
              nodeColor={(node) => {
                const source = graph.nodes.find((item) => item.item_id === node.id);
                return source?.is_missing ? "#fff" : STAGE_COLOR[source?.stage ?? "raw"];
              }}
            />
          )}
        </ReactFlow>
      </div>

      {selected && <NodeDetails node={selected} />}
    </div>
  );
}

function NodeDetails({ node }: { node: LinkGraphNode }) {
  const { t } = useI18n();
  return (
    <div className="rounded-md border bg-card p-3 text-sm">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <span className="font-medium">{t("evidence.nodeDetails")}</span>
        <span className="font-mono text-xs text-muted-foreground">{node.item_id}</span>
      </div>
      <div className="mb-2 flex gap-4 text-xs text-muted-foreground">
        <span>{node.stage}</span>
        <span>
          {t("evidence.confidence")} {node.confidence.toFixed(2)}
        </span>
        <span>depth {node.depth}</span>
      </div>
      <p className="text-sm leading-relaxed">
        {node.is_missing ? t("evidence.missingNode") : node.content_preview || "—"}
      </p>
    </div>
  );
}
