<template>
  <div class="recharge-home">
    <header class="recharge-header">
      <div class="recharge-header-inner">
        <router-link to="/" class="recharge-brand"><Tickets aria-hidden="true" /><span>{{ brand.name || t('home.brand') }}</span></router-link>
        <div class="recharge-tools"><LanguageToggle /><ThemeToggle /></div>
      </div>
    </header>
    <main class="recharge-main">
      <p v-if="isPreview" class="preview-notice">{{ t('rechargeHome.localPreview') }}</p>
      <div class="recharge-intro">
        <div><h1>{{ t('rechargeHome.title') }}</h1><p>{{ t('rechargeHome.subtitle') }}</p></div>
        <nav class="recharge-shortcuts" aria-label="其他功能">
          <router-link to="/batch"><Collection aria-hidden="true" />{{ t('home.services.batch.title') }}</router-link>
          <router-link to="/history"><Search aria-hidden="true" />{{ t('home.services.lookup.title') }}</router-link>
          <router-link to="/billing"><Document aria-hidden="true" />{{ t('home.services.billing.title') }}</router-link>
        </nav>
      </div>
      <div class="recharge-workspace">
        <ol class="recharge-steps" :aria-label="t('rechargeHome.steps')">
          <li v-for="(label, i) in steps" :key="i" :data-flow-step="i + 1" :aria-current="step === i + 1 ? 'step' : undefined" :class="{ current: step === i + 1, passed: step > i + 1 }">
            <span class="step-number">{{ i + 1 }}</span><span>{{ label }}</span>
          </li>
        </ol>
        <form v-show="step === 1" class="recharge-panel recharge-form" novalidate :aria-busy="busy" @submit.prevent="doValidate">
          <div class="recharge-field">
            <label for="recharge-code">{{ t('rechargeHome.code') }}</label>
            <input id="recharge-code" ref="codeInput" v-model="code" class="input" aria-label="CDK 卡密" :placeholder="t('rechargeHome.codePlaceholder')" autocomplete="off" spellcheck="false" :disabled="busy" :aria-invalid="!!error && errorField === 'code'" aria-describedby="code-feedback" @input="invalidateVerification(true)" />
            <div id="code-feedback" aria-live="polite">
              <p v-if="error && errorField === 'code'" class="field-error" role="alert">{{ error }}</p>
              <p v-else-if="previewInfo" class="code-preview"><span>{{ t('rechargeHome.plan') }}：<b>{{ targetPlan ? planLabel(targetPlan) : '—' }}</b></span><span>{{ previewInfo.message || t('rechargeHome.validCode') }}</span></p>
              <p v-else class="field-hint">{{ t('rechargeHome.codeHint') }}</p>
            </div>
          </div>
          <div class="recharge-field">
            <div class="credential-heading">
              <label :for="credMode === 'session' ? 'recharge-session' : 'recharge-email'">{{ t('rechargeHome.credentials') }}</label>
              <div class="credential-switch" role="group" :aria-label="t('rechargeHome.credentials')">
                <button type="button" :aria-pressed="credMode === 'session'" :disabled="busy" @click="setCredentialMode('session')">Session</button>
                <button type="button" data-testid="mailbox-mode" :aria-pressed="credMode === 'mailbox'" :disabled="busy" @click="setCredentialMode('mailbox')">{{ t('rechargeHome.mailbox') }}</button>
              </div>
            </div>
            <textarea v-if="credMode === 'session'" id="recharge-session" v-model="sessionRaw" class="input session-input" :aria-label="t('rechargeHome.sessionLabel')" :placeholder="t('rechargeHome.sessionPlaceholder')" autocomplete="off" spellcheck="false" :disabled="busy" :aria-invalid="!!error && errorField === 'credential'" aria-describedby="credential-feedback" @input="invalidateVerification(false)" />
            <div v-else class="mailbox-fields">
              <label class="sr-only" for="recharge-email">{{ t('rechargeHome.email') }}</label>
              <input id="recharge-email" v-model="email" type="email" class="input" :placeholder="t('rechargeHome.email')" autocomplete="off" :disabled="busy" :aria-invalid="!!error && errorField === 'credential'" aria-describedby="credential-feedback" @input="invalidateVerification(false)" />
              <label class="sr-only" for="recharge-password">{{ t('rechargeHome.password') }}</label>
              <input id="recharge-password" v-model="password" type="password" class="input" :placeholder="t('rechargeHome.password')" autocomplete="off" :disabled="busy" :aria-invalid="!!error && errorField === 'credential'" aria-describedby="credential-feedback" @input="invalidateVerification(false)" />
            </div>
            <div id="credential-feedback" aria-live="polite"><p v-if="error && errorField === 'credential'" class="field-error" role="alert">{{ error }}</p></div>
            <div class="credential-actions">
              <button type="button" class="text-action" :aria-expanded="helpOpen" aria-controls="credential-help" @click="helpOpen = !helpOpen">{{ t('rechargeHome.getSession') }}</button>
              <button type="button" class="text-action muted-action" data-testid="clear-credentials" :disabled="busy" @click="clearCredentials">{{ t('rechargeHome.clear') }}</button>
            </div>
            <div v-if="helpOpen" id="credential-help" class="credential-help">
              <p>{{ t('rechargeHome.help') }}</p>
              <a href="https://chatgpt.com/api/auth/session" target="_blank" rel="noopener noreferrer" class="app-link">{{ t('rechargeHome.openSession') }} ↗</a>
            </div>
          </div>
          <p class="credential-privacy"><Lock aria-hidden="true" /><span>{{ t('rechargeHome.privacy') }}</span></p>
          <p v-if="error && errorField === 'general'" class="field-error" role="alert">{{ error }}</p>
          <button type="submit" class="btn-primary recharge-submit" :disabled="busy">
            <span aria-live="polite">{{ busy ? t(busyPhase === 'preview' ? 'rechargeHome.previewing' : 'rechargeHome.preflighting') : t('rechargeHome.continue') }}</span><ArrowRight v-if="!busy" aria-hidden="true" />
          </button>
        </form>

      <!-- 2 confirm -->
      <section v-show="step === 2" class="recharge-panel space-y-4" data-testid="confirm-panel">
        <h2 class="text-xl font-bold text-ink">{{ t('rechargeHome.confirm') }}</h2>
        <p class="text-sm text-muted">{{ t('rechargeHome.confirmHint') }}</p>

        <!-- 与卡台直充预检一致：邮箱 + 订阅事实 -->
        <div v-if="account.checked" class="rounded-xl border p-4 space-y-3" style="border-color: var(--brd); background: var(--surface-2, var(--soft))">
          <div class="flex flex-wrap items-center gap-2">
            <strong class="text-ink text-base">{{ account.email || '预检未提供账号邮箱' }}</strong>
            <el-tag size="small" :type="subscriptionStatusTag">{{ subscriptionStatusText }}</el-tag>
          </div>
          <dl class="confirmation-summary">
            <div><dt>{{ t('rechargeHome.plan') }}</dt><dd>{{ targetPlan ? planLabel(targetPlan) : '—' }}</dd></div>
            <div><dt>{{ t('rechargeHome.currentPlan') }}</dt><dd>{{ account.currentPlan ? planLabel(account.currentPlan) : '上游未提供' }}</dd></div>
          </dl>
          <details class="subscription-details" open><summary>{{ t('rechargeHome.details') }}</summary>
          <dl class="account-facts">
            <div>
              <dt>目标套餐</dt>
              <dd>{{ targetPlan ? planLabel(targetPlan) : '上游未提供' }}</dd>
            </div>
            <div>
              <dt>当前套餐</dt>
              <dd>{{ account.currentPlan ? planLabel(account.currentPlan) : '上游未提供' }}</dd>
            </div>
            <div>
              <dt>订阅状态</dt>
              <dd>{{ subscriptionStatusText }}</dd>
            </div>
            <div>
              <dt>套餐到期</dt>
              <dd>{{ account.subscriptionActiveUntil ? fmtTime(account.subscriptionActiveUntil) : '上游未提供' }}</dd>
            </div>
            <div>
              <dt>剩余</dt>
              <dd>{{ account.subscriptionActiveUntil ? subscriptionRemaining : '上游未提供' }}</dd>
            </div>
            <div>
              <dt>自动续费</dt>
              <dd :class="account.subscriptionWillRenew === true ? 'text-warn' : account.subscriptionWillRenew === false ? 'text-good' : ''">
                {{ renewalStatusText }}
              </dd>
            </div>
            <div>
              <dt>最近付款时间</dt>
              <dd>{{ lastPaymentAtText }}</dd>
            </div>
            <div>
              <dt>最近付款</dt>
              <dd>{{ lastPaymentText }}</dd>
            </div>
            <div>
              <dt>支付方式</dt>
              <dd>{{ paymentMethodText }}</dd>
            </div>
          </dl>
          </details>
        </div>
        <div v-else class="rounded-xl bg-soft p-3 text-sm text-muted">
          预检未返回账号摘要，仍可尝试兑换（以卡台校验为准）。
        </div>

        <div v-if="alreadySatisfied" class="alert" style="background: var(--warn-soft, #fef3c7); color: var(--warn, #b45309); border-color: var(--warn, #d97706)">
          {{ alreadySatisfiedHint }}
        </div>

        <div v-if="account.subscriptionIsDelinquent === true" class="alert" style="background: var(--warn-soft, #fef3c7); color: var(--warn, #b45309); border-color: var(--warn, #d97706)">
          该账号有未结清账单（欠费）。仍可兑换：卡台会先取消原订阅再重新开通，但成功率低于正常账号。
        </div>

        <div v-if="error" class="alert alert-error">{{ error }}</div>
        <div class="flex gap-3">
          <button class="btn-secondary flex-1" :disabled="busy" data-testid="edit-details" @click="step = 1">{{ t('rechargeHome.back') }}</button>
          <button class="btn-primary flex-1" data-testid="confirm-redeem" :disabled="busy || alreadySatisfied" @click="doRedeem">
            {{ busy ? t('common.submitting') : alreadySatisfied ? '当前套餐已满足' : t('rechargeHome.confirm') }}
          </button>
        </div>
      </section>

      <!-- 3 result -->
      <section v-show="step === 3" class="recharge-panel space-y-4" data-testid="result-panel">
        <h2 class="text-xl font-bold text-ink">兑换进度</h2>

        <div class="flex flex-wrap items-center gap-2">
          <el-tag :type="statusTagType(resultStatus)" size="large">{{ resultStatus || '—' }}</el-tag>
          <span v-if="resultStage" class="text-sm text-muted mono">阶段 {{ resultStage }}</span>
          <span v-if="polling" class="text-sm text-muted">
            <span class="inline-block animate-pulse">●</span> 实时轮询中（约 3s）
          </span>
          <span v-else-if="isTerminal(resultStatus)" class="text-sm" :class="resultStatus === 'completed' ? 'text-good' : 'text-muted'">
            已结束
          </span>
        </div>

        <div class="rounded-xl bg-soft p-3 text-sm space-y-2">
          <div class="flex justify-between gap-3 items-center">
            <span class="text-muted shrink-0">兑换账号</span>
            <span class="mono text-ink text-right break-all">{{ displayResultEmail || '—' }}</span>
          </div>
          <div class="flex justify-between gap-3 items-center">
            <span class="text-muted shrink-0">银行卡</span>
            <span class="mono text-ink">
              <template v-if="resultCardLastFour">•••• {{ resultCardLastFour }}</template>
              <template v-else><span class="text-muted">开卡后显示尾号</span></template>
            </span>
          </div>
        </div>

        <div v-if="resultMessage" class="rounded-xl bg-soft p-3 text-sm text-ink">
          {{ resultMessage }}
        </div>

        <!-- 进度步骤条（由 stage / events 推导） -->
        <div class="grid grid-cols-4 gap-2 text-center text-xs">
          <div
            v-for="p in progressSteps"
            :key="p.key"
            class="rounded-lg border px-2 py-2"
            :class="p.active ? 'border-primary bg-primary/10 text-ink font-semibold' : 'border-brd text-muted'"
          >
            {{ p.label }}
          </div>
        </div>

        <!-- 时间线明细（卡台 events） -->
        <div v-if="timeline.length" class="space-y-0">
          <div class="text-sm font-medium text-ink mb-2">处理明细</div>
          <ol class="space-y-3 border-l-2 pl-4" style="border-color: var(--brd)">
            <li v-for="(ev, idx) in timeline" :key="ev.id || idx" class="relative">
              <span
                class="absolute -left-[1.35rem] top-1 h-2.5 w-2.5 rounded-full"
                :style="{ background: eventDot(ev.category) }"
              />
              <div class="flex flex-wrap items-baseline gap-2">
                <b class="text-sm text-ink">{{ stepLabel(ev.step) }}</b>
                <el-tag size="small" :type="categoryTag(ev.category)">{{ ev.category || 'pending' }}</el-tag>
                <span class="text-xs text-subtle">{{ fmtTime(ev.created_at) }}</span>
              </div>
              <p class="text-sm text-muted mt-0.5">
                {{ ev.public_message || ev.to_status || '—' }}
              </p>
            </li>
          </ol>
        </div>
        <div v-else-if="polling" class="text-sm text-muted">
          已提交，等待卡台返回步骤明细…
        </div>

        <details class="text-xs text-muted">
          <summary class="cursor-pointer select-none">原始响应（调试）</summary>
          <pre class="rounded-xl bg-soft p-4 overflow-auto max-h-48 mt-2">{{ resultPretty }}</pre>
        </details>

        <div v-if="error" class="alert alert-error">{{ error }}</div>
        <div v-if="isTerminal(resultStatus) && resultStatus !== 'completed'" class="alert alert-error">
          兑换未成功。若状态为 review/pending 请勿重复提交；可联系发码方或稍后用同一设备再查结果。
        </div>
        <div v-if="resultStatus === 'completed'" class="alert alert-success">开通完成，请到 ChatGPT 账号确认套餐。</div>
        <p v-if="!isTerminal(resultStatus)" class="field-hint">结果确认前请勿重复兑换，可稍后在同一设备查询进度。</p>
        <button class="btn-secondary" data-testid="reset-recharge" :disabled="busy || !isTerminal(resultStatus)" @click="resetAll">再兑一张</button>
      </section>
        <div v-if="step === 1" class="recharge-help-footer">
          <span>{{ t('rechargeHome.needHelp') }}</span>
          <button type="button" class="text-action" @click="helpOpen = !helpOpen">{{ t('rechargeHome.helpLink') }}</button>
        </div>
      </div>
    </main>
    <footer class="recharge-footer"><span>{{ brand.name || t('home.brand') }}</span><span>{{ t('rechargeHome.footer') }}</span></footer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import LanguageToggle from '../../components/LanguageToggle.vue'
