# v1.4.29 定制升级

基线：本站 v1.4.27（a1e0992）。上游：`zovocard/zovo_card_cdk_auto` 正式标签 v1.4.29（d831397eb87613044867522240bfc37be15a6eb5），2026-10-10 发布。

## 合入与保留

- 合入 Grok 套餐目录、发码/US 地区、单笔和批量兑换、凭证解析、中英文提示；合入 Pro 20x 续费后的自动续费提醒。
- 保留原品牌、蓝色界面、三步首页、CDK/凭证同屏、默认展开、凭证清空、异步失效/防重复提交、上游授权错误映射和地区可空字段语义。
- Grok 预检不返回票据，仅成功预检后允许手动确认，再携带内存中的登录态兑换；刷新确认页需要重新验证。登录态不进入浏览器进度缓存或 GPT 账单绑定。GPT/X 仍需要预检票据。
- 保留 X 目录失败时拒绝发码并扩展至 Grok；拒绝产品与套餐不匹配的请求，Grok 公开目录失败不回落为 GPT。批量无票据路径按预览套餐识别产品，不能仅凭用户输入的 Cookie 放行。
- 不升级依赖，不改数据库结构、认证、JWT、数据库路径、主题或代理配置。
- 独立审查发现并修复两项 P1：后端逐项解析 Cookie，防止分号后多空格/Tab 使 Grok 登录态误入账单库；无邮箱/账号标识的 Excel 行改用完整凭证去重，防止同前缀同长度账号被误删而配对错位。两项均已红→绿复现，包括真实 XLSX 导入至自动提交链路。

## 验证

```sh
cd backend
go test ./... -count=1
go vet ./...
go test -race ./internal/cardplatform ./internal/db ./internal/handler
cd ../frontend
npx vitest run --exclude '**/*.test.mjs'
node --test src/views/user/recharge-reset.test.mjs
npm run test:grace-recovery
npm run build
```

新增 Grok 发码测试和三步页面测试先在旧实现失败、合入后通过；包括阻塞原因、刷新无凭据、GPT 不放宽、批量产品分流与 SQLite 不落 Grok 登录态。Node 测试单独运行，不由 Vitest 收集。

本次通过：83 项 Vitest、3 项 Node、宽限期脚本、Go 全包/vet/关键包 race、生产构建。隔离首页浏览器样式保持原三步界面且无控制台错误。依赖注释和测试脚本生命周期警告仍存在。

## 发布边界

发布前在线备份 SQLite、Compose/Caddy、JWT，Linux/CGO 构建后在空临时数据容器验证，随后只切换 app。保留旧镜像；回滚只换回应用，不回灌数据库覆盖新订单。

**Grok 实际兑换依赖卡台服务端升级支持**，上游明确旧卡台可能“可发不可兑”。本次不执行真实发码、兑换、扣款、退款或取消订阅，自动化和页面检查不能视为真实充值验收。
