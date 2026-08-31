# P2 原始数据完整性清单（开始前）

日期：2026-08-31；分支 feature/p2-enhancement；HEAD 0f0c88a；工作区开始时干净。

只记录路径、字节数和 SHA-256，不复制数据正文。保守覆盖全部现有 Excel/CSV/JSON/NDJSON/SQLite/PDF/DOCX，包括原有验收数据库和 JSON；排除 .git、依赖、构建目录及测试目录。新增测试仅可在明确 synthetic fixture 或临时目录。现有清单 63 个文件。

```json
[
  {
    "path": ".codex_artifacts/p0/browser-results.json",
    "size": 21092,
    "sha256": "b5dfd9b6776dd5bcaf7c1dc7b890a9674a36d1d43299e29ab8ddb414178d8b24"
  },
  {
    "path": ".codex_artifacts/p0/system-qa/system_qa_results_graph_dynamic_v2.json",
    "size": 3470,
    "sha256": "dbe1922065db67aaaabf42c6e4ec6415279a7945364d33821f7e45d2bc4d6945"
  },
  {
    "path": ".codex_artifacts/p1/browser-1788179587539/results.json",
    "size": 1668,
    "sha256": "ac765e14f8dd041e3ebcdc6e9d48188c95c3ad146ecdecbff41e8fb0c85db450"
  },
  {
    "path": ".codex_artifacts/p1/browser-1788179776783/results.json",
    "size": 1764,
    "sha256": "fd99cfd499ca5cc4ed7e54a0458c247f2fa6a9473d14e62fd1fc357f64cc5846"
  },
  {
    "path": ".codex_artifacts/p1/browser-1788180023439/results.json",
    "size": 1648,
    "sha256": "fd03d458fdb6794e42c5d35127c1480e40b8da4a9ac88ab9b7e3f6bd3fccd109"
  },
  {
    "path": ".codex_artifacts/p1/browser-1788182744552/results.json",
    "size": 1648,
    "sha256": "702ba5f468d7b05bf1afc1677436f1cd62ec936f0d71cc9835397baff7989307"
  },
  {
    "path": ".codex_artifacts/p1/downstream-1788182751265/results.json",
    "size": 2334,
    "sha256": "2a6a2e88d33d65de3ff07aa92a1d58d614261453d48125d42007bf48e7e65f05"
  },
  {
    "path": ".codex_artifacts/p1/downstream-1788182893242/results.json",
    "size": 2334,
    "sha256": "1f0184a178af921678ab45f239efe1ba25e11417ad33586cb5833197d39aaf57"
  },
  {
    "path": ".codex_artifacts/p1/downstream-final-20260831.sqlite3",
    "size": 561152,
    "sha256": "56c45d0a2781c56581947b2e886aa1a966497d01fe07c0a8574df9a1e64fb419"
  },
  {
    "path": ".codex_artifacts/p1/downstream-integration-20260831.sqlite3",
    "size": 16830464,
    "sha256": "4faf54ca50c293b6193557a80ffe08c859013d8a66024e50c6e66a4e12d55785"
  },
  {
    "path": ".codex_artifacts/p1/downstream-system-qa-final/system_qa_results_graph_dynamic_v2.json",
    "size": 3470,
    "sha256": "8b7c2940d65bcb71ca3639c528963f4441bf873be5e7d368c741516f1e839002"
  },
  {
    "path": ".codex_artifacts/p1/downstream-system-qa/system_qa_results_graph_dynamic_v2.json",
    "size": 3470,
    "sha256": "c1dd3cc24f2ea51a8f9784de71138e07506dc0c168c2d447b4b33943f3e749df"
  },
  {
    "path": ".codex_artifacts/p1/e2e-20260831-2035.sqlite3",
    "size": 16830464,
    "sha256": "8df58852e9778b97a623d04a5983f098344f1328dabe5cd022d8bc2153719e39"
  },
  {
    "path": ".codex_artifacts/p1/e2e-20260831-2048.sqlite3",
    "size": 16830464,
    "sha256": "55406c4a86c094c1614f8a18d497af84bc8d8197b9ef3d2b057a1eb5155744bf"
  },
  {
    "path": ".codex_artifacts/p1/e2e-final-20260831.sqlite3",
    "size": 16830464,
    "sha256": "e4f55b54fc5ee9f059bbad06a307e1e28cfa65c0ce60a01e82c0a5c11a8ee93f"
  },
  {
    "path": ".codex_artifacts/p1/system-qa-final/system_qa_results_graph_dynamic_v2.json",
    "size": 3470,
    "sha256": "f2744bcb5bc9b4a5600044ea68465a0b28f012fc4ff39a1b67fdc1c24b790acd"
  },
  {
    "path": "agent_framework/taxonomy.json",
    "size": 834,
    "sha256": "0b3476fb5f39d21d9ff510f5c513d222fd502e8d4b284022ec9708831feadbf1"
  },
  {
    "path": "config/skill_dictionary_extensions.json",
    "size": 806,
    "sha256": "8fc191984388aab52fef959e08fbc0be43679c71cbcdb5023aad5222cae4a97d"
  },
  {
    "path": "external_modules/graph_dynamic/3个重要岗位能力画像.xlsx",
    "size": 17800,
    "sha256": "52acf004a7723925736d2a06ea8ea0d940b062cf2e08e8e42d0dd525f2147983"
  },
  {
    "path": "external_modules/graph_dynamic/outputs/data_check_v1.json",
    "size": 832,
    "sha256": "ca2c88241feda3651631ea8730369b570750c40e5e9c949ca48022f5bb56469d"
  },
  {
    "path": "external_modules/graph_dynamic/outputs/graph_edges_v1.xlsx",
    "size": 72818,
    "sha256": "643591028bac3643b264467171b5c78cf732d4bacd42e56bc3b0b1e7547040f6"
  },
  {
    "path": "external_modules/graph_dynamic/outputs/graph_edges_v1.xlsx.inspect.ndjson",
    "size": 7720168,
    "sha256": "95bd281b2e1e6c06f136a4ffea68b678c2050c3a3f081bba28f68a076a37b91b"
  },
  {
    "path": "external_modules/graph_dynamic/outputs/graph_nodes_v1.xlsx",
    "size": 38812,
    "sha256": "145a556d62dfbd4c3d496b6a5db7523aee3abd757c62eb4f939f8eb6c3c3b7a1"
  },
  {
    "path": "external_modules/graph_dynamic/outputs/graph_nodes_v1.xlsx.inspect.ndjson",
    "size": 1400045,
    "sha256": "0bf9f4fa35ccdcc0a5dc643efaa3d7885711d88d18721fc220e3a308500e719e"
  },
  {
    "path": "external_modules/graph_dynamic/outputs/job_skill_evolution_v1.xlsx",
    "size": 65583,
    "sha256": "d46b7a8e72554f1707266c6ed00aa4fe371a423d042f5d56149a5a0cb23284e8"
  },
  {
    "path": "external_modules/graph_dynamic/outputs/job_skill_evolution_v1.xlsx.inspect.ndjson",
    "size": 7802916,
    "sha256": "4821a551a29fbf6f18ef76e8bc7af0e79e94cbad87c3dace00f2170ec769098b"
  },
  {
    "path": "external_modules/graph_dynamic/outputs/key_job_evolution_v1.json",
    "size": 219316,
    "sha256": "63c3c2f79849e0605ad8ca45700e09f06b927228624054ea5c8e08aacfc7b4a0"
  },
  {
    "path": "external_modules/graph_dynamic/outputs/key_job_graph_profiles_v1.xlsx",
    "size": 10252,
    "sha256": "c48bdfcf0e28ac3b77e1fd2be02185652f77e44c79f22148591c209270e6c187"
  },
  {
    "path": "external_modules/graph_dynamic/outputs/key_job_graph_profiles_v1.xlsx.inspect.ndjson",
    "size": 713808,
    "sha256": "edfa981c28c752d3bbc5a20f0a1703303c8c10267d54c82b1e434b2b49a507d4"
  },
  {
    "path": "external_modules/graph_dynamic/outputs/knowledge_graph_v1.json",
    "size": 843112,
    "sha256": "42ef1adb573ed7082eec020cea43642190e1386dd3ab45b37356aaa5663afa42"
  },
  {
    "path": "external_modules/graph_dynamic/outputs/qa_report_v1.json",
    "size": 870,
    "sha256": "66ab52a96219d1fb9a17e3ea92db1a159125106f00c56dff40a165be3736ecf3"
  },
  {
    "path": "external_modules/graph_dynamic/outputs/workbook_data_v1.json",
    "size": 960479,
    "sha256": "a0577ea1fec4f09243b08819b49b26ef6dbe50119ae070ebd422bb1787f45d93"
  },
  {
    "path": "external_modules/graph_dynamic/standard_job_title_mapping_v1.xlsx",
    "size": 20617,
    "sha256": "293b34dbb8e4e6f5689cf58387a38601f30feb759b46e7f34931bc1f6ff859b1"
  },
  {
    "path": "external_modules/graph_dynamic/standard_skill_dictionary_v1.xlsx",
    "size": 19794,
    "sha256": "178c64e654d3534878489e88aafc5a17b98fe361cb38db370f9036d01e5c1055"
  },
  {
    "path": "external_modules/graph_dynamic/standardized_jd_dataset_v1.xlsx",
    "size": 179341,
    "sha256": "b00a0220fd4b974d8b00bb57d6f0af3bb40f1d92cc7ddd59fcb0ddda9fc90ede"
  },
  {
    "path": "external_modules/graph_dynamic/重点岗位真实JD库.xlsx",
    "size": 215048,
    "sha256": "d0903fb823495a08415798374e2c558310536e6e4eac6a356ced80c4a129eef3"
  },
  {
    "path": "external_modules/graph_dynamic/重要岗位技能分析表.xlsx",
    "size": 16467,
    "sha256": "5adb55c786c704aa6c0c62835122138472b32d12992f128919e185c5b4549934"
  },
  {
    "path": "frontend/package-lock.json",
    "size": 68426,
    "sha256": "eb337be830c347f7c6612735e599d6dab6f967f942f53a8092b5d017a5a357e5"
  },
  {
    "path": "frontend/package.json",
    "size": 751,
    "sha256": "57dc6bc0d2179cd268ccabba7873e6cb55c26c5d7e1936bbb6abf546495ae0e1"
  },
  {
    "path": "frontend/tsconfig.app.json",
    "size": 529,
    "sha256": "c47893842c42c6137e589ae1440946cf7cb64ce1e7dc5af69fea30dfd5d43bbd"
  },
  {
    "path": "frontend/tsconfig.json",
    "size": 128,
    "sha256": "53a5de3ac873acc59864b5d565114c460d45f248e60e27ec84a2a621ad26d027"
  },
  {
    "path": "frontend/tsconfig.node.json",
    "size": 180,
    "sha256": "62ee70ccdb851cbc8277aa3e2255170cfa3cb3bd67fc99da6b5fe1be5cb0e094"
  },
  {
    "path": "frontend/vercel.json",
    "size": 141,
    "sha256": "475ed6fcb16d1fa6241b59cd9647b059eb88dc35ec43226b600d460a380fe889"
  },
  {
    "path": "multi_source_evidence_v1 (1).xlsx",
    "size": 10831,
    "sha256": "d10a690e95090ae8fb098c52e513832ddb8ca1ff81038b2dcd6eed4cab9e5603"
  },
  {
    "path": "multi_source_evidence_v1.json",
    "size": 13006,
    "sha256": "d0169670dd4d902b090145c0a245f4fc81a9da0059d2bdc3113c9b8e441927cc"
  },
  {
    "path": "outputs/emerging_jobs_v1.json",
    "size": 79996,
    "sha256": "473db51392b84ae5e603b2a3e1d26ec700d87590c8a72749267425ce46f6e4d0"
  },
  {
    "path": "outputs/emerging_jobs_v1.xlsx",
    "size": 22219,
    "sha256": "cb451ac09a23fc9885c474f5b08bb24da0e2e4db161754628eda18196e93c646"
  },
  {
    "path": "outputs/emerging_jobs_v1.xlsx.inspect.ndjson",
    "size": 208221,
    "sha256": "072639dc79be2cd7e43ff04da8364a18e9d1933a5281885a0049990fd6937b82"
  },
  {
    "path": "outputs/jd_parser_results_v1.xlsx",
    "size": 35582,
    "sha256": "eeb743bc28037b5384a4f0878d2434182efc2db2620938e6b53618e833726ef9"
  },
  {
    "path": "outputs/job_profiles_cleaned.xlsx",
    "size": 11105,
    "sha256": "bc6ecee35ae81255632164f8197afa98fa9f258df004b73ee4e5a4054e0fdb23"
  },
  {
    "path": "outputs/job_skill_analysis_cleaned.xlsx",
    "size": 12375,
    "sha256": "684c6807214d2853492b480f4886f304711b7804bfee68975fa71591703b499a"
  },
  {
    "path": "outputs/job_title_mapping_candidates.xlsx",
    "size": 11816,
    "sha256": "ebd231f3b5c9dce61b0394aa1036facc4907d4bf089dc073af45292ffac7a320"
  },
  {
    "path": "outputs/matching_results_v1.xlsx",
    "size": 12125,
    "sha256": "dc6d8748605b2bcbc04f6f592d586b9125a6fddef0e898a86a10390b9311828b"
  },
  {
    "path": "outputs/resume_annotation_review.xlsx",
    "size": 7920,
    "sha256": "4c4c031b79806dd5414629d6c521b97dc87e3ed74d5ca54aca8ad051f90e0868"
  },
  {
    "path": "outputs/resume_parser_results_v1.xlsx",
    "size": 9932,
    "sha256": "b100c5840d8154426bfb5beaee8d0ee74c1fe96eaa9af18592302577cdc5a897"
  },
  {
    "path": "outputs/skill_alias_candidates.xlsx",
    "size": 9929,
    "sha256": "0efa4917bf85cf07a7674575641c5da2f2f8f899ddc3e4a0152d8f951b26b715"
  },
  {
    "path": "outputs/standard_job_title_mapping_v1.xlsx",
    "size": 20617,
    "sha256": "293b34dbb8e4e6f5689cf58387a38601f30feb759b46e7f34931bc1f6ff859b1"
  },
  {
    "path": "outputs/standard_skill_dictionary_v1.xlsx",
    "size": 19794,
    "sha256": "178c64e654d3534878489e88aafc5a17b98fe361cb38db370f9036d01e5c1055"
  },
  {
    "path": "outputs/standardized_jd_dataset_v1.xlsx",
    "size": 179341,
    "sha256": "b00a0220fd4b974d8b00bb57d6f0af3bb40f1d92cc7ddd59fcb0ddda9fc90ede"
  },
  {
    "path": "outputs/standardized_resume_testset_v1.xlsx",
    "size": 17346,
    "sha256": "3b78edffd349055342818fff6b803b92d5bd1c1bd1de140e3764ef82c3ccd952"
  },
  {
    "path": "reports/formal_graph_evolution_baseline.json",
    "size": 2320,
    "sha256": "81c53bd35964e1ee2f80a578d68d6179060de4ba16fe4c72f516942b56f4f561"
  },
  {
    "path": "reports/system_qa_results.json",
    "size": 3095,
    "sha256": "9660f4e86b2f965b595e53e3db7e10bf3554d77cfbac86b9a72b36efe6d554e6"
  },
  {
    "path": "reports/system_qa_results_graph_dynamic_v2.json",
    "size": 3428,
    "sha256": "7abdda8366f29a2eb145532051fbde3a0f6ad5df463d72e6e1e16697faa9a8c9"
  }
]
```