import ThemeToggle from '../../components/ThemeToggle.vue'
import { ArrowRight, Collection, Document, Lock, Search, Tickets } from '@element-plus/icons-vue'
import { siteBrand } from '../../theme'
import { planLabel, planSatisfied as isSatisfied } from '../../lib/plan'
import { restoreRechargeStep, serializeRechargeStep } from './recharge-progress'

const { t } = useI18n({ useScope: 'global' })
const route = useRoute()
const steps = computed(() => [t('rechargeHome.fill'), t('rechargeHome.confirm'), t('rechargeHome.result')])
const brand = siteBrand
const isPreview = import.meta.env.MODE === 'visual-preview'
const helpOpen = ref(false)
const busyPhase = ref<'preview' | 'preflight'>('preview')
const errorField = ref<'code' | 'credential' | 'general'>('code')
const codeInput = ref<HTMLInputElement | null>(null)
let flowVersion = 0
let pollVersion = 0
let disposed = false
const step = ref(1)
const busy = ref(false)
const error = ref('')
const code = ref('')
const previewInfo = ref<any>(null)
const redemptionToken = ref('')
const preflightToken = ref('')
const credMode = ref<'session' | 'mailbox'>('session')
const sessionRaw = ref('')
const email = ref('')
const password = ref('')
/** 预检成功后的账号/订阅摘要（与卡台 GPT 直充 preflight 字段对齐） */
const account = ref({
  checked: false,
  email: '',
  currentPlan: '',
  subscriptionHasActive: null as boolean | null,
  subscriptionActiveUntil: '',
  canPurchaseAt: '',
  subscriptionWillRenew: null as boolean | null,
  subscriptionIsDelinquent: null as boolean | null,
  lastPayment: null as any,
  paymentMethod: null as any,
})
const resultStatus = ref('')
const resultStage = ref('')
const resultMessage = ref('')
const resultEmail = ref('')
const resultCardLastFour = ref('')
const resultBody = ref<any>(null)
const timeline = ref<any[]>([])
const polling = ref(false)
let pollTimer: any = null
const displayResultEmail = computed(() => resultEmail.value || account.value.email || '')

