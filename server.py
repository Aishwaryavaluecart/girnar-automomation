import sys
sys.stdout.reconfigure(encoding='utf-8')

import os
import io
import re
import json
import hmac
import hashlib
import base64
import time
import uuid
import threading
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from google import genai

load_dotenv()

app = Flask(__name__)
STORE      = 'girnardarshan-com.myshopify.com'
SERVER_URL = os.getenv('SERVER_URL', 'http://localhost:3000')
_TOKEN_SECRET = os.getenv('REGISTER_SECRET', 'girnar2026')

gemini = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

# --- Signed token (no server-side storage needed) ---

def create_signed_token(data):
    payload = base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip('=')
    sig = hmac.new(_TOKEN_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"

def decode_signed_token(token_str):
    try:
        payload, sig = token_str.rsplit('.', 1)
        expected = hmac.new(_TOKEN_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            return None
        padding = 4 - len(payload) % 4
        return json.loads(base64.urlsafe_b64decode(payload + '=' * padding).decode())
    except Exception:
        return None

# --- Shopify HMAC ---

def verify_shopify_hmac(raw_body, hmac_header):
    if not hmac_header:
        return False
    secret = os.getenv('SHOPIFY_CLIENT_SECRET', '').encode()
    digest = hmac.new(secret, raw_body, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode()
    return hmac.compare_digest(expected, hmac_header)

# --- Gemini ---

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

# --- Email via SendGrid (AMP + HTML fallback) ---

def build_amp_email(title, price_str, image_url, post_content, token):
    approve_url = f"{SERVER_URL}/approve-amp"
    safe_post = post_content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

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
    .price {{ font-size:18px; color:#1877f2; font-weight:700; margin:0 0 20px; }}
    .post-box {{ background:#f0f2f5; border-left:4px solid #1877f2; border-radius:8px; padding:20px; margin-bottom:24px; }}
    .post-label {{ display:inline-block; background:#1877f2; color:#fff; font-size:10px; font-weight:700; padding:3px 10px; border-radius:20px; text-transform:uppercase; letter-spacing:0.8px; margin-bottom:12px; }}
    .post-text {{ margin:0; color:#1c1e21; font-size:14px; line-height:1.75; white-space:pre-wrap; }}
    .btn {{ display:block; width:100%; background:linear-gradient(135deg,#42b72a,#2d9e1a); color:#fff; border:none; padding:18px; border-radius:50px; font-size:17px; font-weight:700; cursor:pointer; text-align:center; }}
    .success-box {{ background:#f0fff4; border:2px solid #42b72a; border-radius:12px; padding:24px; text-align:center; }}
    .success-icon {{ font-size:48px; margin-bottom:8px; }}
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
              <div class="success-icon">✅</div>
              <p class="success-title">Posted to Facebook!</p>
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
    safe_post = post_content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
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
    variants = product.get('variants') or [{}]
    price = variants[0].get('price', '')
    price_str = f"₹{price}" if price else ''

    amp_html  = build_amp_email(product['title'], price_str, image_url, post_content, token)
    html      = build_fallback_html(product['title'], price_str, image_url, post_content, token)
    plain     = f"New product: {product['title']}\n\nPost:\n{post_content}\n\nApprove: {SERVER_URL}/approve?token={token}"

    payload = {
        'personalizations': [{'to': [{'email': 'aishwarya@valuecart.in', 'name': 'Aishwarya'}]}],
        'from': {'email': 'aryan@valuecart.in', 'name': 'Girnar Darshan'},
        'subject': f"New Product: {product['title']} — Approve Facebook Post",
        'content': [
            {'type': 'text/plain',     'value': plain},
            {'type': 'text/x-amp-html','value': amp_html},
            {'type': 'text/html',      'value': html},
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
        raise Exception(f"SendGrid error {res.status_code}: {res.text[:200]}")

# --- Poster ---

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')

THEMES = [
    {   # 1 — Navy & Gold (classic luxury)
        'bg1': (12, 8, 35),   'bg2': (28, 18, 65),
        'plate': (248, 246, 255),
        'accent': (212, 175, 55),
        'title': (255, 255, 255),
        'btn_text': (12, 8, 35),
    },
    {   # 2 — Emerald & Champagne (nature, premium)
        'bg1': (6, 38, 24),   'bg2': (12, 68, 42),
        'plate': (240, 252, 245),
        'accent': (230, 210, 160),
        'title': (255, 255, 255),
        'btn_text': (6, 38, 24),
    },
    {   # 3 — Burgundy & Rose Gold (festive, gifting)
        'bg1': (48, 8, 22),   'bg2': (85, 18, 42),
        'plate': (255, 245, 248),
        'accent': (210, 155, 130),
        'title': (255, 255, 255),
        'btn_text': (48, 8, 22),
    },
    {   # 4 — Midnight Purple & Lavender (spiritual)
        'bg1': (22, 8, 55),   'bg2': (45, 18, 95),
        'plate': (248, 245, 255),
        'accent': (185, 160, 245),
        'title': (255, 255, 255),
        'btn_text': (22, 8, 55),
    },
    {   # 5 — Charcoal & Amber (bold, modern)
        'bg1': (18, 16, 14),  'bg2': (42, 38, 32),
        'plate': (252, 250, 245),
        'accent': (255, 185, 55),
        'title': (255, 255, 255),
        'btn_text': (18, 16, 14),
    },
]
_FONTS = {
    'bold':     'https://raw.githubusercontent.com/google/fonts/main/ofl/poppins/Poppins-Bold.ttf',
    'regular':  'https://raw.githubusercontent.com/google/fonts/main/ofl/poppins/Poppins-Regular.ttf',
    'semibold': 'https://raw.githubusercontent.com/google/fonts/main/ofl/poppins/Poppins-SemiBold.ttf',
}

def _ensure_fonts():
    os.makedirs(FONT_DIR, exist_ok=True)
    paths = {}
    for key, url in _FONTS.items():
        path = os.path.join(FONT_DIR, f'Poppins-{key.capitalize()}.ttf')
        if not os.path.exists(path):
            try:
                r = requests.get(url, timeout=15)
                with open(path, 'wb') as f:
                    f.write(r.content)
            except Exception as e:
                print(f'Font download failed ({key}): {e}')
                path = None
        paths[key] = path if os.path.exists(path or '') else None
    return paths

def create_poster(title, price_str, image_url, post_content):
    from PIL import Image, ImageDraw, ImageFont

    theme = THEMES[hash(title) % len(THEMES)]
    BG1   = theme['bg1']
    BG2   = theme['bg2']
    GOLD  = theme['accent']
    WHITE = theme['title']
    PLATE = theme['plate']
    BTNFG = theme['btn_text']

    W, H = 1080, 1080

    canvas = Image.new('RGB', (W, H), BG1)
    draw   = ImageDraw.Draw(canvas)
    for y in range(H):
        t = y / H
        r = int(BG1[0] + (BG2[0] - BG1[0]) * t)
        g = int(BG1[1] + (BG2[1] - BG1[1]) * t)
        b = int(BG1[2] + (BG2[2] - BG1[2]) * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    PAD    = 48
    IMG_H  = 560
    IMG_W  = W - PAD * 2

    if image_url:
        try:
            resp     = requests.get(image_url, timeout=10)
            raw      = Image.open(io.BytesIO(resp.content)).convert('RGBA')
            bg_white = Image.new('RGB', raw.size, WHITE)
            if raw.mode == 'RGBA':
                bg_white.paste(raw, mask=raw.split()[3])
            else:
                bg_white.paste(raw)
            raw = bg_white
            raw.thumbnail((IMG_W, IMG_H), Image.LANCZOS)
            pw, ph = raw.size
            plate = Image.new('RGB', (IMG_W, IMG_H), PLATE)
            plate.paste(raw, ((IMG_W - pw) // 2, (IMG_H - ph) // 2))
            canvas.paste(plate, (PAD, PAD))
        except Exception as e:
            print(f'Poster image error: {e}')

    line_y = PAD + IMG_H + 16
    draw.line([(PAD, line_y), (W - PAD, line_y)], fill=GOLD, width=2)

    font_paths = _ensure_fonts()

    def fnt(key, size):
        p = font_paths.get(key)
        if p:
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
        return ImageFont.load_default()

    f_brand   = fnt('bold',     26)
    f_title   = fnt('bold',     52)
    f_price   = fnt('bold',     46)
    f_cta     = fnt('semibold', 30)
    f_url     = fnt('semibold', 22)

    y = line_y + 24

    # Brand line
    draw.text((W // 2, y), 'GIRNAR DARSHAN', font=f_brand, fill=GOLD, anchor='mt')
    y += 44

    # Title — wrap to 2 lines
    words, cur, title_lines = title.split(), '', []
    for word in words:
        test = (cur + ' ' + word).strip()
        if draw.textlength(test, font=f_title) > W - PAD * 2.5:
            if cur:
                title_lines.append(cur)
            cur = word
        else:
            cur = test
    if cur:
        title_lines.append(cur)
    for line in title_lines[:2]:
        draw.text((W // 2, y), line, font=f_title, fill=WHITE, anchor='mt')
        y += 64

    y += 8

    # Price
    if price_str:
        draw.text((W // 2, y), price_str, font=f_price, fill=GOLD, anchor='mt')
        y += 62

    # Shop Now CTA button
    cta_text = '🛍  Shop Now'
    cta_w = int(draw.textlength(cta_text, font=f_cta)) + 80
    cta_h = 58
    cta_x = (W - cta_w) // 2
    cta_y = y
    draw.rounded_rectangle([cta_x, cta_y, cta_x + cta_w, cta_y + cta_h], radius=29, fill=GOLD)
    draw.text((W // 2, cta_y + cta_h // 2), cta_text, font=f_cta, fill=BTNFG, anchor='mm')

    # URL footer
    draw.text((W // 2, H - 32), 'girnardarshan-com.myshopify.com', font=f_url, fill=GOLD, anchor='mb')

    buf = io.BytesIO()
    canvas.save(buf, format='JPEG', quality=93)
    return buf.getvalue()

# --- Facebook ---

def post_to_facebook(post_content, image_url, poster_bytes=None):
    page_id = os.getenv('FACEBOOK_PAGE_ID')
    token   = os.getenv('FACEBOOK_API_KEY')
    base    = 'https://graph.facebook.com/v19.0'

    if poster_bytes:
        res = requests.post(
            f'{base}/{page_id}/photos',
            data={'caption': post_content, 'access_token': token, 'published': 'true'},
            files={'source': ('poster.jpg', poster_bytes, 'image/jpeg')},
        )
    elif image_url:
        res = requests.post(f'{base}/{page_id}/photos', json={
            'url': image_url, 'caption': post_content,
            'access_token': token, 'published': True,
        })
    else:
        res = requests.post(f'{base}/{page_id}/feed', json={
            'message': post_content, 'access_token': token,
        })

    data = res.json()
    if 'error' in data:
        raise Exception(f"Facebook API: {data['error']['message']}")
    return data

# --- Pipeline ---

def run_pipeline(product):
    print(f"\n🛍️  New product: {product['title']}")
    try:
        images    = product.get('images') or []
        image_url = images[0].get('src') if images else None
        variants  = product.get('variants') or [{}]

        post_content = generate_facebook_post(product)
        print('🤖 Post generated')

        entry = {
            'product': {
                'title':  product['title'],
                'handle': product.get('handle', ''),
                'price':  variants[0].get('price', ''),
            },
            'post_content': post_content,
            'image_url':    image_url,
            'expires_at':   time.time() + 48 * 3600,
        }
        token = create_signed_token(entry)

        send_approval_email(product, post_content, token, image_url)
        print('📧 Approval email sent to aishwarya@valuecart.in')
    except Exception as e:
        print(f'Pipeline error: {e}')

# --- AMP CORS helper ---

def amp_cors_headers():
    origin = request.headers.get('Origin', '*')
    return {
        'Access-Control-Allow-Origin':             origin,
        'Access-Control-Allow-Methods':            'POST, OPTIONS',
        'Access-Control-Allow-Headers':            'Content-Type, AMP-Same-Origin',
        'Access-Control-Expose-Headers':           'AMP-Access-Control-Allow-Source-Origin',
        'AMP-Access-Control-Allow-Source-Origin':  SERVER_URL,
    }

# --- HTML pages (fallback for non-AMP clients) ---

def success_page(name):
    return f'''<!DOCTYPE html><html><head><meta charset="utf-8"><title>Posted!</title>
<script>window.close();</script>
<style>*{{box-sizing:border-box}}body{{margin:0;font-family:'Segoe UI',sans-serif;background:#f0f4f8;display:flex;align-items:center;justify-content:center;min-height:100vh}}
.card{{background:#fff;padding:60px 50px;border-radius:20px;text-align:center;box-shadow:0 8px 32px rgba(0,0,0,.1);max-width:440px;width:90%}}</style></head>
<body><div class="card"><div style="font-size:64px;margin-bottom:16px">✅</div>
<h1 style="font-size:26px;font-weight:700;color:#1a1a2e;margin:0 0 12px">Posted to Facebook!</h1>
<p style="color:#666;font-size:16px;margin:0"><strong>{name}</strong> is now live. You can close this tab.</p>
</div></body></html>'''

def error_page(msg):
    return f'''<!DOCTYPE html><html><head><meta charset="utf-8"><title>Error</title>
<style>*{{box-sizing:border-box}}body{{margin:0;font-family:'Segoe UI',sans-serif;background:#f0f4f8;display:flex;align-items:center;justify-content:center;min-height:100vh}}
.card{{background:#fff;padding:60px 50px;border-radius:20px;text-align:center;box-shadow:0 8px 32px rgba(0,0,0,.1);max-width:440px;width:90%}}</style></head>
<body><div class="card"><div style="font-size:64px;margin-bottom:16px">❌</div>
<h1 style="font-size:26px;font-weight:700;color:#e74c3c;margin:0 0 12px">Something went wrong</h1>
<p style="color:#666;font-size:16px;margin:0">{msg}</p>
</div></body></html>'''

def already_used_page(name):
    return f'''<!DOCTYPE html><html><head><meta charset="utf-8"><title>Already Posted</title>
<style>*{{box-sizing:border-box}}body{{margin:0;font-family:'Segoe UI',sans-serif;background:#f0f4f8;display:flex;align-items:center;justify-content:center;min-height:100vh}}
.card{{background:#fff;padding:60px 50px;border-radius:20px;text-align:center;box-shadow:0 8px 32px rgba(0,0,0,.1);max-width:440px;width:90%}}</style></head>
<body><div class="card"><div style="font-size:64px;margin-bottom:16px">ℹ️</div>
<h1 style="font-size:26px;font-weight:700;color:#f39c12;margin:0 0 12px">Already Posted</h1>
<p style="color:#666;font-size:16px;margin:0"><strong>{name}</strong> was already posted to Facebook.</p>
</div></body></html>'''

# --- Routes ---

@app.route('/')
def health():
    return {'status': 'ok', 'service': 'Girnar Darshan Automation'}

@app.route('/poster/<path:token>')
def serve_poster(token):
    entry = decode_signed_token(token)
    if not entry:
        return 'Not found', 404
    try:
        p         = entry['product']
        price_str = f"₹{p['price']}" if p.get('price') else ''
        img_bytes = create_poster(p['title'], price_str, entry.get('image_url'), entry['post_content'])
        from flask import Response
        return Response(img_bytes, mimetype='image/jpeg')
    except Exception as e:
        return str(e), 500

@app.route('/webhook/shopify', methods=['POST'])
def shopify_webhook():
    raw_body    = request.get_data()
    hmac_header = request.headers.get('X-Shopify-Hmac-Sha256', '')

    if not verify_shopify_hmac(raw_body, hmac_header):
        return 'Unauthorized', 401

    try:
        product = json.loads(raw_body)
    except Exception:
        return 'Bad Request', 400

    threading.Thread(target=run_pipeline, args=(product,), daemon=True).start()
    return 'OK', 200

def _do_post(entry):
    p         = entry['product']
    price_str = f"₹{p['price']}" if p.get('price') else ''
    poster    = create_poster(p['title'], price_str, entry.get('image_url'), entry['post_content'])
    post_to_facebook(entry['post_content'], entry.get('image_url'), poster_bytes=poster)
    print(f"🚀 Posted to Facebook: {p['title']}")

@app.route('/approve-amp', methods=['OPTIONS', 'POST'])
def approve_amp():
    headers = amp_cors_headers()
    if request.method == 'OPTIONS':
        return ('', 204, headers)

    token = request.form.get('token') if not request.is_json else request.json.get('token')
    if not token:
        return jsonify({'message': 'No token provided.'}), 400, headers

    entry = decode_signed_token(token)
    if not entry:
        return jsonify({'message': 'Invalid or expired approval link.'}), 404, headers
    if time.time() > entry['expires_at']:
        return jsonify({'message': 'This approval link has expired (48 hours).'}), 410, headers

    try:
        _do_post(entry)
        return jsonify({'message': f"{entry['product']['title']} is now live on your Facebook page!"}), 200, headers
    except Exception as e:
        print(f'Facebook error: {e}')
        return jsonify({'message': str(e)}), 500, headers

@app.route('/approve')
def approve():
    token = request.args.get('token')
    if not token:
        return error_page('No approval token provided.'), 400

    entry = decode_signed_token(token)
    if not entry:
        return error_page('Invalid or expired approval link.'), 404
    if time.time() > entry['expires_at']:
        return error_page('This approval link has expired (48 hours).'), 410

    try:
        _do_post(entry)
        return success_page(entry['product']['title'])
    except Exception as e:
        print(f'Facebook error: {e}')
        return error_page(str(e)), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 3000))
    print(f'\n🚀 Server running on port {port}')
    print(f'   Webhook : POST {SERVER_URL}/webhook/shopify')
    print(f'   Approve : GET  {SERVER_URL}/approve?token=...\n')
    app.run(port=port, threaded=True)
