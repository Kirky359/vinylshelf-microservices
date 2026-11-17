#!/usr/bin/env bash
# Prints an access token (JWT) from Keycloak via the dev-only password grant of the vinylshelf-cli client.
# usage: TOKEN=$(keycloak/get_token.sh [user] [password])
KC=${KC:-http://localhost:8081}
curl -s -X POST "$KC/realms/vinylshelf/protocol/openid-connect/token" \
  -d grant_type=password -d client_id=vinylshelf-cli \
  -d "username=${1:-artem}" -d "password=${2:-artem123}" \
  -d "scope=openid catalog:read collection:read collection:write rating:read rating:write analytics:read" \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])'
