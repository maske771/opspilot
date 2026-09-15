#!/bin/sh
set -eu

cat > /tmp/alertmanager.yml <<EOF
$(cat /etc/alertmanager/alertmanager.yml.tpl)
EOF

exec /bin/alertmanager --config.file=/tmp/alertmanager.yml --storage.path=/alertmanager
