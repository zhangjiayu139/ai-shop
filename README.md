# AI Shop

本仓库用于存放 AI 商品销售相关的独立服务。

## 子项目

- [`cdk-recharge`](./cdk-recharge/)：GPT CDK 自助充值系统，包含用户充值页面、运营后台、后端服务及 Docker 部署配置。
- [`codex-sms-cdk`](./codex-sms-cdk/)：一次性 OpenAI/Codex 短信接码 CDK 兑换服务。Dujiao-Next 负责订单和 CDK 发货，本服务负责 CDK 核验、取号、收码和核销。