const PROGRESS_KEY = 'cdk_redeem_progress_v1'
const nowTick = ref(Date.now())
let nowTimer: any = null

const deviceId = (() => {
  const k = 'cdk_device_id'
  let v = localStorage.getItem(k)
  if (!v) {
    v = 'web-' + Math.random().toString(36).slice(2) + Date.now().toString(36)
    localStorage.setItem(k, v)
  }
  return v
})()

function saveProgress() {
  try {
    const payload = {
      step: serializeRechargeStep(step.value),
      code: code.value,
      redemptionToken: redemptionToken.value,
      preflightToken: preflightToken.value,
      previewInfo: previewInfo.value,
      account: account.value,
      resultStatus: resultStatus.value,
      resultStage: resultStage.value,
      resultMessage: resultMessage.value,
      resultEmail: resultEmail.value,
      resultCardLastFour: resultCardLastFour.value,
      resultBody: resultBody.value,
      timeline: timeline.value,
      savedAt: Date.now(),
    }
    sessionStorage.setItem(PROGRESS_KEY, JSON.stringify(payload))
  } catch {
    /* ignore quota */
  }
}

function loadProgress(): boolean {
  try {
    const raw = sessionStorage.getItem(PROGRESS_KEY)
    if (!raw) return false
    const p = JSON.parse(raw)
    if (!p || typeof p !== 'object') return false
    // 超过 7 天丢弃
    if (p.savedAt && Date.now() - Number(p.savedAt) > 7 * 24 * 3600 * 1000) {
      sessionStorage.removeItem(PROGRESS_KEY)
      return false
    }
    if (p.code) code.value = String(p.code)
    if (p.redemptionToken) redemptionToken.value = String(p.redemptionToken)
    if (p.preflightToken) preflightToken.value = String(p.preflightToken)
    if (p.previewInfo) previewInfo.value = p.previewInfo
    if (p.account && typeof p.account === 'object') {
      account.value = {
        checked: !!p.account.checked,
        email: String(p.account.email || ''),
        currentPlan: String(p.account.currentPlan || ''),
        subscriptionHasActive:
          typeof p.account.subscriptionHasActive === 'boolean' ? p.account.subscriptionHasActive : null,
        subscriptionActiveUntil: String(p.account.subscriptionActiveUntil || ''),
        canPurchaseAt: String(p.account.canPurchaseAt || ''),
        subscriptionWillRenew:
          typeof p.account.subscriptionWillRenew === 'boolean' ? p.account.subscriptionWillRenew : null,
        subscriptionIsDelinquent:
          typeof p.account.subscriptionIsDelinquent === 'boolean' ? p.account.subscriptionIsDelinquent : null,
        lastPayment: p.account.lastPayment || null,
        paymentMethod: p.account.paymentMethod || null,
      }
    }
    if (p.resultStatus) resultStatus.value = String(p.resultStatus)
    if (p.resultStage) resultStage.value = String(p.resultStage)
    if (p.resultMessage) resultMessage.value = String(p.resultMessage)
    if (p.resultEmail) resultEmail.value = String(p.resultEmail)
    if (p.resultCardLastFour) resultCardLastFour.value = String(p.resultCardLastFour)
    if (p.resultBody) resultBody.value = p.resultBody
    if (Array.isArray(p.timeline)) timeline.value = p.timeline
    step.value = restoreRechargeStep(p)
    return step.value > 1
  } catch {
    /* ignore */
  }
  return false
}

