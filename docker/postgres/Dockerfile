# ./docker/postgres/Dockerfile

FROM postgres:15-alpine

# Optional: install extra packages or extensions
# RUN apk add --no-cache postgresql-contrib

# Copy init script (if needed)
COPY init-db.sh /docker-entrypoint-initdb.d/init-db.sh
