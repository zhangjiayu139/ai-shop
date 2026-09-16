# One-Time SMS CDK Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建设一个可导出 CDK 给 Dujiao-Next、通过私网 MaDao 调用 HeroSMS/5SIM、仅在收到短信后核销权益的一次性 OpenAI/Codex 接码系统。

**Architecture:** 新建 Go API/Worker 与 Vue 3 前端；生产环境复用现有 PostgreSQL 15、Redis 7 和 Caddy，但使用独立数据库/账号、独立 Redis DB/前缀和受控 Caddy 路由。MaDao 以独立容器运行在不发布端口的 provider 网络中，业务 Worker 主动轮询 MaDao，不使用其无持久化重试的回调。

**Tech Stack:** Go 1.24、Chi、pgx v5、Redis 7、PostgreSQL 15、Vue 3、TypeScript、Vite、Vitest、Playwright、Docker Compose、MaDao Docker image。

## Global Constraints

- 项目根目录固定为 `/Users/zhangjiayu/Desktop/project/study/ai/ai-shop/codex-sms-cdk`。
- V1 只支持 SKU `OPENAI_OTP_SINGLE`，不实现租号、续费、余额和任意服务选择。
- Dujiao-Next 只通过人工导入 CDK CSV 对接，不修改其代码和数据库。
- 生产复用 `taoai-shop-postgres`、`taoai-shop-redis`、`gpt-cdk-caddy`；本项目 Compose 禁止定义或重建 PostgreSQL、Redis、Caddy。
- PostgreSQL 使用独立数据库/角色 `codex_sms_cdk`，角色连接上限 10；API 连接池最大 6、Worker 最大 4。
- Redis 固定使用 DB 2 和 `smscdk:` 前缀；每个键必须有 TTL，禁止 `FLUSHDB`、`FLUSHALL` 和无前缀批量删除。
- Redis DB 只提供逻辑命名空间，不视为权限隔离；MaDao 不加入 `taoai-shop_backend`。Redis 不可用时，取号、兑换和限流相关写接口 fail closed 返回 503，查询接口从 PostgreSQL 降级读取。
- API/Worker 通过现有内部网络 `taoai-shop_backend` 访问 PostgreSQL/Redis；API 通过 `taoai_shop_front` 接入现有 Caddy。
- MaDao 只允许私有 Docker 网络访问，禁止将 `7822` 映射到公网。
- CDK 仅在收到目标短信后由 `RESERVED` 变为 `USED`。
- 每枚 CDK 24 小时最多购买 5 个上游号码；每个兑换同一时间最多一个活跃上游订单。
- 所有外部写操作必须幂等；HTTP 超时后先对账，不得直接重复购买。
- MaDao `/api/acquire` 必须由 PostgreSQL 全局 advisory lock 串行执行；存在 `UNKNOWN` 订单时暂停所有新购买，先完成 ticket 快照差集对账。
- CDK 和会话令牌只存 HMAC 指纹；手机号、短信正文、验证码使用 AES-256-GCM 加密。
- 一次性短信正文和验证码在收到后 24 小时清除。
- 全部功能按 TDD 实现，每个任务形成独立可验证提交。

---

## Schedule and Cost Baseline

- 第 1 周：Task 0–2，完成供应商 PoC、项目骨架、PostgreSQL 15 兼容迁移和加密边界。
- 第 2 周：Task 3，完成 CDK 批次、一次性导出、原子预留和管理认证。
- 第 3 周：Task 4–6，完成 MaDao 契约、幂等取号、轮询、换号、核销和对账。
- 第 4 周：Task 7 和 Task 8 的部署准备，完成手机端、最小管理端、共享基础设施脚本与监控。
- 第 5 周：Task 8 的恢复演练、100 并发压测、真实路线回归、48 小时灰度和发布。
- 供应商波动缓冲：额外预留 1 周，不压缩安全、退款和真实收码验证。
- 开发工作量：25–35 人日，预算 ¥4.5万–9万元。
- 增量基础设施：约 ¥0–200/月；复用现有 PostgreSQL、Redis、Caddy 和服务器，费用仅预留给异地备份、监控和流量。
- 共享基础设施预检不通过是发布阻断项；此时先扩容或拆分服务，不能通过降低验收门槛继续上线。

---

## File Map

```text
codex-sms-cdk/
├── cmd/api/main.go                       # 公网 API 入口
├── cmd/worker/main.go                    # 轮询、换号、对账、清理任务入口
├── internal/app/app.go                   # 依赖装配与生命周期
├── internal/config/config.go             # 环境配置和启动校验
├── internal/crypto/field.go              # AES-GCM 字段加密
├── internal/crypto/digest.go             # CDK/Session HMAC 指纹
├── internal/cdk/model.go                 # CDK 与批次模型
├── internal/cdk/repository.go            # CDK PostgreSQL 持久化
├── internal/cdk/service.go               # 生成、恢复、核销、释放逻辑
├── internal/admin/auth.go                # 管理员密码、TOTP 和 Session
├── internal/redemption/model.go          # 兑换和供应商订单状态
├── internal/redemption/repository.go     # 事务与乐观锁
├── internal/redemption/service.go        # 兑换用例
├── internal/redemption/worker.go         # 轮询、换号、对账和清理
├── internal/madao/client.go              # MaDao HTTP client
├── internal/madao/types.go               # MaDao DTO
├── internal/httpapi/router.go            # 路由、中间件和健康检查
├── internal/httpapi/redemption_handler.go# 用户接口
├── internal/httpapi/admin_handler.go     # 批次与运营接口
├── internal/httpapi/auth.go              # 兑换 Session 与管理员认证
├── internal/metrics/metrics.go           # Prometheus 指标
├── migrations/000001_init.sql            # 业务表、约束和索引
├── deploy/docker-compose.test.yml         # PostgreSQL 迁移测试环境
├── web/src/views/RedeemView.vue          # 手机兑换页
├── web/src/views/AdminBatchesView.vue    # 批次生成与导出页
├── web/src/api/client.ts                 # 前端 API client
├── web/src/stores/redemption.ts          # 兑换状态与轮询
├── deploy/docker-compose.yml             # 仅 api/worker/madao，接入现有网络
├── deploy/caddy-route.caddy               # 合并到现有 Caddyfile 的受控路由片段
├── deploy/bootstrap-shared-services.sh    # 独立数据库/角色和 Redis DB 预检
├── deploy/verify-shared-infra.sh          # 部署前后共享基础设施只读验收
├── deploy/backup-codex-sms.sh             # 独立数据库备份与保留策略
├── scripts/configure-madao.sh            # 创建 openai-production 路由
├── docs/vendor-poc-report.md              # HeroSMS/5SIM 真实路线准入记录
├── docs/vendor-poc-results.csv            # 逐次价格、到达、退款和通过结果
├── tests/e2e/redemption.spec.ts           # 端到端兑换测试
├── tests/e2e/fixtures/mock-madao.ts        # 可控 MaDao 测试替身
├── Makefile                               # 统一验证命令
└── README.md                              # 部署、运营、恢复和回滚
```

### Task 0: 完成 HeroSMS/5SIM 真实线路 PoC

**Files:**
- Create: `codex-sms-cdk/docs/vendor-poc-report.md`
- Create: `codex-sms-cdk/docs/vendor-poc-results.csv`

**Interfaces:**
- Produces: 获准进入 `openai-production` 的 provider/country/operator/price ceiling 清单
- Produces: 开发和运营使用的成本基线、退款时延和失败分类

- [ ] **Step 1: 准备隔离测试账户和小额余额**