function clearProgress() {
  try {
    sessionStorage.removeItem(PROGRESS_KEY)
  } catch {
    /* ignore */
  }
}

watch(
  [step, code, redemptionToken, preflightToken, previewInfo, account, resultStatus, resultStage, resultMessage, resultBody, timeline],
  () => saveProgress(),
  { deep: true },
)

const resultPretty = computed(() => JSON.stringify(resultBody.value, null, 2))

const targetPlan = computed(() =>
  String(previewInfo.value?.plan || previewInfo.value?.plan_type || '').toLowerCase(),
)

const subscriptionStatusText = computed(() => {
  if (account.value.subscriptionHasActive === true) return '有效'
  if (
    account.value.subscriptionHasActive === false
    || String(account.value.currentPlan).toLowerCase() === 'free'
  ) {
    return '已到期 / 免费版'
  }
  return '上游未提供'
})

const subscriptionStatusTag = computed(() => {
  if (account.value.subscriptionHasActive === true) return 'success'
  if (account.value.subscriptionHasActive === false) return 'info'
  return 'info'
})

const renewalStatusText = computed(() => {
  if (account.value.subscriptionWillRenew === true) return '到期后自动续费'
  if (account.value.subscriptionWillRenew === false) return '到期后不续费'
  return '上游未提供'
})

const subscriptionRemaining = computed(() =>
  remainingTime(account.value.subscriptionActiveUntil, nowTick.value),
)

const lastPaymentAtText = computed(() => {
  const lp = account.value.lastPayment
  if (!lp) return '上游未提供'
  const at = lp.paidAt || lp.paid_at || lp.created || lp.created_at
  return at ? fmtTime(at) : '上游未提供'
})

const lastPaymentText = computed(() => {
  const lp = account.value.lastPayment
  if (!lp) return '上游未提供'
  const amount = formatPaymentAmount(lp.amountMinor ?? lp.amount_minor, lp.currency)
  const status = String(lp.status || '').toLowerCase() === 'paid' ? '已支付' : (lp.status || '上游未提供')
  return amount ? `${amount} · ${status}` : status
})

const paymentMethodText = computed(() => {
  const method = account.value.paymentMethod
  if (!method) return '上游未提供'
  const brand = String(method.brand || method.type || '').toUpperCase()
  const last4 = method.last4 || method.last_4
  const label = [brand, last4 ? `**** ${last4}` : ''].filter(Boolean).join(' ')
  const expMonth = method.expMonth || method.exp_month
  const expYear = method.expYear || method.exp_year
  const expiry = expMonth && expYear
    ? `卡片到期 ${String(expMonth).padStart(2, '0')}/${expYear}`
    : ''
  const isDefault = method.isDefault ?? method.is_default
  return [label, expiry, isDefault ? '默认支付方式' : ''].filter(Boolean).join(' · ') || '上游未提供'
})

const alreadySatisfied = computed(() => {
  if (!account.value.checked || !targetPlan.value) return false
  if (account.value.subscriptionHasActive === false) return false
  return planSatisfied(account.value.currentPlan, targetPlan.value)
})

const alreadySatisfiedHint = computed(() => {
  const plan = planLabel(targetPlan.value)
  const until = account.value.canPurchaseAt || account.value.subscriptionActiveUntil
  if (until && account.value.subscriptionWillRenew === true) {
    return `账号已有 ${plan} 或更高套餐，当前周期至 ${fmtTime(until)} 并会自动续费，取消并到期前不能重复购买。`
  }
  if (until && account.value.subscriptionWillRenew === false) {
    return `账号已有 ${plan} 或更高套餐，最早可在 ${fmtTime(until)} 后再次购买。`
  }
  if (until) {
    return `账号已有 ${plan} 或更高套餐，当前周期至 ${fmtTime(until)}，暂不能重复购买。`
  }
  return `账号已有 ${plan} 或更高套餐，本次不能重复购买。`
})

function planSatisfied(currentPlan: string, requestedPlan: string) {
  return isSatisfied(currentPlan, requestedPlan, previewInfo.value?.plan_flow)
}

function remainingTime(value: string, timestamp = Date.now()) {
  const expiresAt = Date.parse(value || '')
  if (!Number.isFinite(expiresAt)) return '—'
  const minutes = Math.max(0, Math.ceil((expiresAt - timestamp) / 60000))
  if (minutes <= 0) return '已到期'
  const days = Math.floor(minutes / 1440)
  const hours = Math.floor((minutes % 1440) / 60)
  const restMinutes = minutes % 60
  if (days > 0) return `${days} 天 ${hours} 小时`
  if (hours > 0) return `${hours} 小时 ${restMinutes} 分钟`
  return `${restMinutes} 分钟`
}

