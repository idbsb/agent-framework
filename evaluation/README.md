# 独立评测框架

本目录只读取 gold labels 与 system predictions，不参与抽取、词典、匹配或画像发布。
**Synthetic regression result ≠ Real-world accuracy。当前未产生真实业务准确率结论。**

## 输入契约

两个 UTF-8 JSON 文件各为记录列表。每条记录包含唯一 `id`，`skills` 为
`[{"skill":"标准 skill_id 或一致的标准名称","polarity":"affirmed"}]`，可选 `fields` 对象。
支持 affirmed / negated / planned / other_person / uncertain；必须显式提供极性。
gold 与 prediction 必须使用同一套标准 ID/名称。本程序不调用抽取器推断 gold、不改写标签。

字段未出现表示未标注，不进入该字段分母；显式 null 表示人工标注为 unknown。
缺少 prediction 字段不等于 null 正确。缺失预测样本保留为错误，多余预测样本技能计 FP。
同一记录重复 skill+polarity 只计一次；重复样本 ID、空技能名称、非法极性拒绝处理。

## 指标（micro，0–1）

- TP：同一记录中，技能及极性同时正确。
- FP：预测集合中有、gold 没有的技能+极性。
- FN：gold 中有、预测没有的技能+极性。
- Precision = TP / (TP + FP)。
- Recall = TP / (TP + FN)。
- F1 = 2TP / (2TP + FP + FN)。
- 同时返回仅 affirmed 的正向指标；把 negated 预测为 affirmed 将产生正向 FP，绝不会记为正向 TP。
- 字段 Exact Match / Accuracy = 精确匹配的已标注字段数 / 已标注字段数；不自动大小写/语义模糊对齐。
- 技能集合 Exact Match：gold 样本中存在预测且技能+极性集合完全一致的比例。
- 零分母返回 null，不把空 gold/空预测宣称为 100%；有 gold 无预测时 Recall/F1=0。
- 每条错误给出 ID、FP、FN、字段 gold/prediction 和字段是否存在，不筛选有利子集。

## 运行

在项目根目录：

```powershell
.\.venv\Scripts\python.exe -B -X utf8 -m evaluation --gold tests/fixtures/p2_synthetic/synthetic_gold.json --predictions tests/fixtures/p2_synthetic/synthetic_predictions.json
```

只向标准输出打印结果，不生成/覆盖业务 Excel、JSON 或数据库。合成示例包含故意的错误，用于核对数学，不代表模型业务表现。

## 真实评测限制

仓库已有 27 条标准化测试简历及人工参考字段。既有设计文档明确技能字段不是完整 Gold Standard，
岗位/技能规则也使用当前正式数据，不能把它冒充未见过的独立真实测试集。
本轮未修改、重标、挑选其标签，也未将旧参考字段自动推断成五种极性真值。
**BLOCKER / 独立真实标注数据及来源、划分和适用任务需团队提供或确认。**
不获取外部 JD、简历或数据集，不宣称达到 ≥90%。
