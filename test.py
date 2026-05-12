import sys
sys.stdout.reconfigure(encoding='utf-8')

import os
import re
import json
import hmac
import hashlib
import base64
import time
import requests

from dotenv import load_dotenv
from google import genai

load_dotenv()

STORE         = 'girnardarshan-com.myshopify.com'
PRODUCT_TITLE = 'Neminath Bhagwan LED Photo Frame | 12×17 Inch | Silver Border'
SERVER_URL    = os.getenv('SERVER_URL', 'http://localhost:3000')
_TOKEN_SECRET = os.getenv('REGISTER_SECRET', 'girnar2026')

gemini = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

def create_signed_token(data):
    payload = base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip('=')
    sig = hmac.new(_TOKEN_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"

def fetch_product():
    res = requests.get(
        f'https://{STORE}/admin/api/2024-01/products.json',
        params={'title': PRODUCT_TITLE, 'limit': 5},
        headers={'X-Shopify-Access-Token': os.getenv('SHOPIFY_ACCESS_TOKEN')}
    )
    products = res.json().get('products', [])
    product  = next((p for p in products if 'neminath' in p['title'].lower() or 'led' in p['title'].lower()), None)
    if not product:
        raise Exception(f'Product not found: "{PRODUCT_TITLE}"')
    return product

def generate_facebook_post(product):
    desc = re.sub(r'<[^>]+>', '', product.get('body_html', '') or '').strip() or 'Premium quality product'
    variants  = product.get('variants') or [{}]
    price     = variants[0].get('price', '')
    price_str = f"₹{price}" if price else ''

    prompt = f"""You are a creative social media manager for Girnar Darshan, an Indian e-commerce store.

Write an engaging Facebook post for this new product:

Product: {product['title']}
{f'Price: {price_str}' if price_str else ''}
Description: {desc[:600]}
Link: https://girnardarshan-com.myshopify.com/products/{product.get('handle', '')}

Requirements:
- Start with a strong hook that grabs attention
- Use emojis naturally (not excessive)
- Highlight 2-3 key benefits from the description
- {f'Mention the price {price_str} as a value highlight' if price_str else ''}
- Include a clear call-to-action (Shop now, Order today, etc.)
- Include the product link
- End with 4-6 relevant hashtags
- Keep it under 280 words
- Tone: warm, enthusiastic, trustworthy

Write only the post text, nothing else."""

    response = gemini.models.generate_content(model='gemini-2.5-flash', contents=prompt)
    return response.text.strip()

def build_amp_email(title, price_str, image_url, post_content, token):
    approve_url = f"{SERVER_URL}/approve-amp"
    safe_post   = post_content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    image_block = ''
    if image_url:
        image_block = f'''
      <div style="line-height:0;">
        <amp-img src="{image_url}" width="600" height="300" layout="responsive" alt="{title}"></amp-img>
      </div>'''

    price_block = f'<p style="margin:0 0 4px;font-size:20px;color:#1877f2;font-weight:700;">{price_str}</p>' if price_str else ''

    return f'''<!doctype html>
<html ⚡4email data-css-strict>
<head>
  <meta charset="utf-8">
  <script async src="https://cdn.ampproject.org/v0.js"></script>
  <script async custom-element="amp-form" src="https://cdn.ampproject.org/v0/amp-form-0.1.js"></script>
  <script async custom-template="amp-mustache" src="https://cdn.ampproject.org/v0/amp-mustache-0.2.js"></script>
  <style amp4email-boilerplate>body{{-webkit-animation:-amp-start 8s steps(1,end) 0s 1 normal both;-moz-animation:-amp-start 8s steps(1,end) 0s 1 normal both;-ms-animation:-amp-start 8s steps(1,end) 0s 1 normal both;animation:-amp-start 8s steps(1,end) 0s 1 normal both}}@-webkit-keyframes -amp-start{{from{{visibility:hidden}}to{{visibility:visible}}}}@-moz-keyframes -amp-start{{from{{visibility:hidden}}to{{visibility:visible}}}}@-ms-keyframes -amp-start{{from{{visibility:hidden}}to{{visibility:visible}}}}@keyframes -amp-start{{from{{visibility:hidden}}to{{visibility:visible}}}}</style>
  <style amp-custom>
    body {{ margin:0; padding:0; background:#f0f4f8; font-family:'Segoe UI',Helvetica,Arial,sans-serif; }}
    .wrap {{ max-width:600px; margin:24px auto; background:#fff; border-radius:16px; overflow:hidden; box-shadow:0 8px 32px rgba(0,0,0,0.12); }}
    .header {{ background:linear-gradient(135deg,#1877f2,#0a5ac7); padding:32px 40px; text-align:center; }}
    .header h1 {{ margin:0; color:#fff; font-size:24px; font-weight:700; }}
    .header p {{ margin:8px 0 0; color:rgba(255,255,255,0.85); font-size:14px; }}
    .body {{ padding:28px 36px; }}
    .product-name {{ font-size:20px; font-weight:700; color:#1a1a2e; margin:0 0 6px; }}
    .post-box {{ background:#f0f2f5; border-left:4px solid #1877f2; border-radius:8px; padding:20px; margin-bottom:24px; }}
    .post-label {{ display:inline-block; background:#1877f2; color:#fff; font-size:10px; font-weight:700; padding:3px 10px; border-radius:20px; text-transform:uppercase; letter-spacing:0.8px; margin-bottom:12px; }}
    .post-text {{ margin:0; color:#1c1e21; font-size:14px; line-height:1.75; white-space:pre-wrap; }}
    .btn {{ display:block; width:100%; background:linear-gradient(135deg,#42b72a,#2d9e1a); color:#fff; border:none; padding:18px; border-radius:50px; font-size:17px; font-weight:700; cursor:pointer; text-align:center; }}
    .success-box {{ background:#f0fff4; border:2px solid #42b72a; border-radius:12px; padding:24px; text-align:center; }}
    .success-title {{ font-size:20px; font-weight:700; color:#2d9e1a; margin:0 0 6px; }}
    .success-sub {{ font-size:14px; color:#555; margin:0; }}
    .error-box {{ background:#fff5f5; border:2px solid #e74c3c; border-radius:12px; padding:24px; text-align:center; }}
    .footer {{ background:#f8f9fa; padding:16px 36px; text-align:center; border-top:1px solid #e8ecef; }}
    .footer p {{ margin:0; color:#bbb; font-size:12px; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="header">
      <h1>📦 New Product Added!</h1>
      <p>Review and approve to publish on Facebook</p>
    </div>

    {image_block}

    <div class="body">
      <p class="product-name">{title}</p>
      {price_block}

      <div class="post-box">
        <span class="post-label">🤖 AI-Generated Facebook Post</span>
        <p class="post-text">{safe_post}</p>
      </div>

      <form method="post"
            action-xhr="{approve_url}"
            target="_top">
        <input type="hidden" name="token" value="{token}">

        <div submitting>
          <button class="btn" type="submit" disabled>Posting...</button>
        </div>

        <div submit-success>
          <template type="amp-mustache">
            <div class="success-box">
              <p class="success-title">✅ Posted to Facebook!</p>
              <p class="success-sub">{{{{message}}}}</p>
            </div>
          </template>
        </div>

        <div submit-error>
          <template type="amp-mustache">
            <div class="error-box">
              <p style="color:#e74c3c;font-weight:700;margin:0 0 6px;">❌ Error</p>
              <p style="margin:0;color:#555;font-size:14px;">{{{{message}}}}</p>
            </div>
          </template>
        </div>

        <button class="btn" type="submit">✅ &nbsp;Approve &amp; Post to Facebook</button>
      </form>
    </div>

    <div class="footer">
      <p>Girnar Darshan Automation &nbsp;•&nbsp; Powered by Gemini AI</p>
    </div>
  </div>
</body>
</html>'''

def build_fallback_html(title, price_str, image_url, post_content, token):
    approve_url = f"{SERVER_URL}/approve?token={token}"
    safe_post   = post_content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    image_block = f'<tr><td style="padding:0;line-height:0;"><img src="{image_url}" width="600" style="display:block;width:100%;max-height:320px;object-fit:cover;" /></td></tr>' if image_url else ''
    price_block = f'<p style="margin:0 0 4px;font-size:20px;color:#1877f2;font-weight:700;">{price_str}</p>' if price_str else ''

    return f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f0f4f8;font-family:'Segoe UI',Helvetica,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f4f8;padding:30px 15px;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 8px 32px rgba(0,0,0,.12);max-width:600px;width:100%;">
        <tr><td style="background:linear-gradient(135deg,#1877f2,#0a5ac7);padding:36px 40px;text-align:center;">
          <div style="font-size:40px;margin-bottom:12px;">📦</div>
          <h1 style="margin:0;color:#fff;font-size:26px;font-weight:700;">New Product Added!</h1>
          <p style="margin:10px 0 0;color:rgba(255,255,255,.85);font-size:15px;">Review and approve to publish on Facebook</p>
        </td></tr>
        {image_block}
        <tr><td style="padding:32px 40px 8px;">
          <h2 style="margin:0 0 8px;font-size:22px;color:#1a1a2e;font-weight:700;">{title}</h2>
          {price_block}
        </td></tr>
        <tr><td style="padding:16px 40px 28px;">
          <div style="background:#f0f2f5;border-radius:12px;padding:24px;border-left:4px solid #1877f2;">
            <span style="display:inline-block;background:#1877f2;color:#fff;font-size:11px;font-weight:700;padding:4px 12px;border-radius:20px;text-transform:uppercase;letter-spacing:.8px;margin-bottom:16px;">🤖 AI-Generated Facebook Post</span>
            <p style="margin:0;color:#1c1e21;line-height:1.8;font-size:15px;white-space:pre-wrap;">{safe_post}</p>
          </div>
        </td></tr>
        <tr><td style="padding:0 40px 32px;text-align:center;">
          <a href="{approve_url}" style="display:inline-block;background:linear-gradient(135deg,#42b72a,#2d9e1a);color:#fff;text-decoration:none;padding:18px 56px;border-radius:50px;font-size:18px;font-weight:700;">✅ &nbsp;Approve &amp; Post to Facebook</a>
        </td></tr>
        <tr><td style="background:#f8f9fa;padding:20px 40px;text-align:center;border-top:1px solid #e8ecef;">
          <p style="margin:0;color:#bbb;font-size:12px;">Girnar Darshan Automation &nbsp;•&nbsp; Powered by Gemini AI</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>'''

def send_approval_email(product, post_content, token, image_url):
    variants  = product.get('variants') or [{}]
    price     = variants[0].get('price', '')
    price_str = f"₹{price}" if price else ''

    amp_html = build_amp_email(product['title'], price_str, image_url, post_content, token)
    html     = build_fallback_html(product['title'], price_str, image_url, post_content, token)
    plain    = f"New product: {product['title']}\n\nPost:\n{post_content}\n\nApprove: {SERVER_URL}/approve?token={token}"

    payload = {
        'personalizations': [{'to': [{'email': 'aishwarya@valuecart.in', 'name': 'Aishwarya'}]}],
        'from': {'email': 'aryan@valuecart.in', 'name': 'Girnar Darshan'},
        'subject': f"New Product: {product['title']} — Approve Facebook Post",
        'content': [
            {'type': 'text/plain',      'value': plain},
            {'type': 'text/x-amp-html', 'value': amp_html},
            {'type': 'text/html',       'value': html},
        ]
    }

    res = requests.post(
        'https://api.sendgrid.com/v3/mail/send',
        json=payload,
        headers={
            'Authorization': f"Bearer {os.getenv('SENDGRID_API_KEY')}",
            'Content-Type': 'application/json',
        }
    )
    if res.status_code not in (200, 202):
        raise Exception(f"SendGrid error {res.status_code}: {res.text[:300]}")

def main():
    print('🧪 Test run — Girnar Darshan Automation\n')

    missing = [v for v in ['SERVER_URL', 'SENDGRID_API_KEY', 'SHOPIFY_ACCESS_TOKEN', 'GEMINI_API_KEY'] if not os.getenv(v)]
    if missing:
        print(f'❌ Missing .env vars: {", ".join(missing)}')
        return

    # 1. Fetch product
    print('📦 Fetching product from Shopify...')
    product   = fetch_product()
    images    = product.get('images') or []
    image_url = images[0].get('src') if images else None
    variants  = product.get('variants') or [{}]
    price     = variants[0].get('price', '')
    print(f"   Found: {product['title']}")
    print(f"   Price : {'₹' + price if price else '(no price)'}")
    print(f"   Image : {image_url or '(no image)'}")

    # 2. Generate post
    print('\n🤖 Generating Facebook post with Gemini...')
    post_content = generate_facebook_post(product)
    print(f'\n--- Generated Post ---\n{post_content}\n----------------------\n')

    # 3. Create signed token locally — no server storage needed
    entry = {
        'product': {
            'title':  product['title'],
            'handle': product.get('handle', ''),
            'price':  price,
        },
        'post_content': post_content,
        'image_url':    image_url,
        'expires_at':   time.time() + 48 * 3600,
    }
    token = create_signed_token(entry)

    # 4. Send email — use Railway poster URL so boss sees the actual poster
    poster_url = f"{SERVER_URL}/poster/{token}"
    print('📧 Sending AMP approval email to aishwarya@valuecart.in...')
    send_approval_email(product, post_content, token, poster_url)
    print('   Email sent!\n')

    approve_url = f"{SERVER_URL}/approve?token={token}"
    print(f'🔗 Fallback approve URL (also in the email):')
    print(f'   {approve_url}\n')
    print('Done. Aishwarya will see an Approve button directly in Gmail — no link to click.')

if __name__ == '__main__':
    main()