function formatPaymentAmount(value: unknown, currency: unknown) {
  if (value === null || value === undefined || value === '') return ''
  const amount = Number(value)
  const code = String(currency || '').toUpperCase()
  if (!Number.isFinite(amount)) return ''
  let digits = 2
  if (code) {
    try {
      digits =
        new Intl.NumberFormat(undefined, { style: 'currency', currency: code }).resolvedOptions()
          .maximumFractionDigits ?? 2
    } catch {
      /* use two decimals */
    }
  }
  return `${code ? `${code} ` : ''}${(amount / 10 ** digits).toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })}`
}

function applyAccountFromPreflight(data: any) {
  const body = data?.data && typeof data.data === 'object' ? data.data : data || {}
  account.value = {
    checked: Boolean(body.email || body.account_email || body.currentPlan || body.current_plan || body.plan),
    email: String(body.email || body.account_email || ''),
    currentPlan: String(body.currentPlan || body.current_plan || body.plan || ''),
    subscriptionHasActive:
      typeof body.subscription_has_active === 'boolean' ? body.subscription_has_active : null,
    subscriptionActiveUntil: String(body.subscription_active_until || ''),
    canPurchaseAt: String(body.can_purchase_at || body.subscription_active_until || ''),
    subscriptionWillRenew:
      typeof body.subscription_will_renew === 'boolean' ? body.subscription_will_renew : null,
    // 欠费只提示不拦截：卡台会先取消订阅再重开，多数可恢复
    subscriptionIsDelinquent:
      typeof body.subscription_is_delinquent === 'boolean' ? body.subscription_is_delinquent : null,
    lastPayment: body.last_payment || null,
    paymentMethod: body.payment_method || null,
  }
}

function clearAccount() {
  account.value = {
    checked: false,
    email: '',
    currentPlan: '',
    subscriptionHasActive: null,
    subscriptionActiveUntil: '',
    canPurchaseAt: '',
    subscriptionWillRenew: null,
    subscriptionIsDelinquent: null,
    lastPayment: null,
    paymentMethod: null,
  }
}

const TERMINAL = new Set(['completed', 'declined', 'failed_precharge', 'cancelled', 'failed'])

function isTerminal(st: string) {
  return TERMINAL.has(String(st || '').toLowerCase())
}

function statusTagType(st: string) {
  const s = String(st || '').toLowerCase()
  if (s === 'completed') return 'success'
  if (['declined', 'failed_precharge', 'cancelled', 'failed'].includes(s)) return 'danger'
  if (['review', 'pending', 'card_open_review', 'card_recharge_review'].includes(s)) return 'warning'
  return 'info'
}

function categoryTag(c: string) {
  if (c === 'success' || c === 'completed') return 'success'
  if (c === 'failed' || c === 'error') return 'danger'
  if (c === 'warning') return 'warning'
  return 'info'
}

function eventDot(c: string) {
  if (c === 'success' || c === 'completed') return 'var(--good, #16a34a)'
  if (c === 'failed' || c === 'error') return 'var(--err, #dc2626)'
  if (c === 'warning') return 'var(--warn, #d97706)'
  return 'var(--primary, #2563eb)'
}

function stepLabel(stepKey: string) {
  const map: Record<string, string> = {
    queued: '排队受理',
    credential_check: '凭证校验',
    pricing: '计价',
    checkout: '开卡/绑卡',
    payment: '支付扣款',
    subscription: '订阅生效',
    invoice: '账单',
    renewal: '续费处理',
    reconcile: '对账确认',
    completed: '完成',
  }
  return map[stepKey] || stepKey || '处理中'
}

function fmtTime(v: any) {
  if (!v) return ''
  try {
    const d = new Date(v)
    if (Number.isNaN(d.getTime())) return String(v)
    return d.toLocaleString()
  } catch {
    return String(v)
  }
}

/** 粗粒度进度条：受理 → 开卡/资金 → 支付 → 开通 */
const progressSteps = computed(() => {
  const keys = [
    { key: 'accept', label: '受理' },
    { key: 'card', label: '开卡/资金' },
    { key: 'pay', label: '支付' },
    { key: 'done', label: '开通' },
  ]
  const st = String(resultStatus.value || '').toLowerCase()
  const stage = String(resultStage.value || '').toLowerCase()
  let idx = 0
  if (st === 'completed') idx = 3
  else if (['declined', 'failed_precharge', 'cancelled', 'failed'].includes(st)) {
    // 停在失败前最远一步
    if (stage.includes('pay') || stage.includes('checkout') || stage.includes('subscription')) idx = 2
    else if (stage.includes('card') || stage.includes('fund')) idx = 1
    else idx = 0
  } else if (stage.includes('subscription') || stage.includes('paid') || stage.includes('invoice')) idx = 2
  else if (stage.includes('dispatch') || stage.includes('payment') || stage.includes('checkout') || stage.includes('spend')) idx = 2
  else if (stage.includes('card') || stage.includes('fund') || stage.includes('await')) idx = 1
  else if (timeline.value.some((e) => ['payment', 'subscription', 'checkout'].includes(e.step))) idx = 2
  else if (timeline.value.length) idx = 1
  return keys.map((k, i) => ({ ...k, active: i <= idx }))
})

function extractCardLastFour(order: any): string {
  const last = String(order?.card_last_four || '').trim()
  if (/^\d{4}$/.test(last)) return last
  const n = String(order?.card_number || '').replace(/\D/g, '')
  return n.length >= 4 ? n.slice(-4) : ''
}

function applyResultPayload(data: any) {
  resultBody.value = data
  // 卡台公开结构：{ order: {status,stage,message,account_email,card_last_four}, events: [] }
  // 兼容顶层扁平 / data 包裹
  const order = data?.order || data?.data?.order || data?.data || data || {}
  const st =
    order.status ||
    data?.status ||
    data?.data?.status ||
    ''
  const stage = order.stage || data?.stage || data?.data?.stage || ''
  const message =
    order.message ||
    order.user_message ||
    data?.message ||
    data?.user_message ||
    data?.data?.message ||
    ''
  resultStatus.value = st
  resultStage.value = stage
  resultMessage.value = message
  const email = String(order.account_email || order.email || data?.account_email || '').trim()
  if (email) resultEmail.value = email
  const last4 = extractCardLastFour(order)
  if (last4) resultCardLastFour.value = last4

  let events = data?.events || data?.data?.events || order.events || []
  if (!Array.isArray(events)) events = []
  timeline.value = events.slice().sort((a: any, b: any) => {
    const ta = new Date(a.created_at || 0).getTime()
    const tb = new Date(b.created_at || 0).getTime()
    return ta - tb
  })
}

