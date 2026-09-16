<template>
  <div class="app-shell" :class="[`layout-${layout}`, `nav-${nav}`]">
    <aside v-if="layout !== 'top'" class="sidenav">
      <router-link to="/ops" class="side-brand" :title="brand.name || '运营控制台'">
        <span class="brand-icon" aria-hidden="true"><el-icon><Tickets /></el-icon></span>
        <span class="brand-text">{{ brand.name || '运营控制台' }}</span>
      </router-link>
      <div class="nav-caption">工作空间</div>
      <nav class="side-pills" aria-label="运营导航">
        <router-link v-for="it in navItems" :key="it.path" :to="it.path"
          class="side-link" :class="{ active: isActive(it.path) }" :title="it.label"
          :aria-label="it.label" :aria-current="isActive(it.path) ? 'page' : undefined">
          <el-icon aria-hidden="true"><component :is="it.icon" /></el-icon>
          <span class="side-label">{{ it.label }}</span>
        </router-link>
      </nav>
      <div class="side-foot">
        <el-popover placement="right-end" :width="340" trigger="click">
          <template #reference>
            <button type="button" class="side-tool" aria-label="整站主题" title="整站主题">
              <el-icon aria-hidden="true"><Brush /></el-icon><span class="side-label">整站主题</span>
            </button>
          </template>
          <SkinPicker show-mode title="整站主题" />
        </el-popover>
        <div class="side-account">
          <span class="account-avatar" aria-hidden="true"><el-icon><User /></el-icon></span>
          <span class="admin-name">{{ auth.username || 'admin' }}</span>
          <button type="button" class="logout-button" @click="doLogout" aria-label="退出登录" title="退出登录">
            <el-icon aria-hidden="true"><SwitchButton /></el-icon>
          </button>
        </div>
      </div>
    </aside>

    <div class="main-col">
      <header v-if="layout === 'top'" class="topnav">
        <div class="nav-inner">
          <router-link to="/ops" class="brand">
            <span class="brand-icon" aria-hidden="true"><el-icon><Tickets /></el-icon></span>
            <span class="brand-text">{{ brand.name || '运营控制台' }}</span>
          </router-link>
          <nav class="nav-pills" aria-label="运营导航">
            <router-link v-for="it in navItems" :key="it.path" :to="it.path" class="pill"
              :class="{ active: isActive(it.path) }" :aria-current="isActive(it.path) ? 'page' : undefined">
              <el-icon aria-hidden="true"><component :is="it.icon" /></el-icon><span>{{ it.label }}</span>
            </router-link>
          </nav>
          <div class="nav-actions">
            <el-popover placement="bottom-end" :width="340" trigger="click">
              <template #reference>
                <button type="button" class="hicon" aria-label="整站主题"><el-icon><Brush /></el-icon></button>
              </template>
              <SkinPicker show-mode title="整站主题" />
            </el-popover>
            <span class="admin-name">{{ auth.username || 'admin' }}</span>
            <el-button size="small" @click="doLogout">退出</el-button>
          </div>
        </div>
      </header>
      <header v-else class="subtop">
        <div class="subtop-inner">
          <div class="breadcrumb"><span>运营后台</span><span aria-hidden="true">/</span><strong>{{ currentTitle }}</strong></div>
          <router-link to="/" class="portal-link">访问用户门户 <el-icon aria-hidden="true"><TopRight /></el-icon></router-link>
        </div>
      </header>
      <main class="page"><router-view /></main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { serverLogout } from '../lib/api'
import { siteBrand, currentSkinMeta } from '../theme'
import SkinPicker from '../components/SkinPicker.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const brand = siteBrand

const layout = computed(() => currentSkinMeta.value.layout)
const nav = computed(() => currentSkinMeta.value.nav)

const navItems = [
  { path: '/ops', label: '总览', icon: 'Odometer' },
  { path: '/ops/cdkeys', label: 'CDK卡密', icon: 'Key' },
  { path: '/ops/orders', label: '兑换对账', icon: 'Document' },
  { path: '/ops/integration', label: '卡台接入', icon: 'Link' },
  { path: '/ops/card-selection', label: '选卡配置', icon: 'CreditCard' },
  { path: '/ops/webhooks', label: 'Webhook', icon: 'Bell' },
  { path: '/ops/appearance', label: '外观', icon: 'Brush' },
  { path: '/ops/audit', label: '审计', icon: 'List' },
]

const currentTitle = computed(() => {
  const hit = navItems.find((n) => isActive(n.path))
  return hit?.label || brand.value.name || '控制台'
})

function isActive(p: string) {
  return p === '/ops' ? route.path === '/ops' : route.path.startsWith(p)
}
async function doLogout() {
  await serverLogout()
  router.push('/ops/login')
}
</script>

