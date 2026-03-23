import io

with io.open('backend/app/affiliates/wallet_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

has_inc = '"$inc"' in content
no_vuln = 'wallet.pending_balance += commission_amount' not in content

print('FIX STATUS:')
print(f'  $inc present: {has_inc}')
print(f'  Vulnerable removed: {no_vuln}')

if has_inc and no_vuln:
    print(f'\n✅ RACE CONDITION FIXED!')
else:
    print(f'\n❌ FIX NOT APPLIED')
    if not has_inc:
        print('  - Missing $inc operator')
    if not no_vuln:
        print('  - Vulnerable pattern still present')