分别创建 HeroSMS、5SIM 测试账户，启用 2FA，只充值完成 40–60 次测试所需的小额余额。API key 只写入本机权限为 `0600` 的环境文件，不写入报告、截图、Git 或聊天记录。

- [ ] **Step 2: 建立逐次记录 CSV**

```csv
tested_at,provider,country,operator,quoted_cost_usd,number_type,sms_received,receive_seconds,target_accepted,cancelled,refund_received,refund_seconds,failure_class
2026-09-16T10:00:00+08:00,herosms,US,any,0.030000,mobile,true,42,true,false,false,0,
```

`failure_class` 只允许：`NO_STOCK`、`NO_SMS`、`NUMBER_REJECTED`、`CODE_INVALID`、`UPSTREAM_ERROR`、空值。

- [ ] **Step 3: 每条候选路线执行至少 20 次**

测试只能手工触发合法的本人验证流程，不运行自动注册。每次记录真实报价、号码类型、短信到达、耗时、目标是否接受；无码订单等待或取消后继续记录余额退款时间。

- [ ] **Step 4: 计算准入指标**

```text
短信到达率 = sms_received=true 次数 / 总测试次数
收码后通过率 = target_accepted=true 次数 / sms_received=true 次数
平均成功成本 = quoted_cost_usd 总和 / target_accepted=true 次数
P95到达耗时 = receive_seconds 的第95百分位
退款成功率 = refund_received=true 次数 / cancelled=true 次数
```

只有同时满足“样本数不少于 20、到达率不低于 70%、收码后通过率不低于 80%、无码退款成功率 100%”的路线可以进入生产。失败路线保留记录但禁用。

- [ ] **Step 5: 写 PoC 报告和价格上限**

`vendor-poc-report.md` 必须列出每条路线的五个指标、是否准入和拒绝原因。生产 `max_price` 设置为该路线实测成功订单价格 P95 的 1.2 倍，且每次变更必须重新执行 10 次回归验证。

- [ ] **Step 6: 提交不含秘密和完整号码的证据**

```bash
git add docs/vendor-poc-report.md docs/vendor-poc-results.csv
git commit -m "docs: record sms provider route qualification"
```

### Task 1: 初始化仓库、配置和健康检查

**Files:**
- Create: `codex-sms-cdk/go.mod`
- Create: `codex-sms-cdk/cmd/api/main.go`
- Create: `codex-sms-cdk/internal/config/config.go`
- Create: `codex-sms-cdk/internal/config/config_test.go`
- Create: `codex-sms-cdk/internal/httpapi/router.go`
- Create: `codex-sms-cdk/internal/httpapi/router_test.go`
- Create: `codex-sms-cdk/Makefile`

**Interfaces:**
- Produces: `config.Load() (config.Config, error)`
- Produces: `httpapi.NewRouter(Dependencies) http.Handler`
- Produces: `GET /health/live` and `GET /health/ready`

- [ ] **Step 1: 创建仓库和 Go module**

Run:

```bash
mkdir -p /Users/zhangjiayu/Desktop/project/study/ai/ai-shop/codex-sms-cdk
cd /Users/zhangjiayu/Desktop/project/study/ai/ai-shop/codex-sms-cdk
git init
go mod init github.com/taoai/codex-sms-cdk
go get github.com/go-chi/chi/v5 github.com/google/uuid github.com/jackc/pgx/v5 github.com/redis/go-redis/v9 github.com/prometheus/client_golang/prometheus/promhttp github.com/pquerna/otp/totp golang.org/x/crypto/argon2
go get -t github.com/stretchr/testify
```

Expected: `go.mod` 存在，`go list ./...` 返回成功。

- [ ] **Step 2: 写配置失败测试**

```go
func TestLoadRejectsMissingSecrets(t *testing.T) {
    t.Setenv("DATABASE_URL", "postgres://app:app@db/app")
    t.Setenv("REDIS_ADDR", "redis:6379")
    t.Setenv("REDIS_DB", "2")
    t.Setenv("REDIS_PREFIX", "smscdk:")
    t.Setenv("CDK_HMAC_KEY", "")
    t.Setenv("SESSION_HMAC_KEY", strings.Repeat("b", 64))
    t.Setenv("FIELD_ENCRYPTION_KEY", base64.StdEncoding.EncodeToString(make([]byte, 32)))
    t.Setenv("MADAO_BASE_URL", "http://madao:7822")
    t.Setenv("MADAO_HTTP_SECRET", "secret")
    _, err := Load()
    require.ErrorContains(t, err, "CDK_HMAC_KEY")
}

func TestLoadAcceptsProductionConfig(t *testing.T) {
    t.Setenv("DATABASE_URL", "postgres://codex_sms_cdk:secret@taoai-shop-postgres/codex_sms_cdk")
    t.Setenv("REDIS_ADDR", "taoai-shop-redis:6379")
    t.Setenv("REDIS_DB", "2")
    t.Setenv("REDIS_PREFIX", "smscdk:")
    t.Setenv("CDK_HMAC_KEY", strings.Repeat("a", 64))
    t.Setenv("SESSION_HMAC_KEY", strings.Repeat("b", 64))
    t.Setenv("FIELD_ENCRYPTION_KEY", base64.StdEncoding.EncodeToString(make([]byte, 32)))
    t.Setenv("MADAO_BASE_URL", "http://madao:7822")
    t.Setenv("MADAO_HTTP_SECRET", "secret")
    cfg, err := Load()
    require.NoError(t, err)
    assert.Equal(t, "openai-production", cfg.MaDao.RoutingPlanID)
    assert.Equal(t, 2, cfg.RedisDB)
    assert.Equal(t, "smscdk:", cfg.RedisPrefix)
}
```

- [ ] **Step 3: 运行测试确认 RED**

Run: `go test ./internal/config -run TestLoad -v`
Expected: FAIL，提示 `Load` 未定义。

- [ ] **Step 4: 实现启动配置校验**

```go
type Config struct {
    DatabaseURL string
    RedisAddr string
    RedisDB int
    RedisPrefix string
    CDKHMACKey []byte
    SessionHMACKey []byte
    FieldEncryptionKey []byte
    MaDao struct {
        BaseURL string
        HTTPSecret string
        RoutingPlanID string
    }
}

func Load() (Config, error) {
    var c Config
    c.DatabaseURL = os.Getenv("DATABASE_URL")
    c.RedisAddr = os.Getenv("REDIS_ADDR")
    redisDB, err := strconv.Atoi(os.Getenv("REDIS_DB"))
    c.RedisDB = redisDB
    if err != nil || c.RedisDB != 2 { return Config{}, errors.New("REDIS_DB must be 2") }
    c.RedisPrefix = os.Getenv("REDIS_PREFIX")
    if c.RedisPrefix != "smscdk:" { return Config{}, errors.New("REDIS_PREFIX must be smscdk:") }
    c.CDKHMACKey = []byte(os.Getenv("CDK_HMAC_KEY"))
    c.SessionHMACKey = []byte(os.Getenv("SESSION_HMAC_KEY"))
    c.MaDao.BaseURL = os.Getenv("MADAO_BASE_URL")
    c.MaDao.HTTPSecret = os.Getenv("MADAO_HTTP_SECRET")
    c.MaDao.RoutingPlanID = envOr("MADAO_ROUTING_PLAN_ID", "openai-production")
    key, err := base64.StdEncoding.DecodeString(os.Getenv("FIELD_ENCRYPTION_KEY"))
    if err != nil || len(key) != 32 { return Config{}, errors.New("FIELD_ENCRYPTION_KEY must be base64 encoded 32 bytes") }
    c.FieldEncryptionKey = key
    required := map[string]string{
        "DATABASE_URL": c.DatabaseURL, "REDIS_ADDR": c.RedisAddr, "REDIS_PREFIX": c.RedisPrefix,
        "CDK_HMAC_KEY": string(c.CDKHMACKey), "SESSION_HMAC_KEY": string(c.SessionHMACKey),
        "MADAO_BASE_URL": c.MaDao.BaseURL, "MADAO_HTTP_SECRET": c.MaDao.HTTPSecret,
    }
    for name, value := range required { if value == "" { return Config{}, fmt.Errorf("%s is required", name) } }
    return c, nil
}
```

