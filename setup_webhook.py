import os
import requests
from dotenv import load_dotenv

load_dotenv()

STORE = 'girnardarshan-com.myshopify.com'
API_VERSION = '2024-01'

def main():
    print('🔧 Girnar Darshan Automation — Setup\n')

    # 1. Get Facebook page info
    print('📘 Checking Facebook page token...')
    res = requests.get(
        'https://graph.facebook.com/v19.0/me',
        params={'fields': 'id,name', 'access_token': os.getenv('FACEBOOK_API_KEY')}
    )
    fb = res.json()
    if 'error' in fb:
        print(f"  ⚠️  Facebook error: {fb['error']['message']}")
    else:
        print(f"  ✅ Page: \"{fb['name']}\" (ID: {fb['id']})")
        if not os.getenv('FACEBOOK_PAGE_ID'):
            print(f"\n  👉  Add this to your .env:\n      FACEBOOK_PAGE_ID={fb['id']}\n")
        elif os.getenv('FACEBOOK_PAGE_ID') != fb['id']:
            print(f"  ⚠️  FACEBOOK_PAGE_ID in .env ({os.getenv('FACEBOOK_PAGE_ID')}) doesn't match token ({fb['id']})")

    # 2. Register Shopify webhook
    if not os.getenv('SERVER_URL'):
        print('\n❌ SERVER_URL is not set in .env — cannot register webhook.')
        print('   Example: SERVER_URL=https://your-app.railway.app')
        return

    webhook_url = f"{os.getenv('SERVER_URL')}/webhook/shopify"
    headers = {
        'X-Shopify-Access-Token': os.getenv('SHOPIFY_ACCESS_TOKEN'),
        'Content-Type': 'application/json',
    }

    print(f'\n🔗 Registering Shopify webhook')
    print(f'   Topic : products/create')
    print(f'   Target: {webhook_url}')

    # Check existing
    res = requests.get(
        f'https://{STORE}/admin/api/{API_VERSION}/webhooks.json',
        params={'topic': 'products/create'},
        headers=headers
    )
    existing = next((w for w in res.json().get('webhooks', []) if w['address'] == webhook_url), None)

    if existing:
        print(f"\n  ✅ Webhook already registered (ID: {existing['id']})")
        return

    res = requests.post(
        f'https://{STORE}/admin/api/{API_VERSION}/webhooks.json',
        json={'webhook': {'topic': 'products/create', 'address': webhook_url, 'format': 'json'}},
        headers=headers
    )
    data = res.json()
    if 'webhook' in data:
        print(f"\n  ✅ Webhook registered! ID: {data['webhook']['id']}")
        print('\n🎉 Setup complete. Run "python server.py" to launch the server.\n')
    else:
        print(f"\n  ❌ Failed: {data.get('errors', data)}")

if __name__ == '__main__':
    main()
