The directory `templates/` holds text templates with placeholders, and `values.env` holds `KEY=value` settings. Write a shell script `render.sh` in the current directory that renders every `templates/*.tmpl` file into `out/<name>` (the same name without the `.tmpl` ending), creating `out/` when needed.

Placeholder rules:

- `{{KEY}}` is replaced by the value of KEY from `values.env`.
- `{{KEY|fallback}}` is replaced by the value of KEY when it is set, and by the text `fallback` otherwise.
- Lines in `values.env` starting with `#` and blank lines are ignored, and a value may contain spaces.
- If a template uses a key that is not in `values.env` and has no fallback, `render.sh` must print a line `missing: KEY` for each such key (each key once, in the order of first use across the sorted templates) to standard error, write no output file for that template, keep rendering the other templates, and exit with status 1 at the end. With no missing keys it exits with status 0.

`render.sh` must work when run as `bash render.sh` from this directory.
