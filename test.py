import sys
sys.stdout.reconfigure(encoding='utf-8')

import os
import re
import json
import uuid
import time
import requests
from dotenv import load_dotenv
from google import genai

load_dotenv()

EMAIL_MCP_URL = 'https://valuecart-email-mcp-production.up.railway.app/mcp/valuecart2026'
STORE = 'girnardarshan-com.myshopify.com'
PRODUCT_TITLE = 'Embroidered Girnar Kerchief | French Work Note | White & Gold'
PENDING_FILE = 'pending.json'

gemini = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

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

def fetch_product():
    res = requests.get(
        f'https://{STORE}/admin/api/2024-01/products.json',
        params={'title': PRODUCT_TITLE, 'limit': 5},
        headers={'X-Shopify-Access-Token': os.getenv('SHOPIFY_ACCESS_TOKEN')}
    )
    products = res.json().get('products', [])
    product = next((p for p in products if 'kerchief' in p['title'].lower()), None)
    if not product:
        raise Exception(f'Product not found: "{PRODUCT_TITLE}"')
    return product

def generate_facebook_post(product):
    desc = re.sub(r'<[^>]+>', '', product.get('body_html', '') or '').strip() or 'Premium quality product'
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

def main():
    print('🧪 Test run — Girnar Darshan Automation\n')

    if not os.getenv('SERVER_URL'):
        print('❌ Missing .env var: SERVER_URL')
        return

    # 1. Fetch product
    print('📦 Fetching product from Shopify...')
    product = fetch_product()
    images = product.get('images') or []
    image_url = images[0].get('src') if images else None
    variants = product.get('variants') or [{}]
    price = variants[0].get('price', '')
    print(f"   ✅ Found: {product['title']}")
    print(f"   Price : {'₹' + price if price else '(no price)'}")
    print(f"   Image : {image_url or '(no image)'}")

    # 2. Generate post
    print('\n🤖 Generating Facebook post with Gemini...')
    post_content = generate_facebook_post(product)
    print(f'\n--- Generated Post ---\n{post_content}\n----------------------\n')

    # 3. Save token
    token = str(uuid.uuid4())
    pending = get_pending()
    pending[token] = {
        'product': {
            'title': product['title'],
            'handle': product.get('handle', ''),
            'price': price,
        },
        'post_content': post_content,
        'image_url': image_url,
        'created_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'expires_at': time.time() + 48 * 3600,
        'used': False,
    }
    save_pending(pending)

    # 4. Send email
    print('📧 Sending approval email to aishwarya@valuecart.in...')
    send_approval_email(product, post_content, token, image_url)
    print('   ✅ Email sent!\n')

    # 5. Print approve URL
    approve_url = f"{os.getenv('SERVER_URL')}/approve?token={token}"
    print(f'🔗 Approve URL (also in the email):')
    print(f'   {approve_url}\n')
    print('✅ Test complete. Start the server with "python server.py" then click Approve in the email.')

if __name__ == '__main__':
    main()