- [ ] **Step 5: 增加健康检查并验证 GREEN**

```go
func NewRouter(d Dependencies) http.Handler {
    r := chi.NewRouter()
    r.Get("/health/live", func(w http.ResponseWriter, _ *http.Request) { w.WriteHeader(http.StatusNoContent) })
    r.Get("/health/ready", func(w http.ResponseWriter, r *http.Request) {
        if err := d.Readiness.Check(r.Context()); err != nil { http.Error(w, "not ready", 503); return }
        w.WriteHeader(http.StatusNoContent)
    })
    return r
}
```

Run: `go test ./internal/config ./internal/httpapi -v`
Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add go.mod go.sum cmd internal Makefile
git commit -m "chore: scaffold one-time sms service"
```

### Task 2: 建立数据库状态和加密边界

**Files:**
- Create: `codex-sms-cdk/migrations/000001_init.sql`
- Create: `codex-sms-cdk/internal/crypto/digest.go`
- Create: `codex-sms-cdk/internal/crypto/digest_test.go`
- Create: `codex-sms-cdk/internal/crypto/field.go`
- Create: `codex-sms-cdk/internal/crypto/field_test.go`
- Create: `codex-sms-cdk/internal/cdk/model.go`
- Create: `codex-sms-cdk/internal/redemption/model.go`
- Create: `codex-sms-cdk/deploy/docker-compose.test.yml`

**Interfaces:**
- Produces: `crypto.Digest(key, value []byte) []byte`
- Produces: `crypto.Encrypt(key, plaintext []byte) ([]byte, error)`
- Produces: `crypto.Decrypt(key, ciphertext []byte) ([]byte, error)`
- Produces: SQL states `NEW|RESERVED|USED|EXPIRED|REVOKED`

- [ ] **Step 1: 写 HMAC 和 AES-GCM 测试**

```go
func TestDigestIsDeterministicAndKeyed(t *testing.T) {
    a := Digest([]byte("key-a"), []byte("CDK-123"))
    b := Digest([]byte("key-a"), []byte("CDK-123"))
    c := Digest([]byte("key-b"), []byte("CDK-123"))
    assert.Equal(t, a, b)
    assert.NotEqual(t, a, c)
}

func TestFieldCipherRoundTrip(t *testing.T) {
    key := bytes.Repeat([]byte{7}, 32)
    encrypted, err := Encrypt(key, []byte("+15551234567|123456"))
    require.NoError(t, err)
    assert.NotContains(t, string(encrypted), "123456")
    plain, err := Decrypt(key, encrypted)
    require.NoError(t, err)
    assert.Equal(t, "+15551234567|123456", string(plain))
}
```

- [ ] **Step 2: 运行测试确认 RED**

Run: `go test ./internal/crypto -v`
Expected: FAIL，提示 `Digest`、`Encrypt`、`Decrypt` 未定义。

- [ ] **Step 3: 实现 HMAC 和 AES-GCM**

```go
func Digest(key, value []byte) []byte {
    mac := hmac.New(sha256.New, key)
    _, _ = mac.Write(value)
    return mac.Sum(nil)
}

func Encrypt(key, plaintext []byte) ([]byte, error) {
    block, err := aes.NewCipher(key); if err != nil { return nil, err }
    gcm, err := cipher.NewGCM(block); if err != nil { return nil, err }
    nonce := make([]byte, gcm.NonceSize())
    if _, err = io.ReadFull(rand.Reader, nonce); err != nil { return nil, err }
    return gcm.Seal(nonce, nonce, plaintext, nil), nil
}

func Decrypt(key, ciphertext []byte) ([]byte, error) {
    block, err := aes.NewCipher(key); if err != nil { return nil, err }
    gcm, err := cipher.NewGCM(block); if err != nil { return nil, err }
    if len(ciphertext) < gcm.NonceSize() { return nil, errors.New("ciphertext too short") }
    nonce, payload := ciphertext[:gcm.NonceSize()], ciphertext[gcm.NonceSize():]
    return gcm.Open(nil, nonce, payload, nil)
}
```

- [ ] **Step 4: 创建数据库迁移**

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE TYPE cdk_status AS ENUM ('NEW','RESERVED','USED','EXPIRED','REVOKED');
CREATE TYPE redemption_status AS ENUM ('CREATED','ACQUIRING','NUMBER_READY','WAITING_SMS','REPLACING','CANCELLING','CODE_RECEIVED','TIMED_OUT','FAILED','CANCELLED');
CREATE TYPE provider_order_status AS ENUM ('CREATING','WAITING_SMS','FINISHED','CANCEL_PENDING','CANCELLED','UNKNOWN','FAILED');

CREATE TABLE cdk_batches (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), name varchar(100) NOT NULL,
  sku varchar(50) NOT NULL CHECK (sku = 'OPENAI_OTP_SINGLE'), quantity integer NOT NULL CHECK (quantity > 0),
  expires_at timestamptz NOT NULL, created_by uuid NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE cdk_codes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), batch_id uuid NOT NULL REFERENCES cdk_batches(id),
  code_digest bytea NOT NULL UNIQUE, code_hint varchar(12) NOT NULL, status cdk_status NOT NULL DEFAULT 'NEW',
  reserved_at timestamptz, used_at timestamptz, cooldown_until timestamptz, version bigint NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE redemptions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), cdk_id uuid NOT NULL REFERENCES cdk_codes(id),
  session_digest bytea NOT NULL UNIQUE, status redemption_status NOT NULL DEFAULT 'CREATED',
  attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count BETWEEN 0 AND 5), current_provider_order_id uuid,
  expires_at timestamptz NOT NULL, version bigint NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX one_active_redemption_per_cdk ON redemptions(cdk_id)
WHERE status IN ('CREATED','ACQUIRING','NUMBER_READY','WAITING_SMS','REPLACING','CANCELLING');
CREATE TABLE provider_orders (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), redemption_id uuid NOT NULL REFERENCES redemptions(id),
  idempotency_key uuid NOT NULL UNIQUE, madao_ticket_id varchar(64) UNIQUE, provider varchar(30), country varchar(10), operator varchar(50),
  phone_encrypted bytea, quoted_cost_usd numeric(12,6), status provider_order_status NOT NULL DEFAULT 'CREATING',
  started_at timestamptz NOT NULL DEFAULT now(), finished_at timestamptz
);
ALTER TABLE redemptions ADD CONSTRAINT fk_current_provider_order FOREIGN KEY (current_provider_order_id) REFERENCES provider_orders(id);
CREATE UNIQUE INDEX one_live_provider_order_per_redemption ON provider_orders(redemption_id)
WHERE status IN ('CREATING','WAITING_SMS','CANCEL_PENDING','UNKNOWN');
CREATE TABLE sms_messages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), provider_order_id uuid NOT NULL UNIQUE REFERENCES provider_orders(id),
  body_encrypted bytea NOT NULL, code_encrypted bytea NOT NULL, received_at timestamptz NOT NULL, purge_at timestamptz NOT NULL
);
CREATE TABLE audit_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), actor_type varchar(20) NOT NULL, actor_id varchar(100) NOT NULL,
  action varchar(100) NOT NULL, target_type varchar(50) NOT NULL, target_id uuid NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now()
);
```