async function api(path: string, init: RequestInit = {}) {
  const headers = new Headers(init.headers || {})
  headers.set('X-Redemption-Device', deviceId)
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  const r = await fetch(path, { ...init, headers, credentials: 'include' })
  const text = await r.text()
  let data: any = null
  try { data = text ? JSON.parse(text) : null } catch { data = { raw: text } }
  return { r, data }
}

onUnmounted(() => {
  disposed = true
  flowVersion++
  pollVersion++
  if (pollTimer) clearInterval(pollTimer)
  if (nowTimer) clearInterval(nowTimer)
})

/** 完整 Session：必须含 sessionToken（JWE）；禁止纯 AT */
function extractSession(raw: string): string {
  const s = raw.trim()
  if (!s) return ''
  // 裸 JWE session-token
  if (!s.startsWith('{') && s.split('.').length >= 5) return s
  // 三段 JWT = 纯 AT → 拒绝
  if (!s.startsWith('{') && s.startsWith('eyJ') && s.split('.').length === 3) return ''
  if (s.startsWith('{')) {
    try {
      const o = JSON.parse(s)
      const st = String(o.sessionToken || o.session_token || o.token?.sessionToken || '').trim()
      if (!st) return ''
      // 回传完整 JSON，便于预检绑定 session
      return s
    } catch {
      return ''
    }
  }
  return s.length > 40 ? s : ''
}

async function tryResumeByCode(cdk: string, version = flowVersion): Promise<boolean> {
  const { r, data } = await api(
    '/api/v1/public/cdk/result-by-code?code=' + encodeURIComponent(cdk),
  )
  if (disposed || version !== flowVersion || code.value.trim() !== cdk || !r.ok) return false
  const tok = data?.redemption_token || data?.data?.redemption_token || ''
  if (tok) redemptionToken.value = tok
  applyResultPayload(data)
  if (!resultStatus.value) resultStatus.value = data?.status || data?.order?.status || 'pending'
  step.value = 3
  startPoll()
  return true
}

function invalidateVerification(includePreview: boolean) {
  flowVersion++
  preflightToken.value = ''
  clearAccount()
  error.value = ''
  if (includePreview) {
    redemptionToken.value = ''
    previewInfo.value = null
  }
}

function setCredentialMode(mode: 'session' | 'mailbox') {
  if (busy.value || credMode.value === mode) return
  credMode.value = mode
  invalidateVerification(false)
}

function clearCredentials() {
  if (busy.value) return
  sessionRaw.value = ''
  email.value = ''
  password.value = ''
  invalidateVerification(false)
}

async function doValidate() {
  if (busy.value || step.value !== 1) return
  error.value = ''
  errorField.value = 'code'
  if (!code.value.trim()) {
    error.value = t('rechargeHome.missingCode')
    codeInput.value?.focus()
    return
  }
  const version = ++flowVersion
  const cdk = code.value.trim()
  const signature = () => JSON.stringify([code.value.trim(), credMode.value, sessionRaw.value, email.value, password.value])
  const originalSignature = signature()
  const current = () => !disposed && version === flowVersion && signature() === originalSignature
  busy.value = true
  busyPhase.value = 'preview'
  previewInfo.value = null
  redemptionToken.value = ''
  preflightToken.value = ''
  clearAccount()
  try {
    const { r, data } = await api('/api/v1/public/cdk/preview', {
      method: 'POST',
      body: JSON.stringify({ code: cdk }),
    })
    if (!current()) return
    if (!r.ok) {
      const msg = data?.error || data?.msg || data?.message || t('rechargeHome.invalidCode')
      if (/已兑换|已使用|used|redeemed|consumed|已消耗/i.test(String(msg))) {
        if (await tryResumeByCode(cdk, version)) return
        if (!current()) return
      }
      error.value = msg
      return
    }
    redemptionToken.value = data?.redemption_token || data?.data?.redemption_token || data?.token || ''
    previewInfo.value = data?.data || data
    if (!redemptionToken.value) {
      error.value = t('rechargeHome.missingRedemption')
      return
    }
    errorField.value = 'credential'
    let credential: { mode: 'session'; session: string } | { mode: 'mailbox'; email: string; password: string }
    if (credMode.value === 'session') {
      const session = extractSession(sessionRaw.value)
      if (!session) {
        error.value = t('rechargeHome.invalidSession')
        return
      }
      credential = { mode: 'session', session }
    } else {
      if (!email.value.trim() || !password.value) {
        error.value = t('rechargeHome.missingMailbox')
        return
      }
      credential = { mode: 'mailbox', email: email.value.trim(), password: password.value }
    }
    busyPhase.value = 'preflight'
    const response = await api('/api/v1/public/cdk/preflight', {
      method: 'POST',
      body: JSON.stringify({ code: cdk, redemption_token: redemptionToken.value, credential }),
    })
    if (!current()) return
    const payload = response.data
    if (!response.r.ok || (payload && typeof payload.code === 'number' && payload.code !== 0)) {
      error.value = payload?.error || payload?.msg || payload?.message || t('rechargeHome.preflightFailed')
      return
    }
    const body = payload?.data && typeof payload.data === 'object' ? payload.data : payload || {}
    preflightToken.value = body.preflight_token || payload?.preflight_token || ''
    if (!preflightToken.value) {
      error.value = t('rechargeHome.missingPreflight')
      return
    }
    applyAccountFromPreflight(payload)
    step.value = 2
  } catch {
    if (current()) {
      errorField.value = 'general'
      error.value = t('rechargeHome.networkError')
    }
  } finally {
    if (!disposed) busy.value = false
  }
}