<style scoped>
.app-shell { display:flex; min-height:100vh; background:var(--bg); color:var(--ink); }
.layout-top { flex-direction:column; }
.main-col { flex:1; min-width:0; display:flex; flex-direction:column; }
.sidenav { width:224px; flex-shrink:0; display:flex; flex-direction:column; padding:0 12px; background:var(--surface); border-right:1px solid var(--brd); position:sticky; top:0; height:100dvh; z-index:40; }
.side-brand,.brand { display:flex; align-items:center; gap:10px; min-height:64px; color:var(--ink); text-decoration:none; padding:0 8px; }
.brand-icon { display:grid; place-items:center; width:30px; height:30px; border-radius:6px; background:var(--primary); color:var(--primary-on); flex-shrink:0; font-size:19px; }
.brand-text { font-family:var(--font-sans); font-size:14px; font-weight:650; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.nav-caption { padding:22px 12px 10px; font-size:12px; color:var(--ink-3); }
.side-pills { flex:1; min-height:0; overflow:auto; display:flex; flex-direction:column; gap:4px; }
.side-link { display:flex; align-items:center; gap:12px; padding:11px 12px; min-height:42px; border-radius:6px; font-size:14px; color:var(--ink-2); text-decoration:none; border:1px solid transparent; transition:background .15s,color .15s; }
.side-link .el-icon,.side-tool .el-icon { font-size:18px; flex-shrink:0; }
.side-link:hover,.side-tool:hover { background:var(--surface-2); color:var(--ink); }
.side-link.active { background:var(--primary-soft); color:var(--primary); font-weight:600; }
.side-link:nth-child(7) { margin-top:18px; }
.side-label { white-space:nowrap; }
.side-foot { padding:12px 0; border-top:1px solid var(--brd); margin-top:16px; }
.side-tool { display:flex; align-items:center; gap:12px; min-height:42px; width:100%; padding:10px 12px; border-radius:6px; color:var(--ink-2); font-size:14px; }
.side-account { display:flex; align-items:center; gap:10px; padding:12px 8px 0; }
.account-avatar { display:grid; place-items:center; width:30px; height:30px; border:1px solid var(--brd); border-radius:50%; background:var(--surface-2); color:var(--ink-2); flex-shrink:0; }
.admin-name { color:var(--ink-2); font-size:13px; overflow:hidden; text-overflow:ellipsis; }
.logout-button,.hicon { display:grid; place-items:center; min-width:36px; min-height:36px; border-radius:6px; color:var(--ink-2); margin-left:auto; }
.logout-button:hover,.hicon:hover { background:var(--surface-2); color:var(--ink); }
.subtop,.topnav { background:var(--surface); border-bottom:1px solid var(--brd); }
.subtop-inner { min-height:64px; padding:0 32px; display:flex; align-items:center; justify-content:space-between; gap:16px; }
.breadcrumb { display:flex; gap:14px; align-items:center; font-size:13px; color:var(--ink-3); }
.breadcrumb strong { color:var(--ink); font-weight:500; }
.portal-link { display:inline-flex; align-items:center; gap:6px; color:var(--ink-2); font-size:13px; }
.portal-link:hover { color:var(--primary); }
.page { width:100%; max-width:1500px; margin:0 auto; padding:28px 32px 48px; min-height:0; flex:1; }
.nav-inner { display:flex; flex-wrap:wrap; align-items:center; gap:12px; padding:0 24px; }
.nav-pills { display:flex; flex:1; gap:2px; flex-wrap:wrap; }
.pill { display:inline-flex; align-items:center; gap:6px; padding:10px; border:none; border-radius:6px; background:transparent; font-size:13px; color:var(--ink-2); }
.pill.active { background:var(--primary-soft); color:var(--primary); }
.nav-actions { display:flex; align-items:center; gap:10px; }
.layout-rail .sidenav { width:68px; padding:0 8px; }
.layout-rail .brand-text,.layout-rail .side-label,.layout-rail .nav-caption,.layout-rail .account-avatar,.layout-rail .side-account .admin-name { display:none; }
.layout-rail .side-pills { padding-top:20px; }
.layout-rail .side-link,.layout-rail .side-tool,.layout-rail .side-brand,.layout-rail .side-account { justify-content:center; padding-left:0; padding-right:0; }
.layout-rail .logout-button { margin:0; }
@media(max-width:900px) {
  .sidenav { width:68px; padding:0 8px; }
  .brand-text,.side-label,.nav-caption,.account-avatar,.side-account .admin-name { display:none; }
  .side-pills { padding-top:20px; }
  .side-link,.side-tool,.side-brand,.side-account { justify-content:center; padding-left:0; padding-right:0; }
  .logout-button { margin:0; min-width:44px; min-height:44px; }
  .page { padding:24px 20px; }
  .subtop-inner { padding:0 20px; }
  .nav-inner { padding:8px 16px; }
  .nav-pills { order:3; flex-basis:100%; flex-wrap:nowrap; overflow-x:auto; }
  .nav-pills .pill { flex-shrink:0; }
  .nav-actions { margin-left:auto; }
}
@media(max-width:520px) {
  .page { padding:18px 12px 32px; }
  .subtop-inner { min-height:56px; padding:0 12px; }
  .breadcrumb { gap:7px; font-size:12px; }
  .portal-link { font-size:12px; }
  .sidenav { width:54px; padding:0 5px; }
  .side-brand { min-height:56px; }
  .side-link { min-height:44px; }
}
</style>