- [ ] **Step 5: 验证迁移和加密测试**

`deploy/docker-compose.test.yml` 内容：

```yaml
services:
  postgres-test:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: app
      POSTGRES_USER: app
      POSTGRES_PASSWORD: test
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app -d app"]
      interval: 1s
      timeout: 3s
      retries: 30
  migrate:
    image: postgres:15-alpine
    depends_on:
      postgres-test:
        condition: service_healthy
    environment:
      PGPASSWORD: test
    volumes:
      - ../migrations:/migrations:ro
    command: ["psql", "-h", "postgres-test", "-U", "app", "-d", "app", "-v", "ON_ERROR_STOP=1", "-f", "/migrations/000001_init.sql"]
```

Run: `go test ./internal/crypto -v && docker compose -f deploy/docker-compose.test.yml run --rm migrate`
Expected: Go 测试 PASS，迁移退出码为 0。

- [ ] **Step 6: 提交**

```bash
git add migrations internal/crypto internal/cdk/model.go internal/redemption/model.go
git commit -m "feat: add secure cdk persistence model"
```

### Task 3: 实现 CDK 批次生成、导出和原子预留

**Files:**
- Create: `codex-sms-cdk/internal/cdk/repository.go`
- Create: `codex-sms-cdk/internal/cdk/service.go`
- Create: `codex-sms-cdk/internal/cdk/service_test.go`
- Create: `codex-sms-cdk/internal/httpapi/admin_handler.go`
- Create: `codex-sms-cdk/internal/httpapi/admin_handler_test.go`
- Create: `codex-sms-cdk/internal/admin/auth.go`
- Create: `codex-sms-cdk/internal/admin/auth_test.go`

**Interfaces:**
- Produces: `cdk.Service.GenerateBatch(ctx, GenerateBatchCommand) (BatchExport, error)`
- Produces: `cdk.Service.Reserve(ctx, plainCode, sessionDigest) (Reservation, error)`
- Produces: `cdk.Service.MarkUsed(ctx, cdkID, redemptionID) error`
- Produces: `cdk.Service.Release(ctx, cdkID, redemptionID, cooldownUntil) error`

- [ ] **Step 1: 写并发预留失败测试**

```go
func TestReserveSameCDKReturnsSingleRedemption(t *testing.T) {
    svc, code := newTestService(t)
    const workers = 20
    ids := make(chan uuid.UUID, workers)
    var wg sync.WaitGroup
    for i := 0; i < workers; i++ {
        wg.Add(1)
        go func() {
            defer wg.Done()
            reservation, err := svc.Reserve(context.Background(), code, randomDigest())
            require.NoError(t, err)
            ids <- reservation.RedemptionID
        }()
    }
    wg.Wait(); close(ids)
    unique := map[uuid.UUID]struct{}{}
    for id := range ids { unique[id] = struct{}{} }
    assert.Len(t, unique, 1)
    assert.Equal(t, 1, countActiveRedemptions(t))
}
```

- [ ] **Step 2: 运行测试确认 RED**

Run: `go test ./internal/cdk -run TestReserveSameCDKReturnsSingleRedemption -v`
Expected: FAIL，提示 `Reserve` 未实现。

- [ ] **Step 3: 实现 CDK 生成格式和只存指纹**

```go
func generateCode() (string, error) {
    raw := make([]byte, 16)
    if _, err := rand.Read(raw); err != nil { return "", err }
    encoded := strings.ToUpper(base32.StdEncoding.WithPadding(base32.NoPadding).EncodeToString(raw))
    return "OTP-" + encoded[0:5] + "-" + encoded[5:10] + "-" + encoded[10:15] + "-" + encoded[15:20], nil
}

func hint(code string) string {
    return code[:8] + "…" + code[len(code)-4:]
}
```

`GenerateBatch` 必须在同一事务中插入批次和全部指纹，返回的 `BatchExport.CSV` 为本次唯一明文输出；数据库查询接口不提供明文恢复能力。

- [ ] **Step 4: 实现 `SELECT FOR UPDATE` 原子预留**

```sql
SELECT id, status, cooldown_until FROM cdk_codes
WHERE code_digest = $1 AND status IN ('NEW','RESERVED')
FOR UPDATE;
```

同一事务内：复用已有活跃兑换；否则检查过期和冷却时间，插入 `redemptions` 并将 CDK 更新为 `RESERVED`。唯一索引冲突后查询并返回已有兑换，不向客户端暴露 500。

- [ ] **Step 5: 增加管理端批次 API 测试**

管理接口先通过管理员密码、TOTP 和 HttpOnly Session 验证。密码使用 Argon2id：内存 64 MiB、迭代 3 次、并行度 2、盐 16 字节、输出 32 字节；TOTP 使用 30 秒周期、允许前后各一个时间窗。Session Cookie 固定使用 `Secure`、`HttpOnly`、`SameSite=Strict`，有效期 30 分钟。

```go
func TestAdminLoginRequiresValidPasswordAndTOTP(t *testing.T) {
    auth := newAdminAuthFixture(t, "correct-password", "JBSWY3DPEHPK3PXP")
    _, err := auth.Login(context.Background(), "correct-password", "000000", time.Now())
    assert.ErrorIs(t, err, ErrInvalidCredentials)
    code, _ := totp.GenerateCode("JBSWY3DPEHPK3PXP", time.Now())
    session, err := auth.Login(context.Background(), "correct-password", code, time.Now())
    require.NoError(t, err)
    assert.WithinDuration(t, time.Now().Add(30*time.Minute), session.ExpiresAt, time.Second)
}
```

Run: `go test ./internal/admin -v`
Expected: PASS，错误密码或错误 TOTP 均返回统一的 `ErrInvalidCredentials`。

- [ ] **Step 6: 增加管理端批次 API 测试**

```go
func TestCreateBatchReturnsDownloadOnce(t *testing.T) {
    req := `{"name":"dujiao-202609","quantity":2,"expires_at":"2027-03-15T00:00:00Z"}`
    res := adminRequest(t, http.MethodPost, "/api/admin/v1/cdk-batches", req)
    assert.Equal(t, http.StatusCreated, res.Code)
    assert.Contains(t, res.Body.String(), "OTP-")
    assert.Equal(t, 2, countCodes(t))
    assert.Equal(t, 0, countPlaintextCDKs(t))
}
```

- [ ] **Step 7: 运行聚焦和并发测试**

Run: `go test -race ./internal/cdk ./internal/httpapi -run 'TestReserve|TestCreateBatch' -v`
Expected: PASS，race detector 无报告。

- [ ] **Step 8: 提交**

```bash
git add internal/cdk internal/admin internal/httpapi/admin_handler.go internal/httpapi/admin_handler_test.go
git commit -m "feat: generate and atomically reserve cdk codes"
```

### Task 4: 实现 MaDao 客户端契约

**Files:**
- Create: `codex-sms-cdk/internal/madao/types.go`
- Create: `codex-sms-cdk/internal/madao/client.go`
- Create: `codex-sms-cdk/internal/madao/client_test.go`

**Interfaces:**
- Produces: `madao.Client.Acquire(ctx, planID) (Ticket, error)`
- Produces: `madao.Client.Poll(ctx, ticketID) (PollResult, error)`
- Produces: `madao.Client.Replace(ctx, ReplaceRequest) (ReplaceResult, error)`
- Produces: `madao.Client.Release(ctx, ticketID, action) error`
- Produces: `madao.Client.GetTicket(ctx, ticketID) (Ticket, error)`

