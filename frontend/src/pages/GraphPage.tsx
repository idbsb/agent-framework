import { useEffect, useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";
import { getJson } from "../api";
import { PageIntro, StatusBanner } from "../components/Layout";
import type { GraphPayload, JobOption } from "../types";
import ProfileSourceBadge from "../components/ProfileSourceBadge";

const focus = ["AI Agent开发工程师", "RAG引擎研发工程师", "AI安全技术工程师"];
function filterGraph(payload: GraphPayload, title: string): GraphPayload {
  if (payload.job_title) return payload;
  const jobId = payload.nodes.find((node) => node.type === "job" && node.name === title)?.id || `job:${title}`;
  const edges = payload.edges.filter((edge) => edge.source === jobId && (!edge.edge_type || edge.edge_type === "Job_Skill")).sort((a, b) => b.frequency - a.frequency);
  const ids = new Set(edges.flatMap((edge) => [edge.source, edge.target]));
  return { ...payload, job_title: title, nodes: payload.nodes.filter((node) => ids.has(node.id)), edges, summary: { node_count: ids.size, edge_count: edges.length, evidence_count: edges.reduce((sum, edge) => sum + edge.evidence_count, 0) } };
}

export default function GraphPage() {
  const [jobs, setJobs] = useState<JobOption[]>([]);
  const [title, setTitle] = useState(focus[0]);
  const [data, setData] = useState<GraphPayload | null>(null);
  const [fallback, setFallback] = useState(false);
  const [selected, setSelected] = useState<{ kind: "node" | "edge"; id: string } | null>(null);
  useEffect(() => { getJson<{ jobs: JobOption[] }>("/api/jobs").then(r => setJobs(r.data.jobs)).catch(() => setJobs([])); }, []);
  useEffect(() => {
    let cancelled = false;
    let recoveryTimer: ReturnType<typeof setTimeout> | undefined;
    const load = () => getJson<GraphPayload>(`/api/graph/job/${encodeURIComponent(title)}`, "/data/graph_compat_v1.json").then((result) => {
      if (cancelled) return;
      setData(filterGraph(result.data, title)); setFallback(result.fallback); setSelected(null);
      if (result.fallback) recoveryTimer = setTimeout(load, 15_000);
    });
    void load();
    return () => { cancelled = true; if (recoveryTimer) clearTimeout(recoveryTimer); };
  }, [title]);

  const option = useMemo(() => ({
    backgroundColor: "transparent",
    tooltip: {
      renderMode: "richText", backgroundColor: "#ffffff", borderColor: "#e5e7eb", textStyle: { color: "#111827" },
      formatter: (params: { dataType: string; data: { name?: string; relation?: string; frequency?: number; evidence?: string } }) => params.dataType === "edge" ? `${params.data.relation || "岗位—技能关系"}\n出现频率 ${Math.round((params.data.frequency || 0) * 100)}%\n依据 ${params.data.evidence || "仅提供招聘信息编号"}` : params.data.name,
    },
    legend: [{ data: ["岗位", "技能"], textStyle: { color: "#6b7280" } }],
    series: [{
      type: "graph", layout: "force", roam: true, draggable: true,
      categories: [{ name: "岗位", itemStyle: { color: "#3b82f6" } }, { name: "技能", itemStyle: { color: "#10b981" } }],
      data: data?.nodes.map((node) => ({ id: node.id, name: node.name, value: node.name, category: node.type === "job" ? 0 : 1, symbolSize: node.type === "job" ? 50 : 19 })) || [],
      links: data?.edges.map((edge) => ({ id: edge.id, source: edge.source, target: edge.target, relation: edge.relation_type || edge.relation, frequency: edge.frequency, evidence: edge.evidence || edge.evidence_jd_ids.join("、"), lineStyle: { width: 1 + edge.frequency * 3, opacity: .55, color: "#cbd5e1" } })) || [],
      force: { repulsion: 210, edgeLength: [80, 180], gravity: .08 },
      label: { show: true, color: "#374151", fontSize: 10, position: "right" },
      emphasis: { focus: "adjacency", lineStyle: { width: 4, opacity: 1, color: "#10b981" } },
    }],
  }), [data]);

  const selectedNode = selected?.kind === "node" ? data?.nodes.find((node) => node.id === selected.id) : undefined;
  const selectedEdge = selected?.kind === "edge" ? data?.edges.find((edge) => edge.id === selected.id) : selectedNode ? data?.edges.find((edge) => edge.source === selectedNode.id || edge.target === selectedNode.id) : undefined;
  const relatedEdges = selectedNode ? data?.edges.filter((edge) => edge.source === selectedNode.id || edge.target === selectedNode.id) || [] : [];
  const evidenceIds = [...new Set((selectedEdge ? [selectedEdge] : relatedEdges).flatMap((edge) => edge.evidence_jd_ids))];
  return <>
    <PageIntro kicker="岗位关系 · 技能连接 · 招聘依据" title="探索岗位与技能之间的联系" description="拖拽或缩放图谱，点击岗位、技能和关系即可查看详细要求与来源。" />
    <div className="toolbar"><label>重点岗位<select value={title} onChange={(event) => setTitle(event.target.value)}>{[...focus, ...jobs.filter(j => j.profile_source === "published_dynamic" && !focus.includes(j.standard_job_title)).map(j => j.standard_job_title)].map((item) => <option key={item}>{item}</option>)}</select></label><div className="data-chip">{data?.summary.node_count ?? 0} 节点</div><div className="data-chip">{data?.summary.edge_count ?? 0} 关系</div></div>
    <ProfileSourceBadge info={data ? { ...data, profile_source: fallback ? "static_baseline" : data.profile_source } : null}/>
    {fallback ? <StatusBanner tone="warning">暂时无法连接实时服务，当前展示最近可用图谱。</StatusBanner> : null}<StatusBanner>{data?.source_label}。{data?.notice}</StatusBanner>
    <div className="graph-layout"><article className="panel graph-canvas"><ReactECharts option={option} style={{ height: 560 }} onEvents={{ click: (params: { dataType: string; data: { id: string } }) => { if (params.dataType === "node" || params.dataType === "edge") setSelected({ kind: params.dataType, id: params.data.id }); } }} /></article><aside className="panel node-detail"><div className="panel-title"><span>关系详情</span><small>点击图谱查看</small></div>{selected ? <><h2>{selectedNode?.name || `${selectedEdge?.job_title || title} → ${selectedEdge?.skill_name || "技能"}`}</h2>{selectedNode ? <><p>类型：{selectedNode.formal_type || selectedNode.type}</p><p>技术领域：{selectedNode.technical_domain || "未标注"}</p><p>关联关系：{relatedEdges.length} 条</p></> : null}{selectedEdge ? <><p>关系：{selectedEdge.relation_type || selectedEdge.relation || "未标注"}</p><p>出现频率：{Math.round((selectedEdge.frequency || 0) * 100)}%</p><p>出现次数：{selectedEdge.mention_count ?? "未标注"}</p><p>重要程度：{selectedEdge.importance || "未标注"}</p></> : null}<h3>信息依据</h3><div className="tag-list">{evidenceIds.length ? evidenceIds.map((id) => <span key={id}>{id}</span>) : <em>当前数据未提供招聘原文或编号</em>}</div>{selectedEdge?.evidence ? <p className="evidence-copy">{selectedEdge.evidence}</p> : <p>当前仅提供招聘信息编号，暂无可展示的原文片段。</p>}</> : <div className="empty-state">点击图中的岗位、技能或连线，查看关联要求与招聘信息依据。</div>}</aside></div>
  </>;
}
