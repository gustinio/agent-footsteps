set -e
mkdir templates
cat > values.env <<'ENV'
# deployment settings
APP_NAME=Orbit Dashboard
PORT=8443
ENV_NAME=staging

OWNER=platform team
ENV
cat > templates/server.conf.tmpl <<'TMPL'
# {{APP_NAME}} ({{ENV_NAME}})
listen {{PORT}}
workers {{WORKERS|4}}
owner "{{OWNER}}"
TMPL
cat > templates/motd.txt.tmpl <<'TMPL'
Welcome to {{APP_NAME}}.
Environment: {{ENV_NAME|unknown}}
Contact: {{CONTACT_EMAIL|nobody@example.com}}
TMPL
cat > templates/health.json.tmpl <<'TMPL'
{"service": "{{APP_NAME}}", "port": {{PORT}}, "region": "{{REGION}}"}
TMPL
