# 组员协作说明

## 第一次获取项目

```powershell
git clone https://github.com/idbsb/challenge-cup-job-skill-agent.git
cd challenge-cup-job-skill-agent
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python launch.py
```

## 修改代码的建议流程

每项功能单独创建分支，避免几个人同时修改主分支：

```powershell
git switch -c feature/功能简述
# 修改并测试
python -m unittest discover -s tests -v
git add .
git commit -m "说明本次修改"
git push -u origin feature/功能简述
```

推送后在 GitHub 创建 Pull Request，由至少一位组员检查后再合并到 `main`。

## 数据协作规则

- 不要把真实 JD Excel、简历、`data/challenge_cup.db` 或个人信息提交到 GitHub。
- 岗位必须保持稳定的 `job_id/JD编号`，后续更新继续使用原编号。
- 修改导入、技能抽取或人工复核逻辑时，必须补充测试并运行全部测试。
- API 的字段和行为发生变化时，同步更新 `API接口说明.md`。
