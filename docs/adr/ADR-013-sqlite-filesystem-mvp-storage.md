# ADR-013: SQLite and Filesystem for MVP Execution Storage

## 背景

本地单实例 Demo 需要 Job、账本和 Artifact 持久化，但尚无分布式吞吐或对象存储证据支持引入 Postgres/S3。

## 决策

结构化状态先用 SQLite，二进制与 Markdown Artifact 先用受限 Filesystem；领域只依赖 Repository 和 ArtifactStore Ports。

## 后果

部署简单、可离线测试且可恢复。代价是多实例写入、远程扩展、备份和大对象能力受限；后续 Adapter 可替换而不改变领域契约。