- [ ] **Step 1: 写 Acquire 契约测试**

```go
func TestAcquireUsesBearerAndRoutingPlan(t *testing.T) {
    server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        assert.Equal(t, "Bearer test-secret", r.Header.Get("Authorization"))
        assert.Equal(t, "/api/acquire", r.URL.Path)
        body, _ := io.ReadAll(r.Body)
        assert.JSONEq(t, `{"provider":"auto","routing_plan_id":"openai-production"}`, string(body))
        w.Header().Set("Content-Type", "application/json")
        _, _ = w.Write([]byte(`{"ticket_id":"ticket-1","provider":"herosms","service":"openai","country":"US","phone_number":"+15551234567","price":0.03}`))
    }))
    defer server.Close()
    client := NewClient(server.URL, "test-secret", server.Client())
    ticket, err := client.Acquire(context.Background(), "openai-production")
    require.NoError(t, err)
    assert.Equal(t, "ticket-1", ticket.ID)
    assert.Equal(t, 0.03, ticket.Price)
}
```

- [ ] **Step 2: 写超时结果不确定测试**

```go
func TestAcquireTimeoutIsMarkedUnknown(t *testing.T) {
    client := NewClient("http://127.0.0.1:1", "secret", &http.Client{Timeout: time.Millisecond})
    _, err := client.Acquire(context.Background(), "openai-production")
    assert.ErrorIs(t, err, ErrOutcomeUnknown)
}
```

- [ ] **Step 3: 运行测试确认 RED**

Run: `go test ./internal/madao -v`
Expected: FAIL，提示 `NewClient` 未定义。

- [ ] **Step 4: 实现 DTO 和 HTTP client**

```go
type Ticket struct {
    ID string `json:"ticket_id"`
    Provider string `json:"provider"`
    Service string `json:"service"`
    Country string `json:"country"`
    Operator string `json:"operator"`
    PhoneNumber string `json:"phone_number"`
    Price float64 `json:"price"`
}

func (c *Client) Acquire(ctx context.Context, planID string) (Ticket, error) {
    payload := map[string]string{"provider":"auto", "routing_plan_id":planID}
    var result Ticket
    if err := c.doJSON(ctx, http.MethodPost, "/api/acquire", payload, &result); err != nil {
        if errors.Is(err, context.DeadlineExceeded) || isTransportError(err) { return Ticket{}, ErrOutcomeUnknown }
        return Ticket{}, err
    }
    if result.ID == "" || result.PhoneNumber == "" { return Ticket{}, ErrInvalidResponse }
    return result, nil
}
```

`doJSON` 必须设置 `Authorization: Bearer <secret>`、`Content-Type: application/json`、5 秒连接超时和 15 秒总超时；日志只记录 path、status、duration，不记录 Bearer、手机号和响应正文。

- [ ] **Step 5: 完成 Poll/Replace/Release/GetTicket 契约测试**

分别断言以下请求：

```text
POST /api/poll                            {"ticket_id":"ticket-1"}
POST /api/routing/replace                 {"ticket_id":"ticket-1","failed_item_id":"","reason":"sms timeout","release_action":"cancel"}
POST /api/release                         {"ticket_id":"ticket-1","action":"finish"}
GET  /api/tickets/ticket-1
```

Run: `go test ./internal/madao -v`
Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add internal/madao
git commit -m "feat: add madao activation client"
```

### Task 5: 实现兑换用例和幂等取号

**Files:**
- Create: `codex-sms-cdk/internal/redemption/repository.go`
- Create: `codex-sms-cdk/internal/redemption/service.go`
- Create: `codex-sms-cdk/internal/redemption/service_test.go`
- Create: `codex-sms-cdk/internal/httpapi/redemption_handler.go`
- Create: `codex-sms-cdk/internal/httpapi/redemption_handler_test.go`
- Create: `codex-sms-cdk/internal/httpapi/auth.go`

**Interfaces:**
- Produces: `redemption.Service.Open(ctx, cdkPlaintext) (Session, error)`
- Produces: `redemption.Service.Acquire(ctx, redemptionID, idempotencyKey) (View, error)`
- Produces: `redemption.Service.Cancel(ctx, redemptionID, idempotencyKey) error`
- Produces: the five public `/api/v1/redemptions` endpoints from the spec

- [ ] **Step 1: 写幂等取号测试**

```go
func TestAcquireRetryDoesNotBuySecondNumber(t *testing.T) {
    svc, fakeMaDao, redemptionID := newRedemptionFixture(t)
    key := uuid.New()
    first, err := svc.Acquire(context.Background(), redemptionID, key)
    require.NoError(t, err)
    second, err := svc.Acquire(context.Background(), redemptionID, key)
    require.NoError(t, err)
    assert.Equal(t, first.ProviderOrderID, second.ProviderOrderID)
    assert.Equal(t, 1, fakeMaDao.AcquireCalls())
}
```

- [ ] **Step 2: 写未知结果禁止重买测试**

```go
func TestAcquireUnknownOutcomeRequiresReconciliation(t *testing.T) {
    svc, fakeMaDao, redemptionID := newRedemptionFixture(t)
    fakeMaDao.AcquireError = madao.ErrOutcomeUnknown
    _, err := svc.Acquire(context.Background(), redemptionID, uuid.New())
    assert.ErrorIs(t, err, ErrReconciliationPending)
    order := loadOnlyProviderOrder(t)
    assert.Equal(t, OrderUnknown, order.Status)
    assert.Equal(t, 1, fakeMaDao.AcquireCalls())
}
```

- [ ] **Step 3: 运行测试确认 RED**

Run: `go test ./internal/redemption -run 'TestAcquire' -v`
Expected: FAIL，提示 Service 未实现。

- [ ] **Step 4: 实现购买顺序**

`Acquire` 必须执行：

1. 数据库事务锁定兑换。
2. 检查 `attempt_count < 5` 和不存在活跃订单。
3. 以客户端幂等键插入 `provider_orders(status=CREATING)`；冲突时返回旧订单。
4. 获取 PostgreSQL advisory lock；如果存在任意 `UNKNOWN` 订单，返回 202 并由 Worker 先对账。
5. 调用前读取 `/api/tickets` 并保存 ticket ID 快照，再调用 MaDao。
6. 成功后加密手机号并更新 `madao_ticket_id/status=WAITING_SMS`。
7. 结果未知时更新 `status=UNKNOWN`，保留调用前快照并返回 202，而不是重新调用。

核心返回模型：

```go
type View struct {
    ID uuid.UUID `json:"id"`
    Status Status `json:"status"`
    PhoneNumber string `json:"phone_number,omitempty"`
    AttemptCount int `json:"attempt_count"`
    ExpiresAt time.Time `json:"expires_at"`
    RetryAfterSeconds int `json:"retry_after_seconds,omitempty"`
}
```

- [ ] **Step 5: 实现会话 Bearer 认证**

`POST /api/v1/redemptions` 返回：

```json
{
  "redemption_id": "018f...",
  "session_token": "base64url-32-random-bytes",
  "status": "CREATED"
}
```

后续请求计算 `HMAC(SESSION_HMAC_KEY, token)` 并与 `session_digest` 使用 `subtle.ConstantTimeCompare` 比较。响应和日志均不得回显 CDK。

- [ ] **Step 6: 验证接口和并发测试**

Run: `go test -race ./internal/redemption ./internal/httpapi -run 'TestAcquire|TestOpen|TestSession' -v`
Expected: PASS；同一幂等键只出现一次 MaDao 调用。

- [ ] **Step 7: 提交**

```bash
git add internal/redemption internal/httpapi/redemption_handler.go internal/httpapi/redemption_handler_test.go internal/httpapi/auth.go
git commit -m "feat: add idempotent cdk redemption flow"
```

### Task 6: 实现轮询、换号、核销、对账和数据清理

**Files:**
- Create: `codex-sms-cdk/cmd/worker/main.go`
- Create: `codex-sms-cdk/internal/redemption/worker.go`
- Create: `codex-sms-cdk/internal/redemption/worker_test.go`
- Create: `codex-sms-cdk/internal/metrics/metrics.go`

**Interfaces:**
- Produces: `redemption.Worker.RunOnce(ctx) error`
- Produces: `redemption.Worker.ReconcileUnknown(ctx) error`
- Produces: `redemption.Worker.PurgeExpiredMessages(ctx) error`

- [ ] **Step 1: 写成功收码原子核销测试**

```go
func TestWorkerMarksCodeAndCDKUsedAtomically(t *testing.T) {
    worker, fake, fixture := waitingFixture(t)
    fake.PollResult = madao.PollResult{Ready:true, Code:"123456", Message:"OpenAI code 123456", ReceivedAt:time.Now()}
    require.NoError(t, worker.RunOnce(context.Background()))
    assert.Equal(t, RedemptionCodeReceived, loadRedemption(t, fixture.RedemptionID).Status)
    assert.Equal(t, CDKUsed, loadCDK(t, fixture.CDKID).Status)
    assert.Equal(t, OrderFinished, loadOrder(t, fixture.OrderID).Status)
    assert.Equal(t, 1, countMessages(t, fixture.OrderID))
    assert.Equal(t, 1, fake.ReleaseFinishCalls())
}
```

- [ ] **Step 2: 写无码换号不核销测试**

```go
func TestWorkerReplacesAfterTenMinutesWithoutConsumingCDK(t *testing.T) {
    worker, fake, fixture := waitingFixtureOlderThan(t, 10*time.Minute)
    fake.ReplaceResult = madao.ReplaceResult{NextTicket: madao.Ticket{ID:"ticket-2", Provider:"fivesim", PhoneNumber:"+15557654321", Price:0.1483}}
    require.NoError(t, worker.RunOnce(context.Background()))
    assert.Equal(t, CDKReserved, loadCDK(t, fixture.CDKID).Status)
    assert.Equal(t, 2, loadRedemption(t, fixture.RedemptionID).AttemptCount)
    assert.Equal(t, "ticket-2", loadCurrentOrder(t, fixture.RedemptionID).MaDaoTicketID)
}
```

- [ ] **Step 3: 运行测试确认 RED**

Run: `go test ./internal/redemption -run TestWorker -v`
Expected: FAIL，提示 Worker 未实现。

- [ ] **Step 4: 实现 `FOR UPDATE SKIP LOCKED` Worker**

```sql
SELECT po.id
FROM provider_orders po
JOIN redemptions r ON r.id = po.redemption_id
WHERE po.status IN ('WAITING_SMS','UNKNOWN','CANCEL_PENDING')
  AND r.status IN ('NUMBER_READY','WAITING_SMS','REPLACING','CANCELLING')
