# backend_job_advisor

Python 后端，依赖由 [uv](https://github.com/astral-sh/uv) 管理。

## 初始化

```bash
cd backend_job_advisor
uv sync
cp .env.example .env
```

本地 `.venv` 由 `uv sync` 创建，勿提交到 Git。

## 启动 API（FastAPI）

四类存储在应用 **lifespan** 中初始化，依赖注入见 `src/storage/deps.py`。探活：`GET /health/storage`（Mongo / Redis / ES / Chroma）。

```bash
# Chroma 默认占用 8000，API 建议用其它端口，例如 8080
uv run uvicorn api.main:app --reload --host 0.0.0.0 --port 8080
```

## 基础设施

**仅核心栈**（MongoDB、Redis、Elasticsearch 及控制台；推荐先这样启动）：

```bash
docker compose up -d
```

**再加 ChromaDB（向量库）**：

```bash
docker compose -f docker-compose.yml -f docker-compose.chroma.yml up -d
```

不要使用 `docker compose up -d --build`，除非你自己在 compose 里写了 `build:`；当前编排只有预构建镜像。

### 出现 `failed to read expected number of bytes: unexpected EOF`

通常是**拉镜像时网络中断**或**层缓存损坏**（ES 等层较大时常见）。可重试 `docker compose pull`，或换网络/暂时关闭代理后再拉。

### 数据库初始化脚本

| 存储 | 路径 | 说明 |
| --- | --- | --- |
| MongoDB | `db/mongodb/init_collections.js` | `mongosh` 执行，创建集合与索引 |
| Elasticsearch | `db/elasticsearch/*.json` + `init_indices.ps1` | 创建 `job_advisor_facts`、`job_advisor_jobs` |
| ChromaDB | `db/chroma/README.md` | 集合与 metadata 约定（无 SQL） |

详见 `docker-compose.yml` 与 `docker-compose.chroma.yml`。
