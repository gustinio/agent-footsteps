expected_fixed='about.html
assets/app.css
assets/logo.png
bin/deploy.sh
bin/helper.py
docs
secrets
secrets/api.key
uploads
uploads/b.jpg'
expected_modes=':755
about.html:644
assets/app.css:644
assets/app.js:644
assets/logo.png:644
assets:755
bin/backup.sh:755
bin/deploy.sh:755
bin/helper.py:644
bin:755
docs/guide.md:644
docs:755
index.html:644
secrets/api.key:600
secrets/db.pass:600
secrets:700
uploads/a.jpg:644
uploads/b.jpg:644
uploads:755'

[ "$(cat fixed.txt 2>/dev/null)" = "$expected_fixed" ] || { echo "fixed.txt is missing or wrong"; exit 1; }
[ "$(cd site 2>/dev/null && find . -printf '%P:%m\n' | sort)" = "$expected_modes" ] || { echo "modes in site/ do not follow the policy"; exit 1; }
[ "$(cat site/secrets/api.key)" = "content of secrets/api.key" ] || { echo "file contents changed"; exit 1; }