ORDER BY po.started_at
FOR UPDATE SKIP LOCKED
LIMIT 50;
```

每轮最多处理 50 条；同一订单轮询间隔 3 秒；10 分钟无码执行 `replace`；达到 5 次后取消当前订单、释放 CDK并设置 30 分钟冷却。

- [ ] **Step 5: 实现成功事务和清理**

成功事务必须同时：插入唯一 `sms_messages`、更新 `provider_orders=FINISHED`、更新 `redemptions=CODE_RECEIVED`、更新 `cdk_codes=USED`、写入不含敏感数据的 `audit_logs`。事务提交后调用 MaDao `release(finish)`；调用失败加入对账，不回滚已经接收的验证码。

清理 SQL：

```sql
UPDATE sms_messages
SET body_encrypted = '\x'::bytea, code_encrypted = '\x'::bytea
WHERE purge_at <= now() AND octet_length(code_encrypted) > 0;
```

- [ ] **Step 6: 实现 UNKNOWN 对账**

对有 `ticket_id` 的 `UNKNOWN` 订单调用 `GET /api/tickets/{ticket_id}`。如果没有 `ticket_id`，在全局 acquire advisory lock 内读取 `/api/tickets`，计算“当前 ticket 集合 - 调用前快照”；差集唯一时绑定，差集为空时确认未购买并标记 `FAILED`，差集多于一个时保持 `UNKNOWN` 并告警。只要还有 `UNKNOWN`，禁止创建新订单。

- [ ] **Step 7: 运行 Worker 和竞态测试**

Run: `go test -race ./internal/redemption -run 'TestWorker|TestReconcile|TestPurge' -v`
Expected: PASS；两个 Worker 同时运行也只核销一次。

- [ ] **Step 8: 提交**

```bash
git add cmd/worker internal/redemption/worker.go internal/redemption/worker_test.go internal/metrics
git commit -m "feat: poll sms and reconcile provider orders"
```

### Task 7: 建设手机兑换页和最小管理后台

**Files:**
- Create: `codex-sms-cdk/web/package.json`
- Create: `codex-sms-cdk/web/src/main.ts`
- Create: `codex-sms-cdk/web/src/api/client.ts`
- Create: `codex-sms-cdk/web/src/stores/redemption.ts`
- Create: `codex-sms-cdk/web/src/views/RedeemView.vue`
- Create: `codex-sms-cdk/web/src/views/AdminBatchesView.vue`
- Create: `codex-sms-cdk/web/src/views/RedeemView.test.ts`
- Create: `codex-sms-cdk/web/src/views/AdminBatchesView.test.ts`

**Interfaces:**
- Consumes: `/api/v1/redemptions*` and `/api/admin/v1/cdk-batches*`
- Produces: mobile-first `/redeem` and protected `/admin/cdk-batches`

- [ ] **Step 1: 初始化前端依赖**

Run:

```bash
cd /Users/zhangjiayu/Desktop/project/study/ai/ai-shop/codex-sms-cdk
npm create vite@latest web -- --template vue-ts
cd web
npm install
npm install pinia vue-router
npm install -D vitest @vue/test-utils jsdom playwright
```

Expected: `npm run build` 成功生成 `web/dist`。

- [ ] **Step 2: 写兑换状态测试**

```ts
it('收到验证码后停止轮询并展示复制按钮', async () => {
  vi.useFakeTimers()
  mockApi.sequence([
    { status: 'WAITING_SMS', phone_number: '+1•••4567' },
    { status: 'CODE_RECEIVED', code: '123456' },
  ])
  const wrapper = mount(RedeemView, { global: { plugins: [testPinia()] } })
  await wrapper.get('[data-test=cdk]').setValue('OTP-AAAAA-BBBBB-CCCCC-DDDDD')
  await wrapper.get('[data-test=redeem]').trigger('click')
  await vi.advanceTimersByTimeAsync(3000)
  expect(wrapper.get('[data-test=code]').text()).toBe('123456')
  expect(wrapper.get('[data-test=copy-code]').exists()).toBe(true)
  expect(mockApi.pendingTimers()).toBe(0)
})
```

- [ ] **Step 3: 运行测试确认 RED**

Run: `cd web && npm run test -- --run src/views/RedeemView.test.ts`
Expected: FAIL，页面组件或状态机不存在。

- [ ] **Step 4: 实现用户页面状态**

页面固定显示以下状态，不暴露供应商内部错误：

```ts
export const statusCopy: Record<RedemptionStatus, string> = {
  CREATED: '兑换码有效，可以获取手机号',
  ACQUIRING: '正在分配手机号',
  NUMBER_READY: '手机号已分配，请在目标页面请求短信',
  WAITING_SMS: '正在等待验证码',
  REPLACING: '当前线路未收到短信，正在更换号码',
  CANCELLING: '正在取消当前号码',
  CODE_RECEIVED: '验证码已收到',
  TIMED_OUT: '本次等待超时，兑换码未被消耗',
  FAILED: '暂时无法取号，兑换码未被消耗',
  CANCELLED: '已取消，兑换码可以重新使用',
}
```

手机端必须提供：CDK输入、手机号复制、10 分钟倒计时、验证码复制、取消按钮、尝试次数和明确的“无码不核销”说明。

- [ ] **Step 5: 实现管理批次页面测试和页面**

测试必须断言：数量必须为 `1..10000`，过期时间必须晚于当前时间，生成后自动下载 CSV，离开结果页后不能再次从 API 获取明文 CDK。

CSV 固定格式：

```csv
card_number
OTP-AAAAA-BBBBB-CCCCC-DDDDD
```

- [ ] **Step 6: 验证前端**

Run: `cd web && npm run test -- --run && npm run build`
Expected: Vitest PASS，Vite build PASS。

- [ ] **Step 7: 提交**

```bash
git add web
git commit -m "feat: add mobile redemption and cdk admin ui"
```

### Task 8: 部署、安全、监控和生产验收

**Files:**
- Create: `codex-sms-cdk/deploy/docker-compose.yml`
- Create: `codex-sms-cdk/deploy/caddy-route.caddy`
- Create: `codex-sms-cdk/deploy/.env.example`
- Create: `codex-sms-cdk/deploy/docker-compose.restore.yml`
- Create: `codex-sms-cdk/deploy/bootstrap-shared-services.sh`
- Create: `codex-sms-cdk/deploy/backup-codex-sms.sh`
- Create: `codex-sms-cdk/deploy/verify-shared-infra.sh`
- Create: `codex-sms-cdk/scripts/configure-madao.sh`
- Create: `codex-sms-cdk/tests/e2e/redemption.spec.ts`
- Create: `codex-sms-cdk/tests/e2e/fixtures/mock-madao.ts`
- Create: `codex-sms-cdk/README.md`
- Modify: `codex-sms-cdk/Makefile`

**Interfaces:**
- Consumes: existing containers `taoai-shop-postgres`, `taoai-shop-redis`, `gpt-cdk-caddy`
- Produces: only new production containers `codex-sms-api`, `codex-sms-worker`, `codex-sms-madao`
- Produces: `make verify`, `make backup`, `make restore-check`

- [ ] **Step 1: 实现共享基础设施只读预检**

`verify-shared-infra.sh` 不修改容器、数据库或网络，只在本机写一份检查快照；逐项检查并在任一门槛不满足时非零退出：

- 宿主机至少 4 CPU、可用内存至少 1.5 GiB、可用磁盘至少 20 GiB。
- `taoai-shop-postgres`、`taoai-shop-redis`、`gpt-cdk-caddy` 均为 running/healthy。
- PostgreSQL major version 为 15、`max_connections - count(pg_stat_activity) >= 20`。
- Redis major version 为 7、内存使用率低于 70%、`aof_last_bgrewrite_status=ok`、`evicted_keys=0`。
- Docker 网络 `taoai-shop_backend` 和 `taoai_shop_front` 已存在；5432、6379 未发布到宿主机。

Run: `sudo ./deploy/verify-shared-infra.sh`
Expected: 输出 `SHARED_INFRA_OK`，同时把现有三个容器的 ID、启动时间和健康状态写入 `/opt/codex-sms-cdk/shared-infra.before`，供发布后比对。

- [ ] **Step 2: 创建独立数据库、角色并预检 Redis DB 2**

`bootstrap-shared-services.sh` 从权限为 `0600` 的 `/opt/codex-sms-cdk/secrets.env` 读取 `CODEX_SMS_DB_PASSWORD`，通过 `docker exec taoai-shop-postgres psql` 幂等执行：

```sql
CREATE ROLE codex_sms_cdk LOGIN PASSWORD :'db_password' CONNECTION LIMIT 10;
CREATE DATABASE codex_sms_cdk OWNER codex_sms_cdk;
REVOKE ALL ON DATABASE codex_sms_cdk FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE codex_sms_cdk TO codex_sms_cdk;
```

脚本必须用 `psql` 变量传入密码，不把密码拼进日志或命令回显。若角色已存在，只核对 `rolconnlimit=10` 和数据库 owner，不覆盖未知密码；不一致时停止并要求人工处理。Redis 预检只能执行：

```bash
docker exec taoai-shop-redis redis-cli -n 2 SET smscdk:preflight ok EX 60
docker exec taoai-shop-redis redis-cli -n 2 DEL smscdk:preflight
```

禁止执行 `FLUSHDB` 或 `FLUSHALL`。随后以新账号运行迁移，并确认不能读取 `taoai_shop` 数据库中的业务表。

- [ ] **Step 3: 创建只包含三个新服务的生产 Compose**

```yaml
services:
  api:
    build: ..
    container_name: codex-sms-api
    env_file:
      - .env
      - /opt/codex-sms-cdk/secrets.env
    restart: unless-stopped
    mem_limit: 512m
    cpus: 1.0
    networks: [front, shared_data, provider]
  worker:
    build: ..
    container_name: codex-sms-worker
    command: ["/app/worker"]
    env_file:
      - .env
      - /opt/codex-sms-cdk/secrets.env
    restart: unless-stopped
    mem_limit: 384m
    cpus: 1.0
    networks: [shared_data, provider]
  madao:
    image: netcookies/madao-daemon:latest
    container_name: codex-sms-madao
    env_file:
      - .env.madao
      - /opt/codex-sms-cdk/secrets.env
    volumes: [madao-data:/var/lib/madao]
    expose: ["7822"]
    restart: unless-stopped
    mem_limit: 512m
    cpus: 1.0
    networks: [provider]
