# 一次性接码 CDK 系统设计

日期：2026-09-16
状态：已确认范围，待实施
目标项目目录：`/Users/zhangjiayu/Desktop/project/study/ai/ai-shop/codex-sms-cdk`

## 1. 目标

建设一个独立的一次性短信接码兑换系统：

- Dujiao-Next 继续负责商品、订单、支付和发放 CDK。
- 新系统负责生成 CDK、校验兑换、申请一次性号码、展示号码、轮询短信和展示验证码。
- MaDao 作为内部供应商网关，首期接入 HeroSMS 和 5SIM。
- 首期只支持 OpenAI/Codex 合法的个人验证场景。
- CDK 只有在上游实际收到短信后才核销；没有收到短信时不消耗用户权益。

## 2. 本期不做

- 30/60/90 天租号。
- 同一号码长期保留和按月续费。
- 自动注册、批量养号、代理/VPN、账号交易或绕过平台风控。
- Dujiao-Next 订单回调和支付接口二次开发。
- 用户余额、充值、退款钱包。
- 任意网站、任意短信发送方的通用接码。

## 3. 方案选择

采用“独立业务系统 + 私网 MaDao + 复用现有基础设施”的方案：

```text
Dujiao-Next --发放CDK--> 用户浏览器
                            |
                            v
                   一次性接码业务系统
                   | 复用 PostgreSQL 15（独立库/账号）
                   | 复用 Redis 7（DB 2 + 独立前缀）
                   | 后台任务
                            |
                            v
                     MaDao 私网 API
                     |            |
                     v            v
                  HeroSMS       5SIM
```

不修改 MaDao 的业务模型，不把 MaDao 直接暴露到公网。MaDao 使用官方 Docker 版本运行在独立的 provider 网络中，只允许业务 API/Worker 访问，同时保留访问 HeroSMS/5SIM 公网 API 的出站能力。

### 3.1 现有服务器复用方案

2026-09-16 的只读检查结果表明，当前服务器可以承载 V1：4 vCPU、总内存约 7.8 GiB、可用内存约 6.8 GiB、磁盘剩余约 82 GiB，系统负载低。现有 PostgreSQL、Redis 和商城应用容器均健康。服务器没有 swap，因此必须保留容器内存上限和 1.5 GiB 可用内存发布门槛。

- PostgreSQL：复用 `taoai-shop-postgres`（PostgreSQL 15.19），新建独立数据库和账号，均命名为 `codex_sms_cdk`；角色连接上限 10，API 连接池最大 6、Worker 最大 4。禁止使用商城数据库 `taoai_shop` 的 schema 或账号。
- Redis：复用 `taoai-shop-redis`（Redis 7.4.11），固定使用 DB 2 和键前缀 `smscdk:`；所有键必须有 TTL，只保存限流、短锁和短期缓存，PostgreSQL 是唯一事实来源。禁止 `FLUSHDB`、`FLUSHALL` 和无前缀批量删除。
- Caddy：复用现有 `gpt-cdk-caddy`，把 API 加入外部网络 `taoai_shop_front`，通过受控配置片段增加反向代理；不得再创建占用 80/443 的 Caddy 容器。
- 数据网络：API 和 Worker 加入现有内部网络 `taoai-shop_backend`，通过容器名访问 PostgreSQL/Redis；不把 5432、6379 映射到宿主机。
- 供应商网络：新建普通 bridge 网络 `codex_sms_provider`，API、Worker、MaDao 按需加入；不发布 MaDao 的 7822 端口。

生产环境只新增三个容器：`codex-sms-api`、`codex-sms-worker`、`codex-sms-madao`。建议资源上限分别为 512 MiB/1 CPU、384 MiB/1 CPU、512 MiB/1 CPU。

### 3.2 复用边界与拆分条件

