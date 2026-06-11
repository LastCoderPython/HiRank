import glob

# Backend tests
test_files = glob.glob('backend/tests/*.py')
for file in test_files:
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()
    content = content.replace('"/api/', '"/api/v1/')
    content = content.replace("'/api/", "'/api/v1/")
    with open(file, 'w', encoding='utf-8') as f:
        f.write(content)

print('Fixed test paths')
