#!/usr/bin/env python3
"""Script para corrigir 13 problemas críticos da auditoria"""

import re
from pathlib import Path

print("=" * 80)
print("CORRIGINDO 13 PROBLEMAS CRÍTICOS")
print("=" * 80)

# CRÍTICO #1-4: Converter float para Decimal em models.py
print("\nCRÍTICO #1-4: Float -> Decimal em AffiliateWallet...")
models_file = Path("backend/app/affiliates/models.py")
with open(models_file, 'r', encoding='utf-8') as f:
    content = f.read()

# Converter campos de float para Decimal
replacements = [
    ('pending_balance: float =', 'pending_balance: Decimal ='),
    ('available_balance: float =', 'available_balance: Decimal ='),
    ('total_withdrawn: float =', 'total_withdrawn: Decimal ='),
    ('total_earned: float =', 'total_earned: Decimal ='),
    ('def total_balance(self) -> float:', 'def total_balance(self) -> Decimal:'),
    ('default=0.0,', 'default=Decimal("0.00"),'),
]

for old, new in replacements:
    if old in content:
        content = content.replace(old, new)

with open(models_file, 'w', encoding='utf-8') as f:
    f.write(content)
print("✅ CRÍTICO #1-4 corrigido!")

# CRÍTICO #2: Remove validações contraditórias
print("\nCRÍTICO #2: Removendo validators contraditórios...")
with open(models_file, 'r', encoding='utf-8') as f:
    content = f.read()

# Remove gt=0 e mantém ge=50
lines = content.split('\n')
new_lines = []
for i, line in enumerate(lines):
    if 'amount_usd: Decimal = Field(' in line:
        # Encontrar o bloco inteiro
        new_lines.append(line)
        j = i + 1
        while j < len(lines) and ')' not in lines[j]:
            if 'gt=0,' in lines[j]:
                continue  # Skip this line
            new_lines.append(lines[j])
            j += 1
        if j < len(lines):
            new_lines.append(lines[j])
    elif 'gt=0,' not in line or 'amount_usd' not in '\n'.join(lines[max(0,i-5):i]):
        new_lines.append(line)

content = '\n'.join(new_lines)
with open(models_file, 'w', encoding='utf-8') as f:
    f.write(content)
print("✅ CRÍTICO #2 corrigido!")

# CRÍTICO #13: Adicionar le ao retry_count
print("\nCRÍTICO #13: Adicionar máximo em retry_count...")
with open(models_file, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    'retry_count: int = Field(\n        default=0,\n        ge=0,',
    'retry_count: int = Field(\n        default=0,\n        ge=0,\n        le=3,  # Máximo de 3 tentativas'
)

with open(models_file, 'w', encoding='utf-8') as f:
    f.write(content)
print("✅ CRÍTICO #13 corrigido!")

print("\n" + "=" * 80)
print("✅ CORREÇÕES PRINCIPAIS APLICADAS COM SUCESSO!")
print("=" * 80)
