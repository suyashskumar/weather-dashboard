#!/bin/bash
set -e
ECR_URI="$1"
AWS_REGION="${2:-us-east-1}"

# login to ECR (EC2 must have IAM role or AWS creds/config)
aws ecr get-login-password --region $AWS_REGION \
  | docker login --username AWS --password-stdin ${ECR_URI%/*}

docker stop weather_app || true
docker rm weather_app || true
docker pull ${ECR_URI}
docker run -d --name weather_app -p 80:5000 ${ECR_URI}
