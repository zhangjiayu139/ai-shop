# 首页三步充值 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将已确认效果图实现为本地可操作 Vue 首页，单个充值合并为三步，保留其他功能和原业务边界。

**Architecture:** HomeView 作为同一 RechargeView 的薄入口，RechargeView 自带公共品牌页头与次要入口；两条路由复用同一个流程。维持旧 sessionStorage 记录的四步编号语义，用纯函数映射到三步展示，避免旧进度错页。

**Tech Stack:** Vue 3、TypeScript、Vue Router、Vue I18n、现有主题变量、Vitest、Vue Test Utils、jsdom。

## Global Constraints

- 用户已批准截图设计并要求继续；当前会话执行，不重复询问设计方向。
- 初始阶段只改本地；2026-09-09 用户追加授权“修复review的P2问题，并部署到服务器上”，允许下述前端发布；仍不提交或推送 Git。
- 保留原有未提交改动；在 feat/recharge-home-three-step 分支继续。
- 不改后端、卡密/订阅/计费/鉴权规则；真实充值接口仅在测试中以 fetch 替身验证调用边界。
- 保留 Session 和邮箱方式、后台配置品牌、主题与语言切换、现有卡密恢复和结果轮询。
- 不新增凭证存储。测试及截图仅使用 example.invalid 邮箱和明确的假凭证。

## Task 1：合并流程与进度兼容

**Files:** 修改 frontend/src/views/user/RechargeView.vue；新增 frontend/src/views/user/recharge-progress.ts、recharge-progress.test.ts、recharge-home.test.ts；适配原 recharge-reset.test.mjs。

**Interfaces:** `serializeRechargeStep(step: number): number` 将 1/2/3 存成原来的 1/3/4；`restoreRechargeStep(saved): 1 | 2 | 3` 将旧凭证页回到填写页、带预检 token 的旧3恢复确认页、带兑换 token 的旧4恢复结果页。

- [x] 基线：`node --test src/views/user/recharge-reset.test.mjs`、`npx vitest run src/router/setup-status.test.ts`。
- [x] RED：增加真实组件测试，同时可见 CDK 与 Session、仅三步、卡密预览后自动凭证预检而不提交；增加纯函数映射用例。

```ts
expect(serializeRechargeStep(3)).toBe(4)
expect(restoreRechargeStep({ step: 4, redemptionToken: 'test' })).toBe(3)
expect(restoreRechargeStep({ step: 3, preflightToken: 'test' })).toBe(2)
expect(restoreRechargeStep({ step: 2 })).toBe(1)
```

- [x] 运行新增测试，确认是缺少三步表单、兼容映射或自动预检造成的失败。
- [x] GREEN：第一步单一 form submit，按钮锁住整条校验链；preview 成功后调用现有 preflight；只有确认按钮调用 redeem。
- [x] 增加失败/并发/重置用例：无效卡密不预检、凭证失败不推进、请求异常展示错误、重复点击不重复请求、旧响应不覆盖新输入、回退修改失效旧预检。
- [x] 保留恢复已兑换卡密能力；结果阶段使用独立轮询代次，重置或卸载后旧请求不能覆盖当前状态。
- [x] 运行 `npx vitest run src/views/user/recharge-progress.test.ts src/views/user/recharge-home.test.ts` 与已有凭证清理测试，确认通过。

## Task 2：首页效果稿与响应式

**Files:** 修改 HomeView.vue、RechargeView.vue、frontend/src/i18n/locales/zh.ts 和 en.ts；不改全局后台 CSS。

**Interfaces:** HomeView 模板仅为 `<RechargeView />`；路由 `/` 和 `/recharge` 保留原定义及参数；复用 `siteBrand`、LanguageToggle、ThemeToggle。新增文案集中在 `rechargeHome` 命名空间。

