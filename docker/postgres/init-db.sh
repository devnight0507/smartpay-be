#!/bin/bash

set -e
set -u

echo "Checking if database '$POSTGRES_DB' exists..."

DB_EXIST=$(psql -U "$POSTGRES_USER" -tAc "SELECT 1 FROM pg_database WHERE datname = '$POSTGRES_DB'")
if [ "$DB_EXIST" = "1" ]; then
    echo "Database '$POSTGRES_DB' already exists. Skipping creation."
else
    echo "Creating database '$POSTGRES_DB'..."
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
        CREATE DATABASE "$POSTGRES_DB";
        GRANT ALL PRIVILEGES ON DATABASE "$POSTGRES_DB" TO "$POSTGRES_USER";
EOSQL
    echo "Database '$POSTGRES_DB' created successfully."
fi
