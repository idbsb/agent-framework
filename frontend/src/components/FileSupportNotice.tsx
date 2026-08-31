import { useEffect, useState } from 'react';
import { getJson } from '../api';

export function FileSupportNotice() {
  const [message, setMessage] = useState('PDF/DOCX 解析依赖待批准，当前仅支持文本输入；不会自动上传或保存文件。');
  useEffect(() => { getJson<{ message: string }>('/api/resume/file/capabilities').then(r => setMessage(r.data.message)).catch(() => {}); }, []);
  return <section className="panel" aria-label="简历文件支持状态"><div className="panel-title"><span>PDF/DOCX 简历入口</span><small>依赖待批准</small></div><p>{message}</p><button disabled type="button">上传 PDF/DOCX（暂不可用）</button><p>本轮不支持扫描件 OCR。现有文本字段可编辑；提交前请确认技能、学历、工作经历和项目经历。</p></section>;
}
