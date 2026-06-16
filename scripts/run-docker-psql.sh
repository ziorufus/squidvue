#!/bin/bash

source .env

sudo docker run -d \
  --name quiz-postgres \
  -e POSTGRES_USER=${PG_USER} \
  -e POSTGRES_PASSWORD=${PG_PASS} \
  -e POSTGRES_DB=${PG_DB} \
  -p 5433:5432 \
  -v ${PG_DATA}:/var/lib/postgresql/data \
  postgres:16
