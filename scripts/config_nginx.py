import sys
from pathlib import Path

conf_path = Path(sys.argv[1])
web_root = sys.argv[2]
text = conf_path.read_text()
lines = text.splitlines()
out = []
root_changed = False

for line in lines:
    s = line.strip()
    if s.startswith("root ") and s.endswith(";"):
        indent = line[:len(line)-len(line.lstrip())]
        out.append(f"{indent}root {web_root};")
        root_changed = True
    elif s.startswith("index "):
        indent = line[:len(line)-len(line.lstrip())]
        out.append(f"{indent}index index.html;")
    else:
        out.append(line)

if not root_changed:
    new = []
    inserted = False
    for line in out:
        new.append(line)
        if not inserted and "server {" in line:
            new.append(f"        root {web_root};")
            new.append("        index index.html;")
            inserted = True
    out = new

conf_path.write_text("\n".join(out) + "\n")
print("Nginx apontando para:", web_root)
