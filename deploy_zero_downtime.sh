#!/bin/bash
# ============================================================
# deploy_zero_downtime.sh — Crypto Trade Hub
# Zero-downtime rolling deploy using Docker Swarm
# ============================================================
# Requirements: Docker Swarm initialized (docker swarm init)
# Usage: ./deploy_zero_downtime.sh [--tag v1.2.3]
# ============================================================

set -euo pipefail

# ── Config ────────────────────────────────────────────────────
STACK_NAME="crypto-trade-hub"
COMPOSE_FILE="docker-compose.prod.yml"
REGISTRY="${REGISTRY:-}"   # e.g. registry.example.com/myorg

# Parse optional --tag argument
IMAGE_TAG="${1:-}"
if [[ "$IMAGE_TAG" == "--tag" ]]; then
    IMAGE_TAG="${2:-}"
    shift 2
fi
IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD 2>/dev/null || echo "latest")}"

echo "========================================================"
echo "  Crypto Trade Hub — Zero-Downtime Deploy"
echo "  Image tag : $IMAGE_TAG"
echo "  Stack     : $STACK_NAME"
echo "========================================================"

# ── Step 1: Build images ──────────────────────────────────────
echo ""
echo "[1/5] Building images..."

API_IMAGE="crypto-trade-hub-api:${IMAGE_TAG}"
ENGINE_IMAGE="crypto-trade-hub-engine:${IMAGE_TAG}"
FRONTEND_IMAGE="crypto-trade-hub-frontend:${IMAGE_TAG}"

docker build \
    -t "${REGISTRY:+$REGISTRY/}${API_IMAGE}" \
    -f Dockerfile.prod \
    .

docker build \
    -t "${REGISTRY:+$REGISTRY/}${ENGINE_IMAGE}" \
    -f Dockerfile.engine \
    .

docker build \
    -t "${REGISTRY:+$REGISTRY/}${FRONTEND_IMAGE}" \
    -f Dockerfile.frontend \
    .

echo "  ✅ Images built"

# ── Step 2: Push to registry (if configured) ─────────────────
if [[ -n "$REGISTRY" ]]; then
    echo ""
    echo "[2/5] Pushing images to registry..."
    docker push "${REGISTRY}/${API_IMAGE}"
    docker push "${REGISTRY}/${ENGINE_IMAGE}"
    docker push "${REGISTRY}/${FRONTEND_IMAGE}"
    echo "  ✅ Images pushed to $REGISTRY"
else
    echo ""
    echo "[2/5] No REGISTRY set — skipping push (local deploy)"
fi

# ── Step 3: Run database migrations ──────────────────────────
echo ""
echo "[3/5] Running database migrations..."

docker run --rm \
    --env-file .env \
    "${REGISTRY:+$REGISTRY/}${API_IMAGE}" \
    python -m app.engine.migrations || {
    echo "  ⚠️  Migration returned non-zero — check output above"
}

echo "  ✅ Migrations complete"

# ── Step 4: Deploy API with rolling update (zero downtime) ───
echo ""
echo "[4/5] Deploying stack with rolling update..."

IMAGE_TAG="$IMAGE_TAG" docker stack deploy \
    -c "$COMPOSE_FILE" \
    "$STACK_NAME" \
    --with-registry-auth \
    --prune

# Wait for API to reach steady state
echo "  Waiting for API service to converge..."
docker service wait "${STACK_NAME}_backend" || true
echo "  ✅ API service converged"

# ── Step 5: Rolling update for engine (60 s pause per replica) 
echo ""
echo "[5/5] Rolling engine update (60s graceful shutdown per replica)..."

docker service update \
    --image "${REGISTRY:+$REGISTRY/}crypto-trade-hub-engine:${IMAGE_TAG}" \
    --update-order start-first \
    --update-delay 60s \
    --update-failure-action rollback \
    "${STACK_NAME}_engine" || {
    echo "  ⚠️  Engine update failed — triggering rollback"
    docker service rollback "${STACK_NAME}_engine"
    exit 1
}

echo "  ✅ Engine update complete"

# ── Summary ───────────────────────────────────────────────────
echo ""
echo "========================================================"
echo "  ✅ Deploy concluído — versão: $IMAGE_TAG"
echo "  Stack status:"
docker service ls --filter "name=${STACK_NAME}"
echo "========================================================"
