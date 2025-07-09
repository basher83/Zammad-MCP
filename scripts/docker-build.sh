#!/bin/bash
# Script to build and test Docker image locally

set -euo pipefail

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check for required tools
command -v docker >/dev/null 2>&1 || { echo -e "${RED}Docker CLI not found – install Docker first.${NC}"; exit 1; }

# Configuration
IMAGE_NAME="zammad-mcp"
REGISTRY="ghcr.io/basher83"
VERSION="${1:-latest}"

echo -e "${YELLOW}Building Docker image: ${REGISTRY}/${IMAGE_NAME}:${VERSION}${NC}"

# Build the image (explicitly target production stage)
echo -e "\n${GREEN}Step 1: Building Docker image...${NC}"
docker build --target production \
             -t "${REGISTRY}/${IMAGE_NAME}:${VERSION}" .

# Test the image
echo -e "\n${GREEN}Step 2: Testing Docker image...${NC}"

# Test Python module import
if ! docker run --rm "${REGISTRY}/${IMAGE_NAME}:${VERSION}" python -c "import mcp_zammad; print('✅ Import test passed')"; then
    echo -e "${RED}❌ Failed to import mcp_zammad module${NC}"
    exit 1
fi

# Test MCP server executable exists
if ! docker run --rm "${REGISTRY}/${IMAGE_NAME}:${VERSION}" sh -c 'command -v mcp-zammad >/dev/null'; then
    echo -e "${RED}❌ MCP server executable not found${NC}"
    exit 1
fi
echo "✅ MCP server executable found"

# Check image size
echo -e "\n${GREEN}Step 3: Image details:${NC}"
docker images "${REGISTRY}/${IMAGE_NAME}:${VERSION}" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"

# Optional: Run security scan with trivy if available
if command -v trivy &> /dev/null; then
    echo -e "\n${GREEN}Step 4: Running security scan...${NC}"
    # Use local cache to speed up repeated scans (minutes -> seconds)
    TRIVY_CACHE="${HOME}/.cache/trivy"
    mkdir -p "${TRIVY_CACHE}"
    echo "Using cache directory: ${TRIVY_CACHE}"
    trivy image --cache-dir "${TRIVY_CACHE}" --severity HIGH,CRITICAL "${REGISTRY}/${IMAGE_NAME}:${VERSION}"
else
    echo -e "\n${YELLOW}Trivy not found. Skipping security scan.${NC}"
    echo "Install with: brew install trivy (macOS) or check https://aquasecurity.github.io/trivy/"
fi

echo -e "\n${GREEN}✅ Docker build completed successfully!${NC}"
echo -e "\nTo run the container:"
echo -e "  docker run -e ZAMMAD_URL=<url> -e ZAMMAD_HTTP_TOKEN=<token> ${REGISTRY}/${IMAGE_NAME}:${VERSION}"
echo -e "\nTo push to registry (requires authentication):"
echo -e "  docker push ${REGISTRY}/${IMAGE_NAME}:${VERSION}"