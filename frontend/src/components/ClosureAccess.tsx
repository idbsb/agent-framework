import { useEffect, useState } from "react";
import { getJson, postJson } from "../api";
import { setClosureCredential } from "../closureAccess";

export default function ClosureAccess() {
  const [mode, setMode] = useState("unknown");
  const [token, setToken] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    getJson<{writes_enabled: boolean; auth_mode: string}>("/api/closure/access")
      .then(r => setMode(r.data.writes_enabled ? r.data.auth_mode : "disabled"))
      .catch(() => setMode("unavailable"));
  }, []);
  if (mode !== "bearer") return <p role="status">{mode === "local" ? "当前为本地写入模式。" : mode === "disabled" ? "后端已关闭写入；现有发布画像仍可读取。" : "正在确认写入权限，或后端暂不可用。"}</p>;
  return <form onSubmit={async e => {
    e.preventDefault(); setBusy(true); setMessage(""); setClosureCredential(token.trim()); setToken("");
    try {
      const result = await postJson<{actor: string}>("/api/closure/access/verify", {});
      setMessage(`已授权：${result.actor}。刷新页面后需重新授权。`);
    } catch (error) { setClosureCredential(""); setMessage(error instanceof Error ? error.message : String(error)); }
    finally { setBusy(false); }
  }}>
    <label>管理员写入密钥<input type="password" autoComplete="off" value={token} onChange={e => setToken(e.target.value)} /></label>
    <button disabled={busy || !token.trim()}>验证写入权限</button>
    <button type="button" onClick={() => {setClosureCredential(""); setToken(""); setMessage("已清除本页写入权限。");}}>清除写入权限</button>
    <p>密钥仅保存在当前页面内存，不写入浏览器存储；正式审核记录使用服务器配置的管理员身份。</p>
    <p role="status">{message}</p>
  </form>;
}