- 首批灰度限制为 50 个并发等待短信会话；Mock MaDao 压测通过后开放到 100 个并发，轮询间隔保持 3–5 秒。
- 超过 100 个并发、PostgreSQL 总连接持续超过 70、CDK 角色连接达到 9、Redis 内存超过 70%，必须重新做容量评估后才能扩容。
- Redis 内存持续超过 50%、引入不受信任插件、或接码系统由独立团队运维时，迁移到独立 Redis/ACL 用户，不继续共享实例。
- Redis DB 编号只是逻辑命名空间，不是权限隔离；MaDao 不加入 `taoai-shop_backend`。Redis 不可用时，取号、兑换和限流相关写接口返回 503，状态查询仍从 PostgreSQL 提供，禁止绕过限流继续购买号码。
- 发布接码系统不得重建、重启或修改现有 PostgreSQL/Redis 容器；部署前后必须核对现有容器 ID、启动时间和健康状态未变化。

## 4. 产品定义

首期只有一个商品权益：

- SKU：`OPENAI_OTP_SINGLE`
- 权益：成功接收一条 OpenAI/Codex 验证短信。
- 默认 CDK 有效期：生成后 180 天，可在批次创建时调整。
- 一枚 CDK 同一时间只能存在一个进行中的兑换。
- 收到短信前允许取消、超时和换号；收到任何目标短信后 CDK 立即核销。
- 每枚 CDK 24 小时内最多创建 5 个上游号码，防止恶意消耗供应商资源。
- 验证码收到后保留 24 小时，之后删除短信正文和验证码，只保留脱敏审计记录。

## 5. 用户流程

### 5.1 兑换

1. 用户在 Dujiao-Next 购买商品并取得 CDK。
2. 用户打开兑换页并输入 CDK。
3. 服务端以 HMAC-SHA-256 计算 CDK 指纹，不把明文写入数据库或日志。
4. CDK 为 `NEW` 时创建兑换会话并转为 `RESERVED`。
5. CDK 已有未结束会话时，重新输入同一 CDK可恢复该会话。
6. 服务端返回一次性会话令牌，浏览器只保存会话令牌，不在 URL 中携带 CDK。

### 5.2 取号与收码

1. 用户点击“获取手机号”。
2. 服务端调用 MaDao：

   ```json
   {
     "provider": "auto",
     "routing_plan_id": "openai-production"
   }
   ```

3. MaDao 按已验证的 HeroSMS、5SIM 路线顺序取号，并返回 `ticket_id`、手机号、供应商和价格。
4. 业务系统保存上游订单后再向用户展示手机号。
5. 后台任务每 3 秒调用一次 MaDao `/api/poll`，最长等待 10 分钟。
6. 收到验证码：
   - 加密保存短信正文和验证码；
   - 调用 `/api/release`，`action=finish`；
   - 将 CDK 由 `RESERVED` 原子更新为 `USED`；
   - 记录供应商、线路、实际美元成本和接收耗时；
   - 用户页面展示验证码。
7. 10 分钟无短信：
   - 调用 `/api/routing/replace`，`release_action=cancel`；
   - MaDao 取消当前号码并切换下一候选线路；
   - 增加一次失败尝试，但不核销 CDK。
8. 所有候选失败或达到 5 次限制：
   - 结束当前兑换；
   - CDK 恢复 `NEW`，并设置 30 分钟冷却；
   - 页面提示稍后重试或联系售后。

### 5.3 用户主动取消

- 取号 2 分钟后允许用户取消。
- 取消请求通过幂等键处理，多次点击只执行一次上游取消。
- 上游确认取消后释放 CDK；上游状态未知时 CDK 保持 `RESERVED`，由对账任务查询后处理，禁止直接再次购买。

## 6. 状态机

### CDK

```text
NEW -> RESERVED -> USED
 |        |
 |        +-> NEW（上游确认取消/无码）
 +-> EXPIRED
 +-> REVOKED
```

### 兑换会话

```text
CREATED -> ACQUIRING -> NUMBER_READY -> WAITING_SMS -> CODE_RECEIVED
              |              |               |
              +-> FAILED     +-> CANCELLING  +-> REPLACING
                                             +-> TIMED_OUT
```

状态更新必须使用数据库事务和版本号乐观锁。外部请求重试必须先查询已有 `provider_order`，不得仅凭 HTTP 超时再次购买。

