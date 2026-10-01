set -e
cat > backup.sh <<'SCRIPT'
#!/bin/bash
src=$1
dest=$2
keep=$3
stamp=${BACKUP_STAMP:-$(date +%Y%m%d%H%M%S)}

if [ ! -d "$src" ]; then
  echo "error: no such directory: $src" >&2
  exit 2
fi

mkdir -p "$dest"
tar -czf "$dest/backup-$stamp.tar.gz" -C "$src" .

count=0
while IFS= read -r f; do
  count=$((count + 1))
  if [ "$count" -gt "$keep" ]; then
    rm -- "$f"
  fi
done < <(ls -r "$dest"/backup-*.tar.gz)
echo "kept $((count > keep ? keep : count))"
SCRIPT
