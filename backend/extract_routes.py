import re
with open('main.py', encoding='utf-8') as f:
    content = f.read()
routes = re.findall(r'@app\.(get|post|put|delete)\("(.*?)"', content)
for method, path in routes:
    print(f'{method.upper():6} {path}')
