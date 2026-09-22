#!/bin/sh
set -eu
# Resolve upstreams again after container replacement; use namespace-qualified
# service names because nginx's asynchronous resolver does not use search paths.
HOMEHUB_DNS=$(awk '$1 == "nameserver" {print $2; exit}' /etc/resolv.conf)
HOMEHUB_DOMAIN=$(awk '$1 == "search" {for (i=2;i<=NF;i++) if ($i ~ /\.svc\.cluster\.local$/) {print "." $i; exit}}' /etc/resolv.conf)
export HOMEHUB_DNS HOMEHUB_DOMAIN
envsubst '${HOMEHUB_DNS} ${HOMEHUB_DOMAIN}' < /etc/nginx/homehub.conf.template > /etc/nginx/conf.d/default.conf
