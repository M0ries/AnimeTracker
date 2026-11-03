# AT 同步后端（准备阶段）

这是网页版及 Tauri 桌面版共用的 Supabase 表与乐观锁函数；尚未连接到界面，不会上传用户资料。需要用户自己的 Supabase 项目，在 SQL 编辑器运行 `supabase.sql`。公开的 Project URL 和 publishable key 可写入前端配置；不要把数据库密码或 service role key 写入 GitHub。

每个用户一份 JSON 快照，`at_compare_and_swap` 在版本变化时拒绝写入。客户端必须保留离线副本、验证完整备份，并在同时改动时提示冲突；未实现这些步骤前不应启用自动上传或整库覆盖。
