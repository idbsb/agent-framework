import { useEffect, useState } from 'react';
import { getJson } from '../api';
import { StatusBanner } from './Layout';

export type WindowSamples = { before: number | null; after: number | null; minimum: number };
export type Quality = { raw_evidence_count: number; independent_evidence_count: number; exact_duplicate_count: number; near_duplicate_group_count: number; source_count_raw?: number; source_count_normalized?: number; company_count_raw?: number; company_count_normalized?: number; time_quality: { published_at_coverage: number | null; time_quality: string; fallback_count: number } };

export function QualitySummary({ data, windows }: { data?: Quality | null; windows?: WindowSamples }) {
  return <section className="panel" aria-label="数据科学性提示"><div className="panel-title"><span>数据质量与趋势边界</span><small>只读派生统计</small></div>
    {windows ? <p>前窗口 {windows.before ?? '未知'} 条 · 后窗口 {windows.after ?? '未知'} 条 · 最低门槛 {windows.minimum} 条。达到门槛不代表统计显著。</p> : null}
    {data ? <><p>原始证据 {data.raw_evidence_count} · 独立证据估计 {data.independent_evidence_count} · 完全重复冗余 {data.exact_duplicate_count} · 近重复组 {data.near_duplicate_group_count}</p>
      <p>有效发布时间覆盖率 {data.time_quality.published_at_coverage == null ? '未知' : `${(data.time_quality.published_at_coverage * 100).toFixed(1)}%`} · 时间质量 {data.time_quality.time_quality}</p>
      {data.time_quality.fallback_count > 0 ? <StatusBanner tone="warning">部分记录缺少原始发布时间，趋势计算使用采集时间回退。回退记录 {data.time_quality.fallback_count} 条。</StatusBanner> : null}
      {data.source_count_raw != null ? <p>来源名称 原始 {data.source_count_raw} / 规范化 {data.source_count_normalized} · 企业名称 原始 {data.company_count_raw} / 规范化 {data.company_count_normalized}</p> : null}</> : <p>质量元数据尚未提供，不从缺失信息推断可靠性。</p>}
    <small>重复组为保守检测估计，不等于统计独立性；未删除、合并或改写原始记录，未改变正式评分。</small></section>;
}

export function safeEvolution<T extends { growing_skills?: string[]; declining_skills?: string[]; new_skills?: string[]; stable_skills?: string[] }>(data: T, fallback: boolean) {
  // Offline JSON is frozen and may predate both-window checks: never trust its labels.
  return fallback ? { ...data, growing_skills: [], declining_skills: [], new_skills: [], stable_skills: [], sample_insufficient: true, sample_insufficient_skills: [], trend_status: 'insufficient_sample', sample_notice: '静态正式演化结果缺少已验证的双窗口质量信息，已隐藏趋势分类。' } : data;
}

export default function DataQualityPanel() {
  const [data, setData] = useState<Quality | null>(null);
  const [error, setError] = useState('');
  useEffect(() => { getJson<Quality>('/api/quality/report').then(r => setData(r.data)).catch((e: Error) => setError(e.message)); }, []);
  return <>{error ? <StatusBanner tone="warning">质量报告暂不可用：{error}</StatusBanner> : null}<QualitySummary data={data} /></>;
}