async function doRedeem() {
  if (busy.value || step.value !== 2 || alreadySatisfied.value || !redemptionToken.value || !preflightToken.value) return
  error.value = ''
  busy.value = true
  const version = ++flowVersion
  // Persist a result-screen checkpoint before dispatch, including uncertain network outcomes.
  step.value = 3
  resultStatus.value = 'pending'
  resultMessage.value = ''
  saveProgress()
  try {
    const client_request_id = 'web-' + deviceId.slice(0, 8) + '-' + Date.now()
    const { r, data } = await api('/api/v1/public/cdk/redeem', {
      method: 'POST',
      body: JSON.stringify({
        redemption_token: redemptionToken.value,
        preflight_token: preflightToken.value,
        client_request_id,
      }),
    })
    if (disposed || version !== flowVersion) return
    applyResultPayload(data)
    if (!r.ok && r.status !== 202) {
      error.value = data?.error || data?.msg || data?.message || '兑换被拒绝'
    }
    // Only explicit validation/authentication rejection may return to revalidation.
    // Never retry automatically; transport errors, 5xx and order evidence stay here.
    const legacyRejection = r.status === 400 && typeof data?.error === 'string' && data.error
    const authRejection = [401, 403].includes(r.status) && (
      (typeof data?.error === 'string' && data.error) ||
      (data?.code === r.status && typeof data?.msg === 'string' && data.msg)
    )
    if ((legacyRejection || authRejection) &&
      !data?.order && !data?.data?.order && !resultStatus.value &&
      !data?.order_id && !data?.data?.order_id && !data?.id && !data?.data?.id) {
      preflightToken.value = ''
      clearAccount()
      errorField.value = 'general'
      step.value = 1
      saveProgress()
      return
    }
    if (!resultStatus.value) resultStatus.value = r.ok || r.status === 202 ? 'queued' : 'error'
  } catch {
    if (!disposed && version === flowVersion) resultMessage.value = t('rechargeHome.networkUnknown')
  } finally {
    if (!disposed && version === flowVersion) {
      busy.value = false
      if (step.value === 3) startPoll()
    }
  }
}

function startPoll() {
  const version = ++pollVersion
  if (pollTimer) clearInterval(pollTimer)
  if (!redemptionToken.value && !code.value.trim()) {
    polling.value = false
    return
  }
  polling.value = true
  const tick = async () => {
    try {
      let r: Response
      let data: any
      if (redemptionToken.value) {
        ;({ r, data } = await api(
          '/api/v1/public/cdk/result?token=' + encodeURIComponent(redemptionToken.value),
        ))
      } else {
        ;({ r, data } = await api(
          '/api/v1/public/cdk/result-by-code?code=' + encodeURIComponent(code.value.trim()),
        ))
        if (!disposed && version === pollVersion && r.ok && data?.redemption_token) {
          redemptionToken.value = data.redemption_token
        }
      }
      if (disposed || version !== pollVersion || step.value !== 3) return
      if (r.ok) {
        applyResultPayload(data)
        saveProgress()
        if (isTerminal(resultStatus.value)) {
          polling.value = false
          if (pollTimer) clearInterval(pollTimer)
        }
      }
    } catch {
      /* ignore transient network */
    }
  }
  tick()
  pollTimer = setInterval(tick, 3000)
}

onMounted(() => {
  nowTimer = setInterval(() => {
    nowTick.value = Date.now()
  }, 30000)
  const q = String(route.query.cdk || route.query.code || '').trim()
  if (loadProgress()) {
    if (q && code.value.trim() !== q) {
      resetAll()
      code.value = q
    } else if (step.value === 3 && (redemptionToken.value || code.value)) {
      startPoll()
    }
  } else if (q) {
    code.value = q
  }
})

function resetAll() {
  flowVersion++
  pollVersion++
  busy.value = false
  if (pollTimer) clearInterval(pollTimer)
  clearProgress()
  sessionRaw.value = ''
  email.value = ''
  password.value = ''
  step.value = 1
  error.value = ''
  code.value = ''
  previewInfo.value = null
  redemptionToken.value = ''
  preflightToken.value = ''
  clearAccount()
  resultBody.value = null
  resultStatus.value = ''
  resultStage.value = ''
  resultMessage.value = ''
  resultEmail.value = ''
  resultCardLastFour.value = ''
  timeline.value = []
  polling.value = false
}
</script>

