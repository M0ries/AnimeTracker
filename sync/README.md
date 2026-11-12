# AT 多端同步配置

网页和 Tauri 桌面应用使用同一 Supabase 项目。项目 URL 和 publishable key 已配置在 `portable/cloud-sync.mjs`；公开客户端密钥受 `supabase.sql` 的用户行级策略保护。请勿填写 secret/service role key。

1. 在 **该项目**的 Supabase Dashboard → SQL Editor 中运行 `supabase.sql`。语句创建 `at_snapshots` 表、每用户读写权限、版本检查函数。
2. 在 Authentication → Providers 检查 Email 已启用。AT 设置 → 登录 / 注册同步账号；如果收到确认邮件，先确认后再登录。
   - Supabase 托管项目默认要求确认邮箱。内置邮件服务仅向项目团队邮箱发送，且有低发送上限；要让普通用户注册，请先在 Authentication → Emails → SMTP Settings 配置自定义 SMTP。不要把 SMTP 密码写进 AT 前端或仓库。若只是自己测试，可先用项目团队邮箱。
3. **先在有资料的设备登录并完成首次上传，再到空白新设备登录。** 首次连接时，两端各自已有不同记录会停止，不自动覆盖。
4. AT 在成功登录后、修改资料后以及运行时定期同步。离线修改保留本地副本，网络恢复后重试。两端同时修改会停止并提示冲突，需先导出完整 JSON 备份。

每次从云端替换本地资料前会验证备份并保留当前数据库。当前冲突不能自动合并，删除或重看记录以整份资料库同步；同账号不同设备之间请避免并发编辑。没有登录时完全本地运行。此版本不从 Kazumi 的 InfiniCLOUD 自动读取数据。
