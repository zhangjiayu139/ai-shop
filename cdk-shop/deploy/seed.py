"""Configure the new shop through authenticated API. No payment/redeem actions."""
import json, os, re, secrets, subprocess, urllib.request, urllib.error
from pathlib import Path
os.umask(0o077)
root=Path('/opt/taoai-shop')
ip=json.loads(subprocess.check_output(['docker','inspect','taoai-shop-app']))[0]['NetworkSettings']['Networks']['taoai_shop_front']['IPAddress']
base='http://'+ip+':8080/api/v1'
access=json.loads((root/'admin-access.json').read_text())
token=''
def api(method,path,data=None,raw=None,ctype=None):
    headers={'Accept':'application/json','Accept-Language':'zh-CN'}
    if token:headers['Authorization']='Bearer '+token
    if data is not None:
        raw=json.dumps(data,ensure_ascii=False).encode();ctype='application/json'
    if ctype:headers['Content-Type']=ctype
    req=urllib.request.Request(base+path,data=raw,headers=headers,method=method)
    try:
        with urllib.request.urlopen(req,timeout=30) as r:result=json.load(r)
    except urllib.error.HTTPError as e:
        detail=e.read().decode()[:1000]
        raise RuntimeError(f'{method} {path} HTTP {e.code}: {detail}') from None
    if result.get('status_code', result.get('code')) not in (None,0,200):raise RuntimeError(f'{path}: {result}')
    return result.get('data')
login=api('POST','/admin/login',{'username':access['username'],'password':access['password']})
assert not login.get('requires_totp')
token=login['token']
def loc(s):return {k:s for k in ('zh-CN','zh-TW','en-US')}
policy='GPT官充产品售后质保同步官方，如果出现封号，需自行申诉，官方退款，我们同步退款，收取官方实际退款金额的20%作为手续费。'
site={
 'brand':{'site_name':'TaoAi','site_url':'https://shop.edujerry.icu','site_description':loc('AI 订阅与数字卡密 · 客服微信 lc07130922')},
 'currency':'CNY','languages':['zh-CN'],'template_mode':'default','storefront_template':'default',
 'seo':{'title':loc('TaoAi · AI 订阅与数字卡密'),'description':loc('ChatGPT Plus 一个月，¥139。兑换地址 cdk.edujerry.icu，客服微信 lc07130922。'),'keywords':loc('TaoAi,ChatGPT Plus,CDK')},
 'about':{'hero':{'title':loc('关于 TaoAi'),'subtitle':loc('AI 订阅与数字卡密')},'introduction':loc('购买后凭 CDK 前往 https://cdk.edujerry.icu 兑换。当前正在准备正式库存，暂未开放购买。'),'contact':{'title':loc('客服与售后'),'text':loc('客服：+v : lc07130922\n\n'+policy)}},
 'legal':{'terms':loc('售后规则\n\n'+policy),'privacy':loc('咨询、订单及售后信息仅用于店铺服务。请勿在客服消息中发送账号密码。客服微信：lc07130922。')},
 'footer_links':[{'name':'CDK 自助兑换','url':'https://cdk.edujerry.icu'},{'name':'客服微信：lc07130922','url':'/about'}],
 'scripts':[{'name':'TaoAi 商品主图完整显示','enabled':True,'position':'head','code':'<style>img[alt="ChatGPT Plus · 1个月"]{object-fit:contain!important}.product-detail-page img[alt="ChatGPT Plus · 1个月"]{aspect-ratio:1/1!important}</style>'}]}
