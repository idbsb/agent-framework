# 数据接口说明

## 1. 当前正式数据位置

| 数据键 | 实际位置 |
|---|---|
| `standardized_jd_dataset` | `C:\Users\87294\Documents\挑战杯\agent_framework\outputs\standardized_jd_dataset_v1.xlsx` |
| `standard_job_title_mapping` | `C:\Users\87294\Documents\挑战杯\agent_framework\outputs\standard_job_title_mapping_v1.xlsx` |
| `standard_skill_dictionary` | `C:\Users\87294\Documents\挑战杯\agent_framework\outputs\standard_skill_dictionary_v1.xlsx` |
| `standardized_resume_testset` | `C:\Users\87294\Documents\挑战杯\agent_framework\outputs\standardized_resume_testset_v1.xlsx` |

这4个文件是冻结正式数据，只读、不覆盖、不重新编号。配置入口为`config/data_sources.yaml`。

## 2. 数据文件与稳定内部字段

- JD：`jd_id`、`original_job_title`、`standard_job_title`、`responsibilities`、`required_skills_raw`、`bonus_skills_raw`、`education`、`experience`。
- 岗位映射：`jd_id`、`original_job_title`、`cleaned_job_title`、`standard_job_title`、`status`、`rationale`。
- 技能库：`skill_id`、标准技能名称、技能类别及别名映射。
- 简历：`resume_id`、`target_job`、`education`、`experience`、`work_experience`、`projects`、`skills_raw`及人工参考标注。

中文Excel字段到内部字段的映射位于`config/field_mapping.yaml`。

## 3. 如何更换JD文件

复制为新的版本文件，不覆盖旧版；确认字段兼容后只修改`config/data_sources.yaml`中的`standardized_jd_dataset.path`和`sheet`。

## 4. 如何增加新JD

在新版本JD文件中追加唯一`JD编号`，保留来源和原始文本；运行`python -m src.core.evaluate_core`。新增JD会经过解析、岗位候选和技能Evidence检查。

## 5. 如何增加技能

从上一版技能库复制为新版本，在“标准技能”Sheet末尾追加新技能。已有`skill_id`保持不变，新ID只追加，例如最大编号后加1；同时提升`config/version.yaml`的数据版本。

## 6. 如何新增技能别名

在新版本技能库“技能别名”Sheet追加原始写法、标准名称和已有`skill_id`。一对多拆分必须明确标记“拆分”并经过人工审核。

## 7. 如何调整匹配权重

修改`config/matching_weights.yaml`的`weights`，五项之和必须为1；核心代码无需修改。

## 8. 如何调用JD Parser

```python
from src.api.service import get_services
services = get_services()
result = services.jd_parser.parse({"jd_id":"JD-NEW","original_job_title":"Agent工程师","required_skills_raw":"Python、MCP"})
```

## 9. 如何调用Resume Parser

```python
result = services.resume_parser.parse({"resume_id":"CV-NEW","skills_raw":"Python、Docker"})
```

## 10. 如何调用Matching Engine

```python
resume = services.resume_parser.parse({"resume_id":"CV-NEW","skills_raw":"Python、Docker"})
result = services.matching_engine.match(resume, "AI Agent开发工程师")
```

## 11. API预留结构

- `POST /api/jd/parse`
- `POST /api/resume/parse`
- `POST /api/match`
- `GET /api/jobs`
- `GET /api/skills`

运行：`uvicorn src.api.app:app --host 127.0.0.1 --port 8000`。OpenAPI文档位于`/docs`。

## 12. 数据版本管理

`config/version.yaml`保存`data_version`、`schema_version`、`updated_at`和`source`。更新时创建新文件、递增版本、保留旧文件及其哈希；公共Schema字段只做向后兼容追加。
