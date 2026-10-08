# v1.4.27 定制升级

基线：本站 v1.4.24（`3bec7fd`）。上游：`zovocard/zovo_card_cdk_auto` 标签 `v1.4.27`，提交 `6346a29bded1dc49f319daca63ed9293832f9da8`。

## 合入范围

- X Premium 套餐目录、发码与单笔/批量凭证解析；X Cookie 不写入 GPT 账单 Session 缓存。X 目录不可用或套餐未开放时禁止发码，不降级到 GPT。
- 卡密付款地区持久化和两种列表展示；旧数据新增可空列，不重建或清空卡密表。未知地区保持“待同步”。
- 清除卡台已下架的产品缓存；空响应不清空缓存。不删除卡密、订单或选卡规则。
- Element Plus 按需注册（补齐本站后台图标）、Excel 按需加载、首页不等待站点配置、关闭生产 source map。

## 保留范围

保留本站品牌、蓝色工作台、主题选择、三步充值首页、CDK/凭证同屏、查询入口、详情默认展开、凭证清空、P2 授权失败处理、异步响应失效与防重复提交保护。

上游新主题默认值、主题形态重做和统一用户页头会覆盖既有设计，本次不合入这些视觉改版；版本号表示基于该标签的本站定制版，并非原样上游版本。未修改后台认证、数据库路径、JWT 密钥或反向代理配置。

## 验证与发布边界

```sh
cd backend && go test ./...
cd ../frontend
npx vitest run local-preview.test.ts src/element.test.ts src/lib/payment-region.test.ts src/lib/__tests__/plan.test.ts src/lib/__tests__/x-premium.test.ts src/router/setup-status.test.ts src/views/user/recharge-home.test.ts src/views/user/recharge-progress.test.ts
node --test src/views/user/recharge-reset.test.mjs
npm run test:grace-recovery
npm run build
```

发版前在线备份 SQLite、JWT 和 Compose/Caddy；原生 Linux/CGO 构建，独立临时容器健康检查后仅更新 `gpt-cdk-app`。保留原镜像，回滚只切换应用，不回灌数据库覆盖新增订单。

自动化测试使用合成数据，不代表真实供应商充值验收；不执行真实购码、扣款、取消订阅或退款。
