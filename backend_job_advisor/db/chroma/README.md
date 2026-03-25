ChromaDB 为文档型向量库，**无 SQL 建表**。应用内使用固定 **collection 名称** 与 **metadata** 字段，与 ES 索引 `job_advisor_facts` 对齐。

| 项 | 约定 |
| --- | --- |
| Collection | `job_advisor_facts` |
| 向量 | 对 `content` 或 `value` 的 embedding（维度由所用嵌入模型决定） |
| Document id | 与 ES 文档 `fact_id` 一致，便于双写与删除 |
| Metadata（过滤用） | `user_id`, `predicate`, `status`, `category`, `subject`（均为 string） |

本地服务：`docker compose -f docker-compose.yml -f docker-compose.chroma.yml up -d`，默认 `http://localhost:8000`。
