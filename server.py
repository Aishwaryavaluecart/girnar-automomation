import sys
sys.stdout.reconfigure(encoding='utf-8')

import os
import json
import hmac
import hashlib
import base64
import time
import uuid
import threading
import requests
from flask import Flask, request
from dotenv import load_dotenv
from google import genai

load_dotenv()

app = Flask(__name__)
PENDING_FILE = 'pending.json'
EMAIL_MCP_URL = 'https://valuecart-email-mcp-production.up.railway.app/mcp/valuecart2026'
STORE = 'girnardarshan-com.myshopify.com'

gemini = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

# --- Storage ---

def get_pending():
    if not os.path.exists(PENDING_FILE):
        return {}
    try:
        with open(PENDING_FILE) as f:
            return json.load(f)
    except Exception:
        return {}

def save_pending(data):
    with open(PENDING_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# --- Shopify HMAC ---

def verify_shopify_hmac(raw_body, hmac_header):
    if not hmac_header:
        return False
    secret = os.getenv('SHOPIFY_CLIENT_SECRET', '').encode()
    digest = hmac.new(secret, raw_body, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode()
    return hmac.compare_digest(expected, hmac_header)

# --- Gemini post generation ---

def generate_facebook_post(product):
    desc = product.get('body_html', '') or ''
    import re
    desc = re.sub(r'<[^>]+>', '', desc).strip() or 'Premium quality product'
    variants = product.get('variants') or [{}]
    price = variants[0].get('price', '')
    price_str = f"₹{price}" if price else ''

    prompt = f"""You are a creative social media manager for Girnar Darshan, an Indian e-commerce store.

Write an engaging Facebook post for this new product:

Product: {product['title']}
{f'Price: {price_str}' if price_str else ''}
Description: {desc[:600]}
Link: https://girnardarshan.com/products/{product.get('handle', '')}

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

# --- Email via MCP ---

def build_email_html(title, price_str, image_url, safe_post, approve_url):
    image_block = ''
    if image_url:
        image_block = f'''
        <tr>
          <td style="padding:0;line-height:0;">
            <img src="{image_url}" alt="{title}" width="600"
              style="display:block;width:100%;max-height:340px;object-fit:cover;" />
          </td>
        </tr>'''

    price_block = f'<p style="margin:0 0 4px;font-size:20px;color:#1877f2;font-weight:700;">{price_str}</p>' if price_str else ''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#f0f4f8;font-family:'Segoe UI',Helvetica,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f4f8;padding:30px 15px;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 8px 32px rgba(0,0,0,0.12);max-width:600px;width:100%;">
        <tr>
          <td style="background:linear-gradient(135deg,#1877f2 0%,#0a5ac7 100%);padding:36px 40px;text-align:center;">
            <div style="font-size:40px;margin-bottom:12px;">📦</div>
            <h1 style="margin:0;color:#ffffff;font-size:26px;font-weight:700;">New Product Added!</h1>
            <p style="margin:10px 0 0;color:rgba(255,255,255,0.85);font-size:15px;">Review and approve to publish on Facebook</p>
          </td>
        </tr>
        {image_block}
        <tr>
          <td style="padding:32px 40px 8px;">
            <h2 style="margin:0 0 8px;font-size:22px;color:#1a1a2e;font-weight:700;line-height:1.3;">{title}</h2>
            {price_block}
          </td>
        </tr>
        <tr>
          <td style="padding:16px 40px 28px;">
            <div style="background:#f0f2f5;border-radius:12px;padding:24px;border-left:4px solid #1877f2;">
              <span style="display:inline-block;background:#1877f2;color:white;font-size:11px;font-weight:700;padding:4px 12px;border-radius:20px;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:16px;">🤖 AI-Generated Facebook Post</span>
              <p style="margin:0;color:#1c1e21;line-height:1.8;font-size:15px;white-space:pre-wrap;">{safe_post}</p>
            </div>
          </td>
        </tr>
        <tr>
          <td style="padding:0 40px 16px;text-align:center;">
            <a href="{approve_url}"
              style="display:inline-block;background:linear-gradient(135deg,#42b72a,#2d9e1a);color:#ffffff;text-decoration:none;padding:18px 56px;border-radius:50px;font-size:18px;font-weight:700;letter-spacing:0.3px;">
              ✅ &nbsp;Approve &amp; Post to Facebook
            </a>
          </td>
        </tr>
        <tr>
          <td style="padding:8px 40px 32px;text-align:center;">
            <p style="margin:0;color:#aaa;font-size:13px;">This link expires in 48 hours</p>
          </td>
        </tr>
        <tr>
          <td style="background:#f8f9fa;padding:20px 40px;text-align:center;border-top:1px solid #e8ecef;">
            <p style="margin:0;color:#bbb;font-size:12px;">Girnar Darshan Automation &nbsp;•&nbsp; Powered by Gemini AI</p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>'''

def send_approval_email(product, post_content, token, image_url):
    approve_url = f"{os.getenv('SERVER_URL')}/approve?token={token}"
    variants = product.get('variants') or [{}]
    price = variants[0].get('price', '')
    price_str = f"₹{price}" if price else ''
    safe_post = (post_content
                 .replace('&', '&amp;')
                 .replace('<', '&lt;')
                 .replace('>', '&gt;'))

    html = build_email_html(product['title'], price_str, image_url, safe_post, approve_url)
    body_text = (f"New product: {product['title']}\n\n"
                 f"AI Post:\n{post_content}\n\n"
                 f"Approve here: {approve_url}\n\n(Link expires in 48 hours)")

    payload = {
        'jsonrpc': '2.0',
        'id': 1,
        'method': 'tools/call',
        'params': {
            'name': 'send_email',
            'arguments': {
                'to': 'aishwarya@valuecart.in',
                'subject': f"New Product: {product['title']} — Approve Facebook Post",
                'body_html': html,
                'body_text': body_text,
            }
        }
    }
    res = requests.post(EMAIL_MCP_URL, json=payload,
                        headers={'Accept': 'application/json, text/event-stream'})
    data_line = next((l for l in res.text.splitlines() if l.startswith('data:')), None)
    if not data_line:
        raise Exception('No data in MCP email response')
    parsed = json.loads(data_line[5:].strip())
    if 'error' in parsed:
        raise Exception(f"Email MCP: {parsed['error']['message']}")
    return parsed['result']

# --- Facebook ---

def post_to_facebook(post_content, image_url):
    page_id = os.getenv('FACEBOOK_PAGE_ID')
    token = os.getenv('FACEBOOK_API_KEY')
    base = 'https://graph.facebook.com/v19.0'

    if image_url:
        res = requests.post(f'{base}/{page_id}/photos', json={
            'url': image_url,
            'caption': post_content,
            'access_token': token,
            'published': True,
        })
    else:
        res = requests.post(f'{base}/{page_id}/feed', json={
            'message': post_content,
            'access_token': token,
        })

    data = res.json()
    if 'error' in data:
        raise Exception(f"Facebook API: {data['error']['message']}")
    return data

# --- Pipeline (runs in background thread) ---

def run_pipeline(product):
    print(f"\n🛍️  New product: {product['title']}")
    try:
        images = product.get('images') or []
        image_url = images[0].get('src') if images else None

        post_content = generate_facebook_post(product)
        print('🤖 Post generated')

        token = str(uuid.uuid4())
        variants = product.get('variants') or [{}]
        pending = get_pending()
        pending[token] = {
            'product': {
                'title': product['title'],
                'handle': product.get('handle', ''),
                'price': variants[0].get('price', ''),
            },
            'post_content': post_content,
            'image_url': image_url,
            'created_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'expires_at': time.time() + 48 * 3600,
            'used': False,
        }
        save_pending(pending)

        send_approval_email(product, post_content, token, image_url)
        print('📧 Approval email sent to aishwarya@valuecart.in')
    except Exception as e:
        print(f'Pipeline error: {e}')

# --- Confirmation email after approval ---

def send_confirmation_email(product_title, image_url):
    html = f'''<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f0f4f8;font-family:'Segoe UI',Helvetica,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f4f8;padding:30px 15px;">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 8px 32px rgba(0,0,0,0.10);max-width:560px;width:100%;">
        <tr>
          <td style="background:linear-gradient(135deg,#42b72a,#2d9e1a);padding:32px 40px;text-align:center;">
            <div style="font-size:48px;margin-bottom:8px;">✅</div>
            <h1 style="margin:0;color:#fff;font-size:24px;font-weight:700;">Post is Live on Facebook!</h1>
          </td>
        </tr>
        {f'<tr><td style="padding:0;line-height:0;"><img src="{image_url}" width="560" style="display:block;width:100%;max-height:260px;object-fit:cover;" /></td></tr>' if image_url else ''}
        <tr>
          <td style="padding:32px 40px;text-align:center;">
            <p style="margin:0 0 8px;font-size:18px;color:#1a1a2e;font-weight:600;">{product_title}</p>
            <p style="margin:0;font-size:15px;color:#666;line-height:1.6;">Your Facebook post is now live. 🎉</p>
          </td>
        </tr>
        <tr>
          <td style="background:#f8f9fa;padding:16px 40px;text-align:center;border-top:1px solid #e8ecef;">
            <p style="margin:0;color:#bbb;font-size:12px;">Girnar Darshan Automation</p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>'''

    payload = {
        'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
        'params': {
            'name': 'send_email',
            'arguments': {
                'to': 'aishwarya@valuecart.in',
                'subject': f'✅ Posted to Facebook: {product_title}',
                'body_html': html,
                'body_text': f'Your post for "{product_title}" is now live on Facebook.',
            }
        }
    }
    try:
        res = requests.post(EMAIL_MCP_URL, json=payload,
                            headers={'Accept': 'application/json, text/event-stream'})
        data_line = next((l for l in res.text.splitlines() if l.startswith('data:')), None)
        if data_line:
            parsed = json.loads(data_line[5:].strip())
            if 'error' in parsed:
                print(f'Confirmation email error: {parsed["error"]["message"]}')
    except Exception as e:
        print(f'Confirmation email failed: {e}')

# --- HTML pages ---

def success_page(name):
    return f'''<!DOCTYPE html><html><head><meta charset="utf-8"><title>Posted!</title>
<script>window.close();</script>
<style>*{{box-sizing:border-box}}body{{margin:0;font-family:'Segoe UI',sans-serif;background:#f0f4f8;display:flex;align-items:center;justify-content:center;min-height:100vh}}
.card{{background:#fff;padding:60px 50px;border-radius:20px;text-align:center;box-shadow:0 8px 32px rgba(0,0,0,.1);max-width:440px;width:90%}}
.icon{{font-size:64px;margin-bottom:16px}}.h{{font-size:26px;font-weight:700;color:#1a1a2e;margin:0 0 12px}}
.s{{color:#666;font-size:16px;line-height:1.6;margin:0}}</style></head>
<body><div class="card"><div class="icon">✅</div>
<h1 class="h">Posted to Facebook!</h1>
<p class="s"><strong>{name}</strong> is live. A confirmation has been sent to your email. You can close this tab.</p>
</div></body></html>'''

def error_page(msg):
    return f'''<!DOCTYPE html><html><head><meta charset="utf-8"><title>Error</title>
<style>*{{box-sizing:border-box}}body{{margin:0;font-family:'Segoe UI',sans-serif;background:#f0f4f8;display:flex;align-items:center;justify-content:center;min-height:100vh}}
.card{{background:#fff;padding:60px 50px;border-radius:20px;text-align:center;box-shadow:0 8px 32px rgba(0,0,0,.1);max-width:440px;width:90%}}
.icon{{font-size:64px;margin-bottom:16px}}.h{{font-size:26px;font-weight:700;color:#e74c3c;margin:0 0 12px}}
.s{{color:#666;font-size:16px;line-height:1.6;margin:0}}</style></head>
<body><div class="card"><div class="icon">❌</div>
<h1 class="h">Something went wrong</h1>
<p class="s">{msg}</p>
</div></body></html>'''

def already_used_page(name):
    return f'''<!DOCTYPE html><html><head><meta charset="utf-8"><title>Already Posted</title>
<style>*{{box-sizing:border-box}}body{{margin:0;font-family:'Segoe UI',sans-serif;background:#f0f4f8;display:flex;align-items:center;justify-content:center;min-height:100vh}}
.card{{background:#fff;padding:60px 50px;border-radius:20px;text-align:center;box-shadow:0 8px 32px rgba(0,0,0,.1);max-width:440px;width:90%}}
.icon{{font-size:64px;margin-bottom:16px}}.h{{font-size:26px;font-weight:700;color:#f39c12;margin:0 0 12px}}
.s{{color:#666;font-size:16px;line-height:1.6;margin:0}}</style></head>
<body><div class="card"><div class="icon">ℹ️</div>
<h1 class="h">Already Posted</h1>
<p class="s"><strong>{name}</strong> was already posted to Facebook.</p>
</div></body></html>'''

# --- Routes ---

@app.route('/')
def health():
    return {'status': 'ok', 'service': 'Girnar Darshan Automation'}

@app.route('/webhook/shopify', methods=['POST'])
def shopify_webhook():
    raw_body = request.get_data()
    hmac_header = request.headers.get('X-Shopify-Hmac-Sha256', '')

    if not verify_shopify_hmac(raw_body, hmac_header):
        return 'Unauthorized', 401

    try:
        product = json.loads(raw_body)
    except Exception:
        return 'Bad Request', 400

    threading.Thread(target=run_pipeline, args=(product,), daemon=True).start()
    return 'OK', 200

@app.route('/approve')
def approve():
    token = request.args.get('token')
    if not token:
        return error_page('No approval token provided.'), 400

    pending = get_pending()
    entry = pending.get(token)

    if not entry:
        return error_page('Invalid or expired approval link.'), 404
    if entry.get('used'):
        return already_used_page(entry['product']['title'])
    if time.time() > entry['expires_at']:
        return error_page('This approval link has expired (48 hours).'), 410

    try:
        post_to_facebook(entry['post_content'], entry.get('image_url'))
        pending[token]['used'] = True
        pending[token]['posted_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        save_pending(pending)
        print(f"🚀 Posted to Facebook: {entry['product']['title']}")
        threading.Thread(
            target=send_confirmation_email,
            args=(entry['product']['title'], entry.get('image_url')),
            daemon=True
        ).start()
        return success_page(entry['product']['title'])
    except Exception as e:
        print(f'Facebook error: {e}')
        return error_page(str(e)), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 3000))
    server_url = os.getenv('SERVER_URL', f'http://localhost:{port}')
    print(f'\n🚀 Server running on port {port}')
    print(f'   Webhook : POST {server_url}/webhook/shopify')
    print(f'   Approve : GET  {server_url}/approve?token=...\n')
    app.run(port=port, threaded=True)
