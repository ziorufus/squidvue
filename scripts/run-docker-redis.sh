#!/bin/bash

sudo docker run -d \
  --name quiz-redis \
  -p 6379:6379 \
  redis
