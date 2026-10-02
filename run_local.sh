#!/usr/bin/env bash
# Run the whole demo against a throw-away DynamoDB Local container.
#
#   ./run_local.sh            # start container (if needed) + scripts 01-04 + generated DAL examples
#   ./run_local.sh cleanup    # scripts 05 + stop/remove the container
#
# Why -sharedDb: without it DynamoDB Local keeps a SEPARATE database per
# (access key id, region). Scripts run with different credentials then see
# "non-existent table" even though the table was just created. -sharedDb
# puts everything in one database regardless of credentials.
set -euo pipefail
cd "$(dirname "$0")"

CONTAINER=scania-dynamodb-local
PORT=8001   # 8000 is used by the MCP server's own validation container

export AWS_ENDPOINT_URL_DYNAMODB="http://localhost:${PORT}"
export AWS_ACCESS_KEY_ID=local AWS_SECRET_ACCESS_KEY=local AWS_DEFAULT_REGION=us-east-1

if [[ "${1:-}" == "cleanup" ]]; then
  python3 05_cleanup.py --yes || true
  docker rm -f "$CONTAINER" >/dev/null 2>&1 && echo "🧹 removed container $CONTAINER"
  exit 0
fi

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "🐳 starting DynamoDB Local on port $PORT"
  docker run -d --name "$CONTAINER" -p "${PORT}:8000" amazon/dynamodb-local \
    -jar DynamoDBLocal.jar -inMemory -sharedDb >/dev/null
  sleep 2
fi

python3 01_create_tables.py
python3 02_populate.py
python3 03_read_write.py
python3 04_modify_table.py

echo
echo "=============================================================================="
echo "Generated data access layer (dynamodb_schema/generated_dal/usage_examples.py)"
echo "=============================================================================="
python3 dynamodb_schema/generated_dal/usage_examples.py --all

echo
echo "Done. Clean up with: ./run_local.sh cleanup"
