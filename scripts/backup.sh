#!/data/data/com.termux/files/usr/bin/bash
BASE="$HOME/Servidor"; mkdir -p "$BASE/Backups"; DATE=$(date '+%Y-%m-%d_%H-%M-%S')
python - <<PY
import zipfile, pathlib
base=pathlib.Path.home()/'Servidor'
target=base/'Backups'/'backup_$DATE.zip'
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
    for folder in ['Files','Cameras']:
        for p in (base/folder).rglob('*'):
            if p.is_file(): z.write(p,p.relative_to(base))
print('Backup criado:', target.name)
PY
