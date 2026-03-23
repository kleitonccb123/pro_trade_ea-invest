#!/usr/bin/env python3
"""Remove the duplicate Google OAuth button from Login.tsx"""

import re

# Read the file
with open('src/pages/Login.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Pattern to match the Option 2 button (from the comment through the closing button tag)
pattern = r'\s*\{\s*/\*\s*Google Login - Option 2:[^*]*\*\/\s*\}\s*<button[^>]*>[\s\S]*?</button>\s*'

# Replace with nothing (remove it)
result = re.sub(pattern, '', content)

# Write back
with open('src/pages/Login.tsx', 'w', encoding='utf-8') as f:
    f.write(result)

print("✓ Botão duplicado do Google removido de Login.tsx")
