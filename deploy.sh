#!/usr/bin/env bash
set -euo pipefail

# Deploy script for Resident Schedule app
# Usage: ./deploy.sh [excel_file] [--service SERVICE_NAME]

SERVICE_NAME="${SERVICE_NAME:-resident-schedule}"
CONTAINER_NAME="resident-schedule"
IMAGE_NAME="weirich.david/resident_schedule:latest"

echo -e "\e[1m\e[34m=== Resident Schedule Deployment ===\e[0m"

# Step 1: Parse schedule if Excel file provided
if [ $# -ge 1 ] && [[ "$1" == *.xlsx || "$1" == *.xlsb ]]; then
    EXCEL_FILE="$1"
    shift
    echo -e "\e[1m\e[34mStep 1: Parsing Excel file...\e[0m"
    poetry run python -m app.parser.cli --file "$EXCEL_FILE" --output resident_schedule.db
    echo -e "\e[1m\e[32mSchedule parsed successfully.\e[0m"
else
    echo -e "\e[1m\e[33mStep 1: Skipping parser (no Excel file provided).\e[0m"
    if [ ! -f resident_schedule.db ]; then
        echo -e "\e[1m\e[31mERROR: No resident_schedule.db found. Provide an Excel file to parse.\e[0m"
        exit 1
    fi
fi

# Step 2: Run tests
echo -e "\e[1m\e[34mStep 2: Running tests...\e[0m"
poetry run pytest
echo -e "\e[1m\e[32mTests passed.\e[0m"

# Step 3: Build Docker image
echo -e "\e[1m\e[34mStep 3: Building Docker image...\e[0m"
docker build --no-cache -t "$IMAGE_NAME" .
echo -e "\e[1m\e[32mDocker image built.\e[0m"

# Step 4: Push to Lightsail
echo -e "\e[1m\e[34mStep 4: Pushing to AWS Lightsail...\e[0m"
aws lightsail push-container-image \
    --service-name "$SERVICE_NAME" \
    --label "$CONTAINER_NAME" \
    --image "$IMAGE_NAME"

# Step 5: Deploy new version
echo -e "\e[1m\e[34mStep 5: Deploying new container...\e[0m"
LIGHTSAIL_IMAGE=$(aws lightsail get-container-images \
    --service-name "$SERVICE_NAME" \
    --query 'containerImages[0].image' \
    --output text)

aws lightsail create-container-service-deployment \
    --service-name "$SERVICE_NAME" \
    --containers "{
        \"$CONTAINER_NAME\": {
            \"image\": \"$LIGHTSAIL_IMAGE\",
            \"ports\": {\"8000\": \"HTTP\"}
        }
    }" \
    --public-endpoint "{
        \"containerName\": \"$CONTAINER_NAME\",
        \"containerPort\": 8000
    }"

echo -e "\e[1m\e[32m=== Deployment complete! ===\e[0m"
echo "Check status: aws lightsail get-container-services --service-name $SERVICE_NAME"
