#!/bin/bash
# usage: bash test_backup.sh [path to backup.sh]
script=$(realpath "${1:-./backup.sh}")
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
failed=0

check() {
  if [ "$2" = "$3" ]; then
    echo "ok: $1"
  else
    echo "FAIL: $1 (expected '$3', got '$2')"
    failed=1
  fi
}

mkdir -p "$work/my files/sub"
echo hello > "$work/my files/sub/a.txt"

BACKUP_STAMP=20250101 bash "$script" "$work/my files" "$work/out dir" 3 > /dev/null 2>&1
check "creates the archive in a new destination with spaces" "$(ls "$work/out dir" 2> /dev/null)" "backup-20250101.tar.gz"
check "the archive holds the files" "$(tar -tzf "$work/out dir/backup-20250101.tar.gz" 2> /dev/null | grep -c 'sub/a.txt')" 1

for stamp in 20250102 20250103 20250104; do
  BACKUP_STAMP=$stamp bash "$script" "$work/my files" "$work/out dir" 3 > /dev/null 2>&1
done
check "keeps the newest three archives" "$(ls "$work/out dir" | tr '\n' ' ')" "backup-20250102.tar.gz backup-20250103.tar.gz backup-20250104.tar.gz "

out=$(BACKUP_STAMP=20250105 bash "$script" "$work/my files" "$work/out dir" 3 2> /dev/null)
check "reports the kept count" "$out" "kept 3"
check "rotation drops the oldest" "$(ls "$work/out dir" | head -1)" "backup-20250103.tar.gz"

out=$(BACKUP_STAMP=20250107 bash "$script" "$work/my files" "$work/small" 5 2> /dev/null)
check "reports kept 1 when fewer than KEEP exist" "$out" "kept 1"

bash "$script" "$work/missing dir" "$work/never" 3 > /dev/null 2> "$work/err"
check "a missing source exits with status 2" "$?" 2
check "the error names the missing source" "$(grep -c 'missing dir' "$work/err")" 1
check "a missing source creates nothing" "$(ls "$work" | grep -c never)" 0

exit $failed
