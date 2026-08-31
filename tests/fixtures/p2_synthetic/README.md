# SYNTHETIC TEST DATA

NOT REAL RECRUITMENT DATA / NOT A REAL PERSON

本目录仅含本地虚构逻辑测试数据，不代表真实企业招聘、真实简历或市场趋势。
不含个人姓名、联系方式或身份信息。BOSS 来源别名测试仅验证仓库已有的字符串映射，
不声称该平台发布了本目录的任何岗位。

- synthetic_fixture.py：小型 JD、窗口及指标工厂。
- synthetic_browser_fixture.json：本地 HTTP/浏览器质量检查输入。
- synthetic_gold.json / synthetic_predictions.json：故意含错误的指标算术示例。
- runtime-*：忽略的 TemporaryDirectory，仅由 tests/p2_local_server.py 使用，关闭时自动释放。

不得将本目录内容导入正式 data/、outputs/、Excel 或现有业务数据库。
