import { useEffect, useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";
import { getJson } from "../api";
import { PageIntro, StatusBanner } from "../components/Layout";
import type { GraphPayload, JobOption } from "../types";
import ProfileSourceBadge from "../components/ProfileSourceBadge";

const focus = ["AI Agent开发工程师", "RAG引擎研发工程师", "AI安全技术工程师"];

function filterGraph(payload: GraphPayload, title: string): GraphPayload {
  if (payload.job_title) return payload;
  const job = payload.nodes.find((node) => node.type === "job" && node.name === title);
  const jobId = job?.id || `job:${title}`;
  const edges = payload.edges.filter((edge) => edge.source === jobId && (!edge.edge_type || edge.edge_type === "Job_Skill")).sort((a, b) => b.frequency - a.frequency);
  const ids = new Set(edges.flatMap((edge) => [edge.source, edge.target]));
  if (job) ids.add(job.id);
  return { ...payload, job_title: title, nodes: payload.nodes.filter((node) => ids.has(node.id)), edges, summary: { node_count: ids.size, edge_count: edges.length, evidence_count: edges.reduce((sum, edge) => sum + edge.evidence_count, 0) } };
}

export default function GraphPage() {
  const [jobs, setJobs] = useState<JobOption[]>([]);
  const [title, setTitle] = useState(focus[0]);
  const [data, setData] = useState<GraphPayload | null>(null);
  const [selected, setSelected] = useState<{ kind: "node" | "edge"; id: string } | null>(null);

  useEffect(() => { getJson<{ jobs: JobOption[] }>("/api/jobs", "/data/jobs.json").then((result) => setJobs(result.data.jobs)).catch(() => setJobs([])); }, []);
  useEffect(() => {
    let cancelled = false;
    let recoveryTimer: ReturnType<typeof setTimeout> | undefined;
    const load = () => getJson<GraphPayload>(`/api/graph/job/${encodeURIComponent(title)}`, "/data/graph_compat_v1.json").then((result) => {
      if (cancelled) return;
      setData(filterGraph(result.data, title));
      setSelected(null);
      if (result.fallback) recoveryTimer = setTimeout(load, 15_000);
    });
    void load();
    return () => { cancelled = true; if (recoveryTimer) clearTimeout(recoveryTimer); };
  }, [title]);

  const option = useMemo(() => ({
    backgroundColor: "transparent",
    tooltip: {
      renderMode: "richText", backgroundColor: "#ffffff", borderColor: "#e5e7eb", textStyle: { color: "#111827" },
      formatter: (params: { dataType: string; data: { name?: string; relation?: string; frequency?: number; evidence?: string; evidenceCount?: number; sampleSize?: number } }) => params.dataType === "edge" ? `${params.data.relation || "岗位—技能关系"}\n${(params.data.sampleSize || 0) < 3 ? `${params.data.evidenceCount || 0}条JD提及` : `出现频率 ${Math.round((params.data.frequency || 0) * 100)}%`}\n依据 ${params.data.evidence || "招聘信息编号见详情"}` : params.data.name,
    },
    legend: [{ data: ["岗位", "技能"], textStyle: { color: "#6b7280" } }],
    series: [{
      type: "graph", layout: "force", roam: true, draggable: true,
      categories: [{ name: "岗位", itemStyle: { color: "#3b82f6" } }, { name: "技能", itemStyle: { color: "#10b981" } }],
      data: data?.nodes.map((node) => ({ id: node.id, name: node.name, value: node.name, category: node.type === "job" ? 0 : 1, symbolSize: node.type === "job" ? 50 : 19 })) || [],
      links: data?.edges.map((edge) => ({ id: edge.id, source: edge.source, target: edge.target, relation: edge.relation_type || edge.relation, frequency: edge.frequency, evidenceCount: edge.evidence_count, sampleSize: edge.sample_size, evidence: edge.evidence || edge.evidence_jd_ids.join("、"), lineStyle: { width: 1 + edge.frequency * 3, opacity: .65, color: "#94a3b8", type: "solid" } })) || [],
      force: { repulsion: 210, edgeLength: [80, 180], gravity: .08 },
      label: { show: true, color: "#374151", fontSize: 10, position: "right" },
      emphasis: { focus: "adjacency", lineStyle: { width: 4, opacity: 1, color: "#10b981" } },
    }],
  }), [data]);

  const selectedNode = selected?.kind === "node" ? data?.nodes.find((node) => node.id === selected.id) : undefined;
  const selectedEdge = selected?.kind === "edge" ? data?.edges.find((edge) => edge.id === selected.id) : selectedNode ? data?.edges.find((edge) => edge.source === selectedNode.id || edge.target === selectedNode.id) : undefined;
  const relatedEdges = selectedNode ? data?.edges.filter((edge) => edge.source === selectedNode.id || edge.target === selectedNode.id) || [] : [];
  const evidenceIds = [...new Set((selectedEdge ? [selectedEdge] : relatedEdges).flatMap((edge) => edge.evidence_jd_ids))];
  const sampleSize = selectedEdge?.sample_size || data?.nodes.find((node) => node.type === "job")?.jd_count || 0;

  return <>
    <PageIntro kicker="岗位关系 · 技能连接 · 招聘依据" title="探索岗位与技能之间的联系" description="拖拽或缩放图谱，点击岗位、技能和关系即可查看详细要求与来源。" />
    <div className="toolbar"><label>岗位<select value={title} onChange={(event) => setTitle(event.target.value)}>{[...new Set([...focus, ...jobs.map((job) => job.standard_job_title)])].map((item) => <option key={item}>{item}</option>)}</select></label><div className="data-chip">{data?.summary.node_count ?? 0} 节点</div><div className="data-chip">{data?.summary.edge_count ?? 0} 关系</div></div>
    <ProfileSourceBadge info={data} />
    <StatusBanner>{data?.notice || "岗位与技能关系均可追溯到真实招聘信息。"}</StatusBanner>
    <div className="graph-layout"><article className="panel graph-canvas"><ReactECharts option={option} style={{ height: 560 }} onEvents={{ click: (params: { dataType: string; data: { id: string } }) => { if (params.dataType === "node" || params.dataType === "edge") setSelected({ kind: params.dataType, id: params.data.id }); } }} /></article><aside className="panel node-detail"><div className="panel-title"><span>节点与关系详情</span><small>点击图谱查看</small></div>{selected ? <><h2>{selectedNode?.name || `${selectedEdge?.job_title || title} → ${selectedEdge?.skill_name || "技能"}`}</h2>{selectedNode ? <><p>岗位/技能ID：{selectedNode.id}</p><p>类型：{selectedNode.formal_type || selectedNode.type}</p><p>分析样本：{selectedNode.jd_count ?? sampleSize} 条JD</p><p>关联关系：{relatedEdges.length} 条</p></> : null}{selectedEdge ? <><p>关系：{selectedEdge.relation_type || selectedEdge.relation || "岗位要求"}</p><p>技能证据：{selectedEdge.evidence_count} 条JD提及</p><p>出现频率：{sampleSize < 3 ? "小样本不形成频率结论" : `${selectedEdge.evidence_count}/${sampleSize} · ${Math.round(selectedEdge.frequency * 100)}%`}</p></> : null}<h3>技能证据</h3><div className="tag-list">{evidenceIds.length ? evidenceIds.map((id) => <span key={id}>{id}</span>) : <em>当前招聘信息未命中标准技能词典</em>}</div><p>可依据招聘信息编号在多源数据页追溯来源链接与采集信息。</p></> : <div className="empty-state">点击图中的岗位、技能或连线，查看岗位样本和技能证据。</div>}</aside></div>
  </>;
}
