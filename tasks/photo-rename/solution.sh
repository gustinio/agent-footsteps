set -e
cd photos
declare -A used
: > ../renames.tsv
while IFS= read -r f; do
  case "${f,,}" in *.jpg|*.jpeg) ;; *) continue ;; esac
  stem=$(printf '%s' "${f%.*}" | tr 'A-Z' 'a-z' | sed -E 's/[^a-z0-9]+/_/g; s/^_+//; s/_+$//')
  name="$stem.jpg"
  n=1
  while [ -n "${used[$name]:-}" ]; do
    n=$((n + 1))
    name="${stem}_$n.jpg"
  done
  used[$name]=1
  if [ "$f" != "$name" ]; then
    mv -- "$f" "$name"
    printf '%s\t%s\n' "$f" "$name" >> ../renames.tsv
  fi
done < <(printf '%s\n' * | sort)
