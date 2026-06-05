集中配置目录说明

- `.env`：应用通用配置，建议放数据库、Redis、MinIO、大模型、短信、微信等环境变量。
- `kingdee/`：放金蝶 `conf.ini` 或同类 ERP 接入配置。
- `sql/`：放数据库初始化和结构变更脚本。

推荐新增变量：

```env
MINIO_ENDPOINT=127.0.0.1:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=supply-chain-agent
MINIO_SECURE=false
MINIO_PUBLIC_BASE_URL=
PO_HISTORY_SYNC_START_DATE=2025-01-01T00:00:00
KINGDEE_CONFIG_PATH=config/kingdee/conf.ini
```
