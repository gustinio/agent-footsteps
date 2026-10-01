#!/bin/bash
src=$1
dest=$2
keep=$3
stamp=${BACKUP_STAMP:-$(date +%Y%m%d%H%M%S)}

if [ ! -d $src ]; then
  echo "error: no such directory: $src" >&2
  exit 0
fi

mkdir -p $dest
tar -czf $dest/backup-$stamp.tar.gz -C $src .

count=0
for f in $(ls $dest/backup-*.tar.gz); do
  count=$((count + 1))
  if [ $count -gt $keep ]; then
    rm $f
  fi
done
echo "kept $count"
