set -e
cat > render.sh <<'SCRIPT'
#!/bin/bash
declare -A values
while IFS= read -r line; do
  case "$line" in ''|'#'*) continue ;; esac
  values[${line%%=*}]=${line#*=}
done < values.env

mkdir -p out
status=0
declare -A reported
for template in templates/*.tmpl; do
  name=$(basename "$template" .tmpl)
  rendered=
  missing=
  while IFS= read -r line || [ -n "$line" ]; do
    while [[ $line =~ \{\{([A-Za-z_][A-Za-z0-9_]*)(\|([^}]*))?\}\} ]]; do
      whole=${BASH_REMATCH[0]}
      key=${BASH_REMATCH[1]}
      if [ -n "${values[$key]+set}" ]; then
        replacement=${values[$key]}
      elif [ -n "${BASH_REMATCH[2]}" ]; then
        replacement=${BASH_REMATCH[3]}
      else
        missing=1
        if [ -z "${reported[$key]:-}" ]; then
          echo "missing: $key" >&2
          reported[$key]=1
        fi
        replacement=
      fi
      line=${line/"$whole"/$replacement}
    done
    rendered+=$line$'\n'
  done < "$template"
  if [ -n "$missing" ]; then
    status=1
  else
    printf '%s' "$rendered" > "out/$name"
  fi
done
exit $status
SCRIPT