networks:
  front:
    external: true
    name: taoai_shop_front
  shared_data:
    external: true
    name: taoai-shop_backend
  provider:
    name: codex_sms_provider
    internal: false
volumes:
  madao-data: {}
```

`.env.example` 固定使用 `taoai-shop-postgres:5432/codex_sms_cdk`、`taoai-shop-redis:6379`、`REDIS_DB=2`、`REDIS_PREFIX=smscdk:` 和 `http://madao:7822`。生产文件中的数据库密码、HMAC key、加密 key 和 MaDao secret 只从 `/opt/codex-sms-cdk/secrets.env` 注入。

Compose 不声明 `ports`，也不声明 PostgreSQL、Redis、Caddy 服务。`provider` 网络保留公网出站能力；安全边界依靠未发布端口阻止宿主机入站。验收：宿主机请求 `127.0.0.1:7822` 连接失败，API 容器请求 `http://madao:7822/health` 成功，MaDao 访问供应商 API 成功。

- [ ] **Step 4: 受控接入现有 Caddy**

`caddy-route.caddy` 是发布模板；发布脚本要求 `SMS_PUBLIC_HOST` 非空并校验为合法主机名，再用 `envsubst '$SMS_PUBLIC_HOST'` 渲染候选站点块，不写死生产域名：