api('PUT','/admin/settings',{'key':'site_config','value':site})
api('PUT','/admin/settings',{'key':'registration_config','value':{'registration_enabled':False,'email_verification_enabled':True,'email_domain_allowlist_enabled':False,'allowed_email_domains':[]}})
api('PUT','/admin/settings',{'key':'home_announcement','value':{'enabled':True,'type':'info','title':loc('TaoAi 开店准备中'),'content':loc('<p>ChatGPT Plus · 1个月，售价 <strong>¥139</strong>。正式库存准备中，暂未开放购买。客服：<strong>+v : lc07130922</strong>。</p>'),'start_at':'','end_at':''}})
state_path=root/'deploy/seed-state.json'
state=json.loads(state_path.read_text()) if state_path.exists() else {}
def save():state_path.write_text(json.dumps(state,ensure_ascii=False,indent=2))
if 'image_url' not in state:
    boundary='TaoAi'+secrets.token_hex(16)
    raw=(f'--{boundary}\r\nContent-Disposition: form-data; name="scene"\r\n\r\ncommon\r\n--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="taoai-chatgpt-plus.png"\r\nContent-Type: image/png\r\n\r\n'.encode()+(root/'assets/chatgpt-plus-139.png').read_bytes()+f'\r\n--{boundary}--\r\n'.encode())
    state['image_url']=api('POST','/admin/upload',raw=raw,ctype='multipart/form-data; boundary='+boundary)['url'];save()
cats=api('GET','/admin/categories')
if isinstance(cats,dict):cats=cats.get('items',cats.get('list',[]))
def category(slug,name,active):
    found=next((c for c in cats if c['slug']==slug),None)
    if not found:found=api('POST','/admin/categories',{'slug':slug,'name':loc(name),'sort_order':10 if active else 999})
    api('PATCH',f'/admin/categories/{found["id"]}/active',{'is_active':active})
    return found['id']
main_cat=category('ai-subscriptions','AI 订阅',True)
test_cat=category('internal-invalid-tests','内部测试（不可兑换）',False)
description=(root/'products/chatgpt-plus/description.html').read_text()+'<p><strong>正式库存准备中，暂未开放购买。请联系店铺客服了解补货情况。</strong></p>'
assert description.count(policy)==3
def product(test):
    key='test_product' if test else 'main_product'
    if key in state:return state[key]
    payload={'category_id':test_cat if test else main_cat,'slug':'internal-invalid-chatgpt-plus-test' if test else 'chatgpt-plus-1-month','title':loc('内部测试 · 无效 CDK（禁止销售）' if test else 'ChatGPT Plus · 1个月'),'description':loc('仅供后台测试，无法兑换订阅，禁止对外售卖。' if test else '一个月订阅 · CDK 自助兑换 · 售后规则请先阅读商品详情'),'content':loc('测试卡密无效，无法激活订阅。禁止销售。' if test else description),'instructions':loc('前往 https://cdk.edujerry.icu 输入卡密，按页面提示兑换。客服：+v : lc07130922'),'price_amount':139,'images':[state['image_url']],'tags':['内部测试'] if test else ['ChatGPT Plus','1个月','CDK'],'purchase_type':'guest','min_purchase_quantity':1,'max_purchase_quantity':1,'stock_display_mode':'exact','fulfillment_type':'auto','is_active':not test,'is_affiliate_enabled':False,'sort_order':999 if test else 1,'payment_channel_ids':[],'skus':[{'sku_code':'INVALID-TEST-PLUS1M' if test else 'PLUS-1MONTH','spec_values':{},'price_amount':139,'is_active':True,'sort_order':1}]}
    result=api('POST','/admin/products',payload)
    state[key]={'id':result['id'],'slug':payload['slug']};save()
    return state[key]
main=product(False);test=product(True)
if not state.get('test_batch_imported'):
    codes=(root/'testing/chatgpt-plus-test-cdks.txt').read_text().splitlines()
    assert len(codes)==10 and len(set(codes))==10 and all(c.startswith('TAOAI-TEST-INVALID-') for c in codes)
    d=api('GET',f'/admin/products/{test["id"]}')
    api('POST','/admin/card-secrets/batch',{'product_id':test['id'],'sku_id':d['skus'][0]['id'],'name':'无效测试卡密-禁止销售','secrets':codes,'batch_no':'TAOAI-INVALID-TEST-20260914','note':'没有在兑换站注册，无法兑换任何订阅，仅用于隔离测试','deduplicate':True})
    state['test_batch_imported']=True;save()
public=api('GET','/public/products/'+main['slug'])
assert float(public['price_amount'])==139
assert public['content']['zh-CN'].count(policy)==3
state['main_url']='https://shop.edujerry.icu/products/'+main['slug'];save()
print('Store settings, image, public zero-stock product, hidden invalid test inventory configured.')
print('Product URL:',state['main_url'])
print('Public product keys:',', '.join(public.keys()))