- [x] RED：首页真实挂载出现卡密/凭证；三个轻量入口 href 为 /batch、/history、/billing；语言切换后主要表单文案切换。
- [x] 按已批准图实现页头、标题、三个按钮、三步条、840px 主表单、帮助区和页脚。CDK 与凭证同屏，清空仅作用凭证。表单宽度以效果图落地比例微调。
- [x] 确认页突出目标账号/套餐，订阅事实可展开但不删除；欠费与已满足套餐规则保持。
- [x] 375px 下内边距16px、次要按钮可换行、输入字号16px；暗色使用原主题变量。所有新增字段有 label，错误有文字与无障碍关联。
- [x] GREEN：运行组件及已有测试；`npm run build`；只针对修改文件检查格式/差异，不调用带自动修复的全仓 lint。

## Task 3：本地预览与验收

**Files:** 测试/截图产物放独立本地临时目录，更新本计划的实测结果。

- [x] 启动独立 localhost 开发预览，不接生产兑换。visual-preview 中间件拦截全部 /api 请求，业务默认503；独立QA浏览器仅用假数据替身。
- [x] 组件测试验证首页、/recharge 参数、第一步错误、Session 与邮箱、确认、处理中/成功/待核查、再兑一张及输入清理；真实浏览器另检查布局和主流程。
- [x] 1440px、768px、375px 三种宽度以及明暗/中英文检查：无横向溢出，主操作与三个辅助入口均可见。
- [x] 按 requesting-code-review 请求独立只读复核；仅审查相对本轮基线的差异，不带入旧修改。发现1项重要问题已修复并复核通过，无剩余阻断。
- [x] 最终展示本地预览入口和截图；说明未部署、未做真实充值，不声称服务器问题已解决。

## 实测记录

2026-09-09 本地验证：

- 最终 Vitest 四文件41项通过，原有 Node 凭证清空测试3项通过；包含审查后增加的3项拒绝/不确定状态回归。覆盖实际Vue组件与路由，不调用真实API。
- 审查发现明确400拒绝且无订单时可能卡住；已通过RED/GREEN修复为返回填写重新校验，清除预检token与摘要。网络不确定、5xx或存在订单证据仍保持结果查询与防重复保护。
- `npm run build` 通过；保留现有依赖PURE注释及大包告警。
- `git diff --check` 通过。
- `vue-tsc --noEmit` 启动失败：旧vue-tsc与已锁定TypeScript不兼容，报 supportedTSExtensions 搜索失败；未扩大范围升级工具链。
- 定向ESLint无法运行：仓库无ESLint配置；未自动生成配置或执行全仓修复。
- 本地入口 http://127.0.0.1:5178/ ，以 `npm run dev -- --mode visual-preview --host 127.0.0.1 --port 5178 --strictPort` 启动。无后端代理；正式构建不含预览中间件。
- 桌面、手机及手机暗色英文截图：工作区根 `output/playwright/cdk-home-*.png`，仅空表单或明确假数据。
- 未部署服务器、未重启Docker、未执行真实充值，尚不能视为线上联调完成。

## 追加授权：P2 修复与服务器发布（2026-09-09）

- 已修复：兑换明确返回401/403拒绝，且不存在订单对象、订单ID或订单状态时，返回填写页，清除旧预检token和账号摘要；必须重新校验并明确确认，不自动重复兑换。
- 保留保护：网络异常、5xx、409及存在订单证据时仍停留结果页；新增顶层/嵌套 `id` 保护。此次不修复账单查询401。
- TDD：新增4项授权拒绝用例先失败再通过；最终 Vitest 51项、Node凭证清空3项，共54项通过。构建及 `git diff --check` 通过；独立只读复核未发现新增阻断。
- 已发布至 https://cdk.edujerry.icu/ ，镜像 `gpt-cdk:20260909-home-three-step-p2`；仅更新前端，后端二进制哈希与原版本一致。
- 在线SQLite备份及发布后完整性检查通过，沿用原数据目录和JWT密钥。Caddy与TaoAi容器未重启。
- 线上首页与主脚本哈希匹配本地产物，HTTPS首页/静态资源200，后台匿名请求401符合预期。浏览器刷新后正确显示三步表单与三个辅助入口，控制台0错误；未提交真实充值。
- 初次外网验证发生短暂连接关闭，重试后恢复，不能据此保证长期网络稳定。
- 发布和回滚记录见工作区根目录 `zovo-frontend-deployment-2026-09-09.md`。上方“未部署”属于追加授权之前的历史记录。
