#!/usr/bin/env bash
set -euo pipefail

# Deploy script for Resident Schedule app
#
# Usage:
#   ./deploy.sh setup                    — one-time: create Lightsail service + TLS cert
#   ./deploy.sh attach-domain            — one-time: attach custom domain after DNS validation
#   ./deploy.sh [excel_file.xlsx]        — recurring: parse, test, build, push, deploy
#   ./deploy.sh status                   — check service status
#   ./deploy.sh teardown-eb              — remove old Elastic Beanstalk environment

SERVICE_NAME="${SERVICE_NAME:-resident-schedule}"
CONTAINER_NAME="resident-schedule"
IMAGE_NAME="weirich.david/resident_schedule:latest"
DOMAIN="osuresidentschedule.com"
REGION="${AWS_REGION:-us-east-1}"

blue()  { echo -e "\e[1m\e[34m$*\e[0m"; }
green() { echo -e "\e[1m\e[32m$*\e[0m"; }
yellow(){ echo -e "\e[1m\e[33m$*\e[0m"; }
red()   { echo -e "\e[1m\e[31m$*\e[0m"; }

# ---------------------------------------------------------------------------
# setup: one-time Lightsail infrastructure creation
# ---------------------------------------------------------------------------
cmd_setup() {
    blue "=== Lightsail Setup ==="

    # 1. Create container service
    blue "Step 1: Creating Lightsail container service..."
    if aws lightsail get-container-services --service-name "$SERVICE_NAME" &>/dev/null; then
        yellow "Service '$SERVICE_NAME' already exists, skipping creation."
    else
        aws lightsail create-container-service \
            --service-name "$SERVICE_NAME" \
            --power nano \
            --scale 1 \
            --region "$REGION"
        green "Container service created."
        echo "Waiting for service to become active (this can take a few minutes)..."
        aws lightsail wait container-service-active --service-name "$SERVICE_NAME" 2>/dev/null || \
            echo "  (wait command not available — check manually with: ./deploy.sh status)"
    fi

    # 2. Create TLS certificate
    blue "Step 2: Creating TLS certificate for $DOMAIN..."
    CERT_EXISTS=$(aws lightsail get-certificates \
        --query "certificates[?domainName=='$DOMAIN'].certificateName" \
        --output text 2>/dev/null || echo "")

    if [ -n "$CERT_EXISTS" ] && [ "$CERT_EXISTS" != "None" ]; then
        yellow "Certificate for $DOMAIN already exists: $CERT_EXISTS"
    else
        aws lightsail create-certificate \
            --certificate-name "${SERVICE_NAME}-cert" \
            --domain-name "$DOMAIN" \
            --subject-alternative-names "www.$DOMAIN"
        green "Certificate created."
    fi

    # 3. Show DNS validation records
    blue "Step 3: DNS validation records for GoDaddy"
    echo ""
    echo "Add these CNAME records in GoDaddy DNS to validate the certificate:"
    echo ""
    aws lightsail get-certificates \
        --certificate-name "${SERVICE_NAME}-cert" \
        --query "certificates[0].certificateDetail.domainValidationRecords[].{Host:resourceRecord.name,Value:resourceRecord.value}" \
        --output table 2>/dev/null || {
            yellow "Could not fetch records yet — the certificate may still be initializing."
            echo "Run this to check manually:"
            echo "  aws lightsail get-certificates --certificate-name ${SERVICE_NAME}-cert"
        }
    echo ""
    echo "In GoDaddy: DNS → Add Record → Type: CNAME → Host and Value from above."
    echo "(For Host, remove the trailing '.osuresidentschedule.com.' — GoDaddy adds it automatically.)"
    echo ""
    echo "After adding the records, wait for validation (usually 5-15 minutes), then run:"
    echo ""
    echo "  ./deploy.sh attach-domain"
    echo ""
}

# ---------------------------------------------------------------------------
# attach-domain: attach custom domain after cert validation
# ---------------------------------------------------------------------------
cmd_attach_domain() {
    blue "=== Attaching Custom Domain ==="

    # Check cert status
    CERT_STATUS=$(aws lightsail get-certificates \
        --certificate-name "${SERVICE_NAME}-cert" \
        --query "certificates[0].certificateDetail.status" \
        --output text 2>/dev/null || echo "UNKNOWN")

    if [ "$CERT_STATUS" = "ISSUED" ]; then
        green "Certificate is validated and issued."
    else
        red "Certificate status: $CERT_STATUS"
        echo "The certificate must be in ISSUED status before attaching the domain."
        echo "Make sure the DNS validation CNAME records are added in GoDaddy."
        echo ""
        echo "Check status with:"
        echo "  aws lightsail get-certificates --certificate-name ${SERVICE_NAME}-cert"
        exit 1
    fi

    # Enable custom domain on the container service
    blue "Enabling custom domain on container service..."
    aws lightsail update-container-service \
        --service-name "$SERVICE_NAME" \
        --public-domain-names "certificateName=${SERVICE_NAME}-cert,domainNames=$DOMAIN,www.$DOMAIN"

    green "Custom domain attached!"
    echo ""
    echo "Final step: Update your GoDaddy DNS records."
    echo ""

    # Get the Lightsail default URL
    DEFAULT_URL=$(aws lightsail get-container-services \
        --service-name "$SERVICE_NAME" \
        --query "containerServices[0].url" \
        --output text 2>/dev/null || echo "<check-lightsail-console>")

    echo "In GoDaddy DNS manager for $DOMAIN:"
    echo ""
    echo "  1. Delete any existing A record or CNAME for @ (root domain)"
    echo "  2. Add a CNAME record:"
    echo "       Host:  @"
    echo "       Value: $DEFAULT_URL"
    echo ""
    echo "  3. Add/update CNAME for www:"
    echo "       Host:  www"
    echo "       Value: $DEFAULT_URL"
    echo ""
    echo "Note: GoDaddy may not allow CNAME on the root domain (@)."
    echo "If so, use GoDaddy's 'Forwarding' feature to forward @ to www.$DOMAIN,"
    echo "and point the www CNAME to the Lightsail URL above."
    echo ""
    echo "DNS propagation usually takes a few minutes but can take up to an hour."
}

