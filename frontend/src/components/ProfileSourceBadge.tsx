export type ProfileSourceInfo = { profile_source?: string; profile_version?: number | null; profile_id?: string | null; profile_fingerprint?: string | null };

export default function ProfileSourceBadge({ info }: { info?: ProfileSourceInfo | null }) {
  if (!info) return null;
  return <p className="data-chip" data-testid="profile-source">当前岗位画像：{info.profile_source === "published_dynamic" ? `已发布画像 V${info.profile_version}` : "静态基线（无已发布版本）"}</p>;
}
