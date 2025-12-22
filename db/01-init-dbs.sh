#!/bin/bash
set -e

# Function to create database if it doesn't exist
create_database_if_not_exists() {
    local db_name=$1
    if ! psql -U "$POSTGRES_USER" -lqt | cut -d \| -f 1 | grep -qw "$db_name"; then
        echo "Creating database $db_name..."
        createdb -U "$POSTGRES_USER" "$db_name"
    else
        echo "Database $db_name already exists."
    fi
}

echo "Checking for additional databases..."

# Create databases for Zitadel and OpenFGA
create_database_if_not_exists "zitadel"
create_database_if_not_exists "openfga"
