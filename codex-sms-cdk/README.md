# Codex SMS CDK

一次性 OpenAI/Codex 短信接码 CDK 兑换服务。

## V1 范围

- Dujiao-Next 负责商品、订单、支付和发放 CDK。
- 本服务负责生成 CDK、兑换、获取一次性手机号、接收验证码和核销权益。
- MaDao 作为私网供应商网关，首期接入 HeroSMS 和 5SIM。
- 无码不核销 CDK；收到目标短信后才核销。
- 暂不实现 30/60/90 天租号及按月续费。

## 文档

- [设计方案](./docs/superpowers/specs/2026-09-16-one-time-sms-cdk-design.md)
- [实施计划](./docs/superpowers/plans/2026-09-16-one-time-sms-cdk.md)

## 计划技术栈

- Go 1.24
- Vue 3 + TypeScript
- PostgreSQL 16
- Redis 7
- MaDao
- Docker Compose

当前仅完成设计与实施计划，业务代码尚未开始。