MaDao 当前没有业务侧幂等键。所有 `/api/acquire` 调用必须经过 PostgreSQL 全局 advisory lock 串行执行；开始调用前记录 MaDao ticket 快照。如果请求结果未知，暂停后续购买，先用快照差集完成对账。服务进程异常退出后，Worker 也必须先清空 `UNKNOWN` 订单，才允许处理新的取号请求。

## 7. 供应商策略和成本控制

首期只启用 HeroSMS、5SIM：

- HeroSMS：主候选，公开页面当前约 `$0.03/次`；无码自动退回余额。
- 5SIM：备用，当前 OpenAI 最低 `$0.038`，美国示例 `$0.1483`；无码取消后退款。
- 生产预算按每次成功接码 ¥0.30–2.50 计算，包含收到短信但目标平台拒绝号码的损耗。
- MaDao 路由条目必须配置 `max_price`，禁止在价格异常时无上限购买。
- 每 5 分钟采集供应商余额；低于设定阈值时通知管理员并暂停新取号。

上线前路线准入门槛：

- 每条候选路线至少完成 20 次真实测试。
- 短信到达率不低于 70%。
- 收到短信后的目标验证通过率不低于 80%。
- 无码取消后余额能够正确退回。
- 单次价格未超过后台配置上限。

## 8. 数据模型

### `cdk_batches`

- `id UUID`
- `name VARCHAR(100)`
- `sku VARCHAR(50)`
- `quantity INTEGER`
- `expires_at TIMESTAMPTZ`
- `created_by UUID`
- `created_at TIMESTAMPTZ`

### `cdk_codes`

- `id UUID`
- `batch_id UUID`
- `code_digest BYTEA UNIQUE`
- `code_hint VARCHAR(8)`，仅保存首尾脱敏片段
- `status VARCHAR(20)`
- `reserved_at TIMESTAMPTZ`
- `used_at TIMESTAMPTZ`
- `cooldown_until TIMESTAMPTZ`
- `version BIGINT`

### `redemptions`

- `id UUID`
- `cdk_id UUID`
- `session_digest BYTEA UNIQUE`
- `status VARCHAR(30)`
- `attempt_count INTEGER`
- `current_provider_order_id UUID`
- `expires_at TIMESTAMPTZ`
- `version BIGINT`
- `created_at/updated_at TIMESTAMPTZ`

### `provider_orders`

- `id UUID`
- `redemption_id UUID`
- `idempotency_key UUID UNIQUE`
- `madao_ticket_id VARCHAR(64) UNIQUE`
- `provider VARCHAR(30)`
- `country VARCHAR(10)`
- `operator VARCHAR(50)`
- `phone_encrypted BYTEA`
- `quoted_cost_usd NUMERIC(12,6)`
- `status VARCHAR(30)`
- `started_at/finished_at TIMESTAMPTZ`

### `sms_messages`

- `id UUID`
- `provider_order_id UUID`
- `body_encrypted BYTEA`
- `code_encrypted BYTEA`
- `received_at TIMESTAMPTZ`
- `purge_at TIMESTAMPTZ`

### `audit_logs`

- `id UUID`
- `actor_type VARCHAR(20)`
- `actor_id VARCHAR(100)`
- `action VARCHAR(100)`
- `target_type VARCHAR(50)`
- `target_id UUID`
- `metadata JSONB`，禁止写入 CDK、完整手机号和验证码
- `created_at TIMESTAMPTZ`

## 9. 接口

### 用户接口

- `POST /api/v1/redemptions`：输入 CDK，创建或恢复会话。
- `GET /api/v1/redemptions/{id}`：查询当前状态。
- `POST /api/v1/redemptions/{id}/acquire`：开始取号。
- `POST /api/v1/redemptions/{id}/cancel`：取消当前号码。
- `GET /api/v1/redemptions/{id}/messages/latest`：读取最新验证码。

除第一个接口外，全部使用兑换会话 Bearer Token；CDK 不作为后续接口凭证。

### 管理接口

- `POST /api/admin/v1/cdk-batches`：生成批次。
- `GET /api/admin/v1/cdk-batches/{id}/export`：一次性下载明文 CSV。
- `POST /api/admin/v1/cdk-codes/{id}/revoke`：作废未使用 CDK。
- `GET /api/admin/v1/redemptions`：查询兑换记录。
- `GET /api/admin/v1/provider-metrics`：查询余额、成功率和成本。

