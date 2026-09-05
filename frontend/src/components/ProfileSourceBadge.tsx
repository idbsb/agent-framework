export type ProfileSourceInfo = { profile_source?: string; profile_version?: number | null; profile_id?: string | null; profile_fingerprint?: string | null };

export default function ProfileSourceBadge({ info }: { info?: ProfileSourceInfo | null }) {
  if (!info) return null;
  const label = info.profile_source === "published_dynamic"
    ? `已发布画像 V${info.profile_version}（已审核）`
    : info.profile_source === "jd_aggregate"
      ? "真实招聘信息聚合"
      : "真实招聘信息聚合";
  return <p className="data-chip" data-testid="profile-source">岗位画像来源：{label}</p>;
}
