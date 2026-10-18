import json
d = json.load(open('data/prospects/fresh_to_send.json', encoding='utf-8'))
print(f"Total: {len(d['companies'])}\n")
for c in d['companies']:
    name = c.get('company_name', '?')
    email = c.get('email', '?')
    sector = c.get('sector', '?')
    phone = c.get('phone_e164', '-')
    print(f"• {name}")
    print(f"  Email:  {email}")
    print(f"  Phone:  {phone}")
    print(f"  Sector: {sector}")
    print()