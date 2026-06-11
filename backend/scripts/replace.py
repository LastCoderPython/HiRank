import os
import glob

# Backend
backend_files = glob.glob('backend/app/api/*.py')
for file in backend_files:
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()
    content = content.replace('prefix="/api', 'prefix="/api/v1')
    with open(file, 'w', encoding='utf-8') as f:
        f.write(content)

# Frontend api.ts
frontend_file = 'frontend/lib/api.ts'
with open(frontend_file, 'r', encoding='utf-8') as f:
    content = f.read()
content = content.replace("'/api/", "'/api/v1/")
with open(frontend_file, 'w', encoding='utf-8') as f:
    f.write(content)

# main.py might have a redirect or root endpoint
main_file = 'backend/app/main.py'
with open(main_file, 'r', encoding='utf-8') as f:
    content = f.read()
content = content.replace('"/api/health"', '"/api/v1/health"')
with open(main_file, 'w', encoding='utf-8') as f:
    f.write(content)

print('Updated prefixes')