# ---------------------------------------------------------------------------
# status: check current service state
# ---------------------------------------------------------------------------
cmd_status() {
    blue "=== Service Status ==="
    aws lightsail get-container-services \
        --service-name "$SERVICE_NAME" \
        --query "containerServices[0].{State:state,Power:power,Scale:scale,URL:url,IsDisabled:isDisabled}" \
        --output table

    echo ""
    blue "Current deployment:"
    aws lightsail get-container-service-deployments \
        --service-name "$SERVICE_NAME" \
        --query "deployments[0].{State:state,Version:version,CreatedAt:createdAt}" \
        --output table 2>/dev/null || echo "  No deployments yet."

    echo ""
    blue "Certificate status:"
    aws lightsail get-certificates \
        --certificate-name "${SERVICE_NAME}-cert" \
        --query "certificates[0].certificateDetail.{Status:status,Domain:domainName}" \
        --output table 2>/dev/null || echo "  No certificate found."
}

# ---------------------------------------------------------------------------
# teardown-eb: remove old Elastic Beanstalk resources
# ---------------------------------------------------------------------------
cmd_teardown_eb() {
    yellow "=== Elastic Beanstalk Teardown ==="
    echo ""
    echo "This will terminate your EB environment. Make sure:"
    echo "  1. The Lightsail deployment is working"
    echo "  2. DNS has been updated to point to Lightsail"
    echo "  3. You've verified https://$DOMAIN loads from Lightsail"
    echo ""
    read -p "Type 'yes' to proceed: " confirm
    if [ "$confirm" != "yes" ]; then
        echo "Aborted."
        exit 0
    fi

    echo "Listing EB environments..."
    aws elasticbeanstalk describe-environments \
        --query "Environments[].{Name:EnvironmentName,Status:Status,URL:CNAME}" \
        --output table

    echo ""
    read -p "Enter the environment name to terminate: " env_name
    aws elasticbeanstalk terminate-environment --environment-name "$env_name"
    green "EB environment '$env_name' termination initiated."
}

# ---------------------------------------------------------------------------
# deploy: the main recurring workflow
# ---------------------------------------------------------------------------
cmd_deploy() {
    blue "=== Resident Schedule Deployment ==="

    # Step 1: Parse schedule if Excel file provided
    if [ $# -ge 1 ] && [[ "$1" == *.xlsx || "$1" == *.xlsb ]]; then
        EXCEL_FILE="$1"
        blue "Step 1: Parsing Excel file..."
        poetry run python -m app.parser.cli --file "$EXCEL_FILE" --output resident_schedule.db
        green "Schedule parsed successfully."
    else
        yellow "Step 1: Skipping parser (no Excel file provided)."
        if [ ! -f resident_schedule.db ]; then
            red "ERROR: No resident_schedule.db found. Provide an Excel file to parse."
            exit 1
        fi
    fi

    # Step 2: Run tests
    blue "Step 2: Running tests..."
    poetry run pytest
    green "Tests passed."

    # Step 3: Build Docker image
    blue "Step 3: Building Docker image..."
    docker build --no-cache -t "$IMAGE_NAME" .
    green "Docker image built."

    # Step 4: Push to Lightsail
    blue "Step 4: Pushing to AWS Lightsail..."
    aws lightsail push-container-image \
        --service-name "$SERVICE_NAME" \
        --label "$CONTAINER_NAME" \
        --image "$IMAGE_NAME"

    # Step 5: Deploy new version
    blue "Step 5: Deploying new container..."
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

    green "=== Deployment complete! ==="
    echo "Check status: ./deploy.sh status"
}

# ---------------------------------------------------------------------------
# main: route subcommands
# ---------------------------------------------------------------------------
case "${1:-}" in
    setup)
        cmd_setup
        ;;
    attach-domain)
        cmd_attach_domain
        ;;
    status)
        cmd_status
        ;;
    teardown-eb)
        cmd_teardown_eb
        ;;
    help|--help|-h)
        echo "Usage:"
        echo "  ./deploy.sh setup                 — create Lightsail service + TLS cert"
        echo "  ./deploy.sh attach-domain         — attach custom domain after DNS validation"
        echo "  ./deploy.sh [schedule.xlsx]        — parse, test, build, push, deploy"
        echo "  ./deploy.sh status                — check service status"
        echo "  ./deploy.sh teardown-eb           — remove old Elastic Beanstalk environment"
        ;;
    *)
        cmd_deploy "$@"
        ;;
esac