<style scoped>
.recharge-home { min-height:100vh; display:flex; flex-direction:column; background:var(--bg); color:var(--ink); }
.recharge-header { background:var(--surface); border-bottom:1px solid var(--brd); }
.recharge-header-inner { max-width:1280px; min-height:76px; margin:auto; padding:16px 32px; display:flex; justify-content:space-between; align-items:center; gap:20px; }
.recharge-brand { display:flex; align-items:center; gap:14px; min-width:0; color:var(--ink); font-size:20px; font-weight:650; text-decoration:none; }
.recharge-brand > svg { width:34px; height:34px; flex-shrink:0; color:var(--primary); }
.recharge-brand > span { overflow-wrap:anywhere; }
.recharge-tools { display:flex; align-items:center; gap:8px; flex-shrink:0; }
.recharge-main { width:100%; max-width:1184px; margin:0 auto; padding:36px 32px 32px; flex:1; }
.recharge-intro { display:flex; justify-content:space-between; align-items:flex-start; gap:24px; margin-bottom:36px; }
.recharge-intro h1 { font-size:30px; font-weight:650; line-height:1.3; margin:0 0 10px; }
.recharge-intro p { font-size:15px; color:var(--ink-2); margin:0; }
.recharge-shortcuts { display:flex; flex-wrap:wrap; gap:10px; padding-top:2px; flex-shrink:0; }
.recharge-shortcuts a { display:inline-flex; align-items:center; justify-content:center; gap:9px; min-height:44px; padding:9px 14px; border:1px solid var(--brd-2); border-radius:5px; background:var(--surface); color:var(--ink-2); font-size:14px; white-space:nowrap; transition:color .15s,border-color .15s; }
.recharge-shortcuts a:hover { border-color:var(--primary); color:var(--primary); }
.recharge-shortcuts svg { width:18px; height:18px; }
.recharge-workspace { max-width:840px; margin:0 auto; }
.recharge-steps { display:flex; list-style:none; align-items:center; justify-content:center; margin:0 auto 24px; padding:0 30px; }
.recharge-steps li { display:flex; align-items:center; gap:10px; color:var(--ink-3); font-size:14px; font-weight:500; flex:1; white-space:nowrap; }
.recharge-steps li:not(:last-child)::after { content:''; height:1px; background:var(--brd-2); flex:1; margin:0 22px 0 12px; }
.recharge-steps li:last-child { flex:0 0 auto; }
.step-number { display:grid; place-items:center; width:32px; height:32px; border-radius:50%; background:var(--surface-3,var(--brd)); color:var(--ink-2); font-size:15px; font-weight:650; flex-shrink:0; }
.recharge-steps .current { color:var(--primary); }
.current .step-number { background:var(--primary); color:var(--primary-on); }
.passed .step-number { background:var(--primary-soft); color:var(--primary); }
.recharge-panel { padding:28px 32px; background:var(--surface); border:1px solid var(--brd); border-radius:8px; }
.recharge-form { display:flex; flex-direction:column; gap:24px; }
.recharge-field { min-width:0; }
.recharge-field label { display:block; margin:0 0 10px; font-size:16px; font-weight:600; color:var(--ink); }
.recharge-field .input { width:100%; min-height:48px; padding:12px 14px; font-family:var(--font-sans); font-size:16px; line-height:1.5; border:1px solid var(--brd-2); border-radius:6px; background:var(--surface); color:var(--ink); box-shadow:none; }
.recharge-field .input::placeholder { color:var(--ink-3); opacity:1; }
.recharge-field .input[aria-invalid=true] { border-color:var(--err); }
.recharge-field .input:disabled { cursor:wait; opacity:.7; }
.field-hint { margin:7px 0 0; color:var(--ink-3); font-size:13px; line-height:1.6; }
.field-error { margin:8px 0 0; color:var(--err); font-size:14px; overflow-wrap:anywhere; }
.code-preview { margin:8px 0 0; display:flex; flex-wrap:wrap; gap:6px 18px; font-size:13px; color:var(--ink-2); }
.code-preview > span:last-child { color:var(--good); }
.credential-heading { display:flex; align-items:center; justify-content:space-between; gap:16px; margin-bottom:12px; }
.credential-heading label { margin:0; }
.credential-switch { display:flex; border:1px solid var(--brd-2); border-radius:5px; overflow:hidden; }
.credential-switch button { min-width:94px; min-height:40px; padding:7px 14px; background:var(--surface); color:var(--ink-2); font-size:14px; border:0; }
.credential-switch button + button { border-left:1px solid var(--brd); }
.credential-switch button[aria-pressed=true] { color:var(--primary); background:var(--primary-soft); font-weight:600; }
.recharge-field .session-input { display:block; height:160px; min-height:132px; resize:vertical; }
.mailbox-fields { display:grid; gap:12px; }
.credential-actions { display:flex; justify-content:space-between; flex-wrap:wrap; gap:4px 12px; margin-top:4px; }
.text-action { padding:8px 0; min-height:40px; background:transparent; border:0; font-size:13px; color:var(--primary); text-align:left; }
.text-action:hover { text-decoration:underline; text-underline-offset:3px; }
.muted-action { color:var(--ink-2); }
.credential-help { margin-top:4px; padding:14px 16px; background:var(--surface-2); border-radius:5px; color:var(--ink-2); font-size:13px; line-height:1.7; }
.credential-help p { margin:0 0 6px; }
.credential-privacy { display:flex; align-items:flex-start; gap:9px; margin:-12px 0 0; color:var(--ink-2); font-size:13px; line-height:1.7; }
.credential-privacy svg { width:18px; height:18px; margin-top:2px; flex-shrink:0; }
.recharge-submit { display:flex; align-items:center; justify-content:center; gap:12px; min-height:48px; width:100%; border-radius:5px; font-size:16px; font-weight:500; }
.recharge-submit svg { width:18px; height:18px; }
.recharge-help-footer { display:flex; align-items:center; justify-content:center; flex-wrap:wrap; gap:0 8px; margin-top:12px; color:var(--ink-3); font-size:13px; }
.recharge-footer { display:flex; justify-content:space-between; gap:20px; padding:18px max(32px,calc((100vw - 1216px)/2)); border-top:1px solid var(--brd); color:var(--ink-3); font-size:12px; background:var(--surface); }
.confirmation-summary { display:grid; grid-template-columns:1fr 1fr; gap:20px; margin:16px 0; }
.confirmation-summary dt { font-size:13px; color:var(--ink-2); }
.confirmation-summary dd { margin:4px 0 0; font-size:22px; font-weight:600; overflow-wrap:anywhere; }
.subscription-details summary { padding:8px 0; color:var(--ink-2); font-size:13px; }
.subscription-details .account-facts { margin-top:12px; }
.preview-notice { padding:0 0 12px; margin:0; color:var(--ink-3); font-size:12px; }
@media(max-width:1000px) {
  .recharge-intro { flex-direction:column; gap:20px; margin-bottom:28px; }
}
@media(max-width:640px) {
  .recharge-header-inner { min-height:64px; padding:12px 16px; gap:10px; }
  .recharge-brand { font-size:15px; gap:8px; }
  .recharge-brand > svg { width:28px; height:28px; }
  .recharge-tools { gap:0; }
  .recharge-main { padding:24px 16px; }
  .recharge-intro h1 { font-size:26px; }
  .recharge-intro p { font-size:14px; }
  .recharge-shortcuts { width:100%; gap:8px; }
  .recharge-shortcuts a { padding:8px 10px; font-size:13px; flex:1; gap:6px; }
  .recharge-steps { padding:0; margin-bottom:20px; }
  .recharge-steps li { font-size:12px; gap:6px; }
  .recharge-steps li:not(:last-child)::after { margin:0 8px 0 2px; }
  .step-number { width:26px; height:26px; font-size:13px; }
  .recharge-panel { padding:22px 20px; }
  .credential-heading { flex-wrap:wrap; gap:10px; }
  .credential-switch button { min-width:72px; min-height:44px; padding:7px 10px; font-size:13px; }
  .text-action { min-height:44px; }
  .recharge-footer { padding:16px; flex-wrap:wrap; gap:8px; }
}
.text-good { color: var(--good, #16a34a); }
.text-warn { color: var(--warn, #d97706); }
.border-primary { border-color: var(--primary) !important; }
.bg-primary\/10 { background: color-mix(in srgb, var(--primary) 12%, transparent); }
.border-brd { border-color: var(--brd); }
.account-facts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 16px;
  margin: 0;
}
.account-facts > div {
  min-width: 0;
}
.account-facts dt {
  margin: 0;
  font-size: 12px;
  color: var(--muted, #6b7280);
}
.account-facts dd {
  margin: 2px 0 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--ink, #111827);
  word-break: break-all;
}
@media (max-width: 640px) {
  .account-facts { grid-template-columns: 1fr; }
}
</style>
