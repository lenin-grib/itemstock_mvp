#!/bin/bash

# Script to setup microk8s for deployment
# This script should be run on the microk8s host

set -e

NAMESPACE="itemstock"
GITHUB_USERNAME="${1:-}"
GITHUB_TOKEN="${2:-}"

if [ -z "$GITHUB_USERNAME" ] || [ -z "$GITHUB_TOKEN" ]; then
    echo "Usage: $0 <github_username> <github_token>"
    echo ""
    echo "GitHub token should have read:packages permission"
    exit 1
fi

echo "Setting up microk8s for itemstock deployment..."

# Enable required addons
echo "Enabling required microk8s addons..."
microk8s enable dns storage ingress

# Create namespace
echo "Creating namespace $NAMESPACE..."
microk8s kubectl create namespace $NAMESPACE --dry-run=client -o yaml | microk8s kubectl apply -f -

# Create docker registry secret for GitHub Container Registry
echo "Creating GitHub Container Registry secret..."
microk8s kubectl create secret docker-registry ghcr-secret \
    --docker-server=ghcr.io \
    --docker-username=$GITHUB_USERNAME \
    --docker-password=$GITHUB_TOKEN \
    --docker-email=$GITHUB_USERNAME@users.noreply.github.com \
    -n $NAMESPACE \
    --dry-run=client -o yaml | microk8s kubectl apply -f -

echo "✓ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Set GitHub Secrets in your repository:"
echo "   - MICROK8S_HOST: IP or hostname of your microk8s server"
echo "   - MICROK8S_USER: SSH user for microk8s server"
echo "   - MICROK8S_KEY: Private SSH key (base64 encoded)"
echo "   - MICROK8S_KUBECONFIG: kubeconfig file (base64 encoded)"
echo ""
echo "2. Get kubeconfig (base64 encoded):"
echo "   cat /var/snap/microk8s/current/credentials/client.config | base64"
echo ""
echo "3. Push changes to GitHub to trigger deployment"
