import { useEffect, useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";
import { ArrowRight } from "lucide-react";
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
      data: data?.nodes.map((node) => ({ id: node.id, name: `${node.name}${node.batch_status ? ` · ${node.batch_status}` : ""}`, value: node.name, category: node.type === "job" ? 0 : 1, symbolSize: node.type === "job" ? 50 : node.batch_status === "NEW" ? 24 : 19, itemStyle: node.batch_status === "NEW" ? { color: "#f59e0b", borderColor: "#fff", borderWidth: 2 } : undefined })) || [],
      links: data?.edges.map((edge) => ({ id: edge.id, source: edge.source, target: edge.target, relation: edge.relation_type || edge.relation, frequency: edge.frequency, evidence: edge.evidence || edge.evidence_jd_ids.join("、"), lineStyle: { width: edge.batch_status ? 3 : 1 + edge.frequency * 3, opacity: edge.batch_status ? .9 : .55, color: edge.batch_status === "NEW" ? "#f59e0b" : edge.batch_status === "UPDATED" ? "#3b82f6" : "#cbd5e1", type: edge.batch_status === "NEW" ? "dashed" : "solid" } })) || [],
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
    <div className="toolbar"><label>岗位<select value={title} onChange={(event) => setTitle(event.target.value)}>{[...new Set([...focus, ...jobs.map(j => j.standard_job_title)])].map((item) => <option key={item}>{item}</option>)}</select></label><div className="data-chip">{data?.graph_version || "Graph V2"}</div><div className="data-chip">{data?.summary.node_count ?? 0} 节点</div><div className="data-chip">{data?.summary.edge_count ?? 0} 关系</div></div>
    {data?.baseline_summary ? <article className="panel graph-version-compare"><div><small>基准 Graph V1</small><b>{data.baseline_summary.job_count} 岗位 · {data.baseline_summary.skill_count} 技能 · {data.baseline_summary.edge_count} 关系</b></div><ArrowRight/><div><small>本批次 {data.batch_id}</small><b>+{data.graph_change?.new_job_node_count || 0} 岗位 · +{data.graph_change?.new_skill_node_count || 0} 技能 · +{data.graph_change?.new_relation_count || 0} 关系</b></div><ArrowRight/><div><small>当前 {data.graph_version}</small><b>{data.summary.job_count} 岗位 · {data.summary.skill_count} 技能 · {data.summary.edge_count} 关系</b></div></article> : null}
    <ProfileSourceBadge info={data ? { ...data, profile_source: fallback ? "static_baseline" : data.profile_source } : null}/>
    {fallback ? <StatusBanner tone="warning">暂时无法连接实时服务，当前展示最近可用图谱。</StatusBanner> : null}<StatusBanner>{data?.source_label}。{data?.notice}</StatusBanner>
    <div className="graph-layout"><article className="panel graph-canvas"><ReactECharts option={option} style={{ height: 560 }} onEvents={{ click: (params: { dataType: string; data: { id: string } }) => { if (params.dataType === "node" || params.dataType === "edge") setSelected({ kind: params.dataType, id: params.data.id }); } }} /></article><aside className="panel node-detail"><div className="panel-title"><span>节点与关系详情</span><small>点击图谱查看</small></div>{selected ? <><h2>{selectedNode?.name || `${selectedEdge?.job_title || title} → ${selectedEdge?.skill_name || "技能"}`}</h2>{selectedNode ? <><p>岗位/技能ID：{selectedNode.id}</p><p>类型：{selectedNode.formal_type || selectedNode.type}</p><p>岗位状态：{selectedNode.job_status || (selectedNode.is_emerging ? "新兴岗位候选" : "已有节点")}</p><p>动态：{selectedNode.batch_status || "Baseline"} · {selectedNode.batch_id || "Graph V1"}</p><p>JD / 企业 / 来源：{selectedNode.incremental_jd_count ?? "暂无数据"} / {selectedNode.company_count ?? "暂无数据"} / {selectedNode.source_count ?? "暂无数据"}</p><p>首次 / 最近：{selectedNode.first_seen || "暂无数据"} / {selectedNode.last_seen || "暂无数据"}</p><p>图谱版本：{selectedNode.graph_version || data?.graph_version || "Graph V1"}</p><p>关联关系：{relatedEdges.length} 条</p></> : null}{selectedEdge ? <><p>关系：{selectedEdge.relation_type || selectedEdge.relation || "未标注"}</p><p>变化标记：{selectedEdge.batch_status || "Baseline"}</p><p>出现频率：{selectedEdge.frequency ? `${Math.round(selectedEdge.frequency * 100)}%` : "新增批次暂不作频率判断"}</p><p>出现次数：{selectedEdge.mention_count ?? "未标注"}</p><p>重要程度：{selectedEdge.importance || "未标注"}</p></> : null}<h3>Evidence</h3><div className="tag-list">{evidenceIds.length ? evidenceIds.map((id) => <span key={id}>{id}</span>) : <em>当前数据未提供招聘原文或编号</em>}</div>{selectedEdge?.evidence ? <p className="evidence-copy">{selectedEdge.evidence}</p> : <p>来源URL与发布日期请在多源数据或岗位变化页按 Evidence ID 追溯；缺失字段显示暂无数据。</p>}</> : <div className="empty-state">点击图中的岗位、技能或连线，查看基础信息、动态状态与 Evidence。</div>}</aside></div>
  </>;
}