```caddy
$SMS_PUBLIC_HOST {
    encode zstd gzip
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
        X-Content-Type-Options "nosniff"
        Referrer-Policy "same-origin"
    }
    @internal path /metrics /debug/*
    respond @internal 404
    reverse_proxy codex-sms-api:8080
}
```

发布脚本必须沿用现有商城的安全模式：备份 `/opt/gpt-cdk/Caddyfile`，在 `# BEGIN CODEX-SMS-CDK` 与 `# END CODEX-SMS-CDK` 标记间幂等替换，生成候选文件，在 `gpt-cdk-caddy` 内运行 `caddy validate`；只有验证通过才原子替换并 reload，失败则恢复备份。不得重建或重启 Caddy 容器。

- [ ] **Step 5: 创建 MaDao 路由配置脚本**

脚本使用 Bearer Secret 向 `/api/routing-plans` 写入：

```json
{
  "id": "openai-production",
  "name": "OpenAI Production",
  "service": "openai",
  "enabled": true,
  "execution_mode": "sequential",
  "execution_rounds": 1,
  "items": [
    {"id":"hero-primary","provider":"herosms","country":"US","operator":"any","enabled":true,"price_mode":"range","min_price":0,"max_price":0.20},
    {"id":"fivesim-backup","provider":"fivesim","country":"US","operator":"any","enabled":true,"price_mode":"range","min_price":0,"max_price":0.30}
  ]
}
```

生产前允许根据 PoC 结果更换国家和价格上限，但必须通过配置变更审计，不写死在业务代码中。

- [ ] **Step 6: 增加端到端测试**

`tests/e2e/fixtures/mock-madao.ts` 启动一个本地 HTTP 测试替身，保存当前 ticket，并提供 `timeoutCurrentTicket()` 与 `deliverCode(code)` 两个仅供 Playwright 调用的方法；`/api/acquire`、`/api/poll`、`/api/routing/replace`、`/api/release` 的 JSON 与 Task 4 契约完全一致。

```ts
test('no-code replacement keeps cdk usable and successful code consumes it', async ({ page }) => {
  await page.goto('/redeem')
  await page.getByTestId('cdk').fill(process.env.E2E_CDK!)
  await page.getByTestId('redeem').click()
  await expect(page.getByTestId('phone')).toBeVisible()
  await mockMadao.timeoutCurrentTicket()
  await expect(page.getByText('正在更换号码')).toBeVisible()
  await mockMadao.deliverCode('123456')
  await expect(page.getByTestId('code')).toHaveText('123456')
  await page.reload()
  await expect(page.getByTestId('code')).toHaveText('123456')
  await expect(api.openRedemption(process.env.E2E_CDK!)).rejects.toMatchObject({ status: 409 })
})
```

- [ ] **Step 7: 建立独立备份、恢复演练和统一验证命令**

`backup-codex-sms.sh` 用 `pg_dump -Fc` 只备份 `codex_sms_cdk` 到 `/opt/codex-sms-cdk/backups`，先写临时文件再原子改名，文件权限 `0600`，原子更新同目录 `latest.dump` 符号链接并保留 14 天。现有商城备份脚本只覆盖 `taoai_shop`，不能复用。`docker-compose.restore.yml` 使用 `postgres:15-alpine` 创建隔离的 `postgres-restore` 服务，挂载只读备份目录，不连接生产网络和数据卷。

```make
verify:
	go test -race ./...
	cd web && npm run test -- --run
	cd web && npm run build
	npx playwright test
	docker compose -f deploy/docker-compose.yml config --quiet

backup:
	sudo ./deploy/backup-codex-sms.sh

restore-check:
	docker compose -f deploy/docker-compose.restore.yml up -d postgres-restore
	docker compose -f deploy/docker-compose.restore.yml exec -T postgres-restore pg_restore --clean --if-exists -U codex_sms_cdk -d codex_sms_cdk /backup/latest.dump
	docker compose -f deploy/docker-compose.restore.yml exec -T postgres-restore psql -U codex_sms_cdk -d codex_sms_cdk -c 'SELECT count(*) FROM redemptions'
```

- [ ] **Step 8: 执行安全、共享资源和日志验收**

Run:

```bash
make verify
rg -n 'OTP-[A-Z0-9-]{20,}|\+[0-9]{8,}|[0-9]{6}' logs/ tests/output/ || true
docker compose -f deploy/docker-compose.yml ps
sudo ./deploy/verify-shared-infra.sh --compare /opt/codex-sms-cdk/shared-infra.before
```

Expected:

- 全部测试通过。
- 脱敏扫描无完整 CDK、手机号、验证码。
- 只有 `codex-sms-api`、`codex-sms-worker`、`codex-sms-madao` 三个新容器 healthy/running。
- 现有 PostgreSQL、Redis、Caddy 的容器 ID、启动时间和健康状态未变化。
- MaDao 无宿主机公开端口。
- PostgreSQL `codex_sms_cdk` 角色连接上限为 10，当前连接不超过 9。
- Redis DB 2 中本系统键全部以 `smscdk:` 开头且均有 TTL；其他 DB 的 keyspace 数量未变化。
- 宿主机可用内存不低于 1.5 GiB、磁盘使用率低于 80%、Redis 内存低于 70%。

- [ ] **Step 9: 复核供应商准入配置**

按 Task 0 已准入路线各执行 10 次发布前回归，核对 MaDao 返回价格没有超过报告中的 `max_price`，到达率仍不低于 70%，收码后通过率仍不低于 80%；不达标时禁止写入 `openai-production`。

- [ ] **Step 10: 灰度上线并分级放量**

1. 导入 20 枚灰度 CDK 到 Dujiao-Next 测试商品。
2. 限制最多 50 个并发等待短信会话、每天最多 50 次上游购买。
3. 连续观察 48 小时的到达率、成功成本、退款和未知订单。
4. 使用 Mock MaDao 完成 100 并发压测，API P95 小于 500ms，且 PostgreSQL 总连接低于 70、CDK 角色连接低于 9、Redis 内存低于 70% 后，才把并发上限提高到 100、每日额度提高到 500 次。
5. 保留上一版本镜像和数据库备份；回滚只切换 API/Worker 镜像，不删除 PostgreSQL、Redis 或 MaDao 数据卷。
6. 超过 100 并发前必须重新执行容量评估；共享 Redis 使用超过 50% 或出现团队隔离要求时迁移独立 Redis/ACL。

- [ ] **Step 11: 提交**

```bash
git add deploy scripts tests Makefile README.md
git commit -m "ops: add production deployment and release gates"
```

## Self-Review Result

- 规格覆盖：CDK生成、Dujiao导入、原子兑换、MaDao取号、HeroSMS/5SIM路由、无码重试、成功核销、对账、敏感数据清理、部署和灰度均有对应任务。
- 占位检查：实施步骤没有未决占位或未定义的后续功能；国家线路允许在 PoC 后通过审计配置调整，但业务接口和状态机固定。
- 类型一致性：`RedemptionID`、`ProviderOrderID`、`MaDaoTicketID`、`Status` 在 Task 3–8 中保持一致；MaDao 客户端只由 Redemption Service/Worker 调用。
- 范围检查：没有租号、续费、钱包、任意服务、Dujiao支付回调或自动注册功能。
- 复用检查：生产只新增 API、Worker、MaDao；PostgreSQL 使用独立库/角色，Redis 使用 DB 2/前缀/TTL，Caddy 采用验证后原子合并，发布前后比对现有容器未被重建或重启。
- 容量检查：50 并发灰度、100 并发压测门禁、数据库/Redis/主机告警和超过门槛后的拆分条件均有可执行步骤。
