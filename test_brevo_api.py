import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("BREVO_API_KEY")
if not api_key:
    print("❌ لم يتم العثور على BREVO_API_KEY في ملف .env")
else:
    headers = {"api-key": api_key, "accept": "application/json"}
    
    # نأخذ تاريخ اليوم ونطرح منه يوم واحد لضمان قبول الطلب
    safe_end_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    url = "https://api.brevo.com/v3/smtp/statistics/aggregatedReport"
    params = {"startDate": "2026-10-01", "endDate": safe_end_date}
    
    r = requests.get(url, headers=headers, params=params)
    print("Status Code:", r.status_code)
    if r.status_code == 200:
        data = r.json()
        print("✅ الاتصال ناجح! الإحصائيات:")
        print(f"Sent: {data.get('sent')}")
        print(f"Delivered: {data.get('delivered')}")
        print(f"Opened: {data.get('uniqueOpens')}")
        print(f"Clicks: {data.get('uniqueClicks')}")
    else:
        print("Response:", r.json())