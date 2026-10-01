set -e
cd site
: > ../fixed.txt
while IFS= read -r path; do
  if [ -d "$path" ]; then
    want=755
    [ "$path" = secrets ] && want=700
  else
    want=644
    case "$path" in
      *.sh) want=755 ;;
      secrets/*) want=600 ;;
    esac
  fi
  if [ "$(stat -c %a "$path")" != "$want" ]; then
    chmod "$want" "$path"
    echo "$path" >> ../fixed.txt
  fi
done < <(find . -mindepth 1 | sed 's|^\./||' | sort)
sort -o ../fixed.txt ../fixed.txt