管理端必须使用密码、TOTP 和短时 Session；生产环境不提供默认管理员密码。

## 10. 安全与隐私

- CDK、管理会话和用户兑换会话均使用独立 HMAC 密钥计算指纹。
- 手机号、短信正文、验证码使用 AES-256-GCM 字段级加密。
- 日志自动脱敏 CDK、手机号、验证码和供应商密钥。
- 公网接口启用 IP/CDK 双层限流和人机验证。
- MaDao API 密钥只存在于服务端 Secret，不下发浏览器。
- MaDao 端口不映射公网；业务容器通过私有 Docker 网络访问。
- `codex_sms_cdk` 每日执行独立 `pg_dump -Fc`，备份文件权限 `0600`，保留 14 天；上线前在隔离的 PostgreSQL 15 容器完成一次真实恢复演练。现有商城备份脚本不包含该数据库，不能作为本系统备份。
- Redis 不是灾难恢复数据源；Redis 丢失后必须能仅依靠 PostgreSQL 恢复业务状态。
- 一次性短信正文和验证码在收到后 24 小时自动清除。
- 仅用于合法验证；禁止批量注册、欺诈、规避平台限制和其他违法用途。

## 11. 运行指标

- `sms_acquire_total{provider,result}`
- `sms_code_received_total{provider}`
- `sms_activation_duration_seconds`
- `sms_provider_cost_usd_total{provider}`
- `sms_provider_balance_usd{provider}`
- `cdk_redemption_total{result}`
- `cdk_duplicate_attempt_total`
- `provider_order_reconciliation_pending`

告警：

- 连续 10 次取号失败。
- 15 分钟短信到达率低于 50%。
- 供应商余额低于可支持 100 次成功接码的预计金额。
- 存在超过 5 分钟的状态未知订单。
- CDK 重复核销或同一兑换出现多个活跃上游订单。
- PostgreSQL 总连接数超过 70，或 `codex_sms_cdk` 角色连接数超过 9。
- Redis 使用内存超过 70%、出现 `evicted_keys`、AOF 错误或阻塞客户端。
- 宿主机可用内存低于 1.5 GiB，或磁盘使用率超过 80%。

## 12. 验收标准

- 一枚 CDK 并发提交 20 次，只能产生一个有效兑换会话。
- API 超时重试不会创建第二个上游号码。
- 无码取消后 CDK 可再次使用，收到短信后 CDK 不可再次使用。
- HeroSMS 失败后能按路由切换到 5SIM。
- MaDao 重启后业务系统能根据数据库记录继续查询或对账。
- 任何应用日志中都找不到完整 CDK、手机号或验证码。
- 100 个并发兑换下，业务 API P95 小于 500ms，不含供应商等待时间。
- 数据库备份能够在一台空白环境恢复并完成一次历史兑换查询。
- 生产 Compose 不定义 PostgreSQL、Redis 和 Caddy 服务；发布前后现有三个容器的 ID、启动时间和健康状态保持不变。
- Redis DB 2 中本系统的键全部以 `smscdk:` 开头且均有 TTL，删除操作不能影响其他 DB 或其他前缀。

## 13. 交付周期和费用

按 1 名高级全栈开发、兼职测试/运维估算：

- 周期：5 周，预留 1 周供应商不稳定缓冲。
- 工作量：25–35 人日。
- 开发预算：¥4.5万–9万元。
- 增量基础设施：约 ¥0–200/月，主要用于异地备份、监控和额外流量；复用现有 PostgreSQL、Redis、Caddy 和服务器，不新增常驻数据库/缓存主机。
- 供应商周转金：`日均接码量 × 平均成功成本 × 7 × 1.3`。

里程碑：

- 第 1 周：供应商 PoC、路线准入和项目骨架。
- 第 2 周：CDK、后台批次、兑换会话。
- 第 3 周：MaDao 取号、轮询、取消、换号和对账。
- 第 4 周：用户端、管理端、安全、监控和部署。
- 第 5 周：压力测试、故障演练、灰度和正式上线。
