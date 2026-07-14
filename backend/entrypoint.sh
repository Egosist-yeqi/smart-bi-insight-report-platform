#!/bin/sh
set -eu

if [ "$#" -gt 0 ]; then
    exec "$@"
fi

attempt=1
max_attempts=30

while ! alembic upgrade head >/dev/null 2>&1; do
    if [ "$attempt" -ge "$max_attempts" ]; then
        printf '%s\n' "Database migration did not succeed after ${max_attempts} attempts." >&2
        exit 1
    fi

    printf '%s\n' "Database migration is not ready; retrying (${attempt}/${max_attempts})." >&2
    attempt=$((attempt + 1))
    sleep 2
done

python -m app.db.seed
exec uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000
