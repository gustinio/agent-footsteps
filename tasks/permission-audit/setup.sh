set -e
mkdir -p site/assets site/bin site/secrets site/uploads site/docs
cd site
for entry in index.html:644 about.html:666 assets/app.js:644 assets/app.css:777 assets/logo.png:600 bin/deploy.sh:644 bin/backup.sh:755 bin/helper.py:755 secrets/api.key:644 secrets/db.pass:600 uploads/a.jpg:644 uploads/b.jpg:664 docs/guide.md:644; do
  path=${entry%%:*}
  echo "content of $path" > "$path"
  chmod "${entry##*:}" "$path"
done
chmod 755 . assets bin
chmod 755 secrets
chmod 777 uploads
chmod 750 docs
