# Start minikube with enough resources
minikube start --cpus 4 --memory 8192

# Enable necessary addons
minikube addons enable ingress
minikube addons enable metrics-server
```

2. Set up secrets for local development:
```bash
# Create local secrets file from template
cp .env.example .env

# Edit the .env file with your values
# Required values:
# - DATABASE_URL: Your PostgreSQL connection string
# - SESSION_SECRET: A secure random string
# - TELEGRAM_BOT_TOKEN: Your Telegram bot token
# - ADMIN_CHAT_ID: Your Telegram chat ID
nano .env

# Create Kubernetes secret from .env file
kubectl create secret generic app-secrets \
  --from-env-file=.env \
  --namespace=development

# Verify secret creation
kubectl get secrets -n development
kubectl describe secret app-secrets -n development
```

3. Configure local Docker environment:
```bash
# Point your shell to minikube's Docker daemon
eval $(minikube docker-env)  # Unix
minikube docker-env | Invoke-Expression  # Windows PowerShell
```

3. Build local images:
```bash
# Build with local tag
docker build -t price-monitor:local -f Dockerfile --target price-monitor .
docker build -t ml-prediction:local -f Dockerfile --target ml-prediction .
docker build -t pattern-analysis:local -f Dockerfile --target pattern-analysis .
```

### Development Workflow

1. Start local development environment:
```bash
# Apply development configuration
kubectl apply -k k8s/overlays/development

# Port forward services
kubectl port-forward svc/price-monitor-service 5000:80 &
kubectl port-forward svc/ml-prediction-service 5001:80 &
kubectl port-forward svc/pattern-analysis-service 5002:80 &
```

2. Enable hot reloading (with Skaffold):
```bash
# Create skaffold.yaml for development
cat > skaffold.yaml <<EOF
apiVersion: skaffold/v2beta29
kind: Config
build:
  artifacts:
  - image: price-monitor
    context: .
    docker:
      dockerfile: Dockerfile
      target: price-monitor
  - image: ml-prediction
    context: .
    docker:
      dockerfile: Dockerfile
      target: ml-prediction
  - image: pattern-analysis
    context: .
    docker:
      dockerfile: Dockerfile
      target: pattern-analysis
deploy:
  kubectl:
    manifests:
    - k8s/overlays/development/*.yaml
EOF

# Start development with hot reload
skaffold dev
```

### Local Testing

1. Run integration tests:
```bash
# Port-forward test database
kubectl port-forward svc/postgres 5432:5432 &

# Run tests with local configuration
pytest tests/ --kube-config=k8s/overlays/development/config.yaml
```

2. Test individual modules:
```bash
# Get pod name
POD_NAME=$(kubectl get pod -l app=price-monitor -o jsonpath="{.items[0].metadata.name}")

# Execute tests in pod
kubectl exec $POD_NAME -- python -m pytest /app/tests/
```

### Debugging in Kubernetes

1. Enable debug mode:
```bash
# Add debug configuration to deployment
kubectl patch deployment price-monitor -p '{"spec": {"template": {"spec": {"containers": [{"name": "price-monitor", "env": [{"name": "DEBUG", "value": "true"}]}]}}}}'
```

2. Access logs:
```bash
# Stream logs from all modules
kubectl logs -f -l app=price-monitor
kubectl logs -f -l app=ml-prediction
kubectl logs -f -l app=pattern-analysis

# Save logs to file
kubectl logs -l app=price-monitor > price-monitor.log
```

3. Interactive debugging:
```bash
# Start debug shell in pod
kubectl debug -it deployment/price-monitor --image=python:3.11-slim

# Attach debugger
kubectl attach -it deployment/price-monitor
```

### Development Tips

1. Local Registry Setup:
```bash
# Start local registry
minikube addons enable registry
```

2. Resource Monitoring:
```bash
# Monitor resource usage
kubectl top pods
kubectl top nodes
```

3. Development Namespace:
```bash
# Create and use development namespace
kubectl create namespace development
kubectl config set-context --current --namespace=development
```

4. Quick Module Restart:
```bash
# Restart specific deployment
kubectl rollout restart deployment price-monitor
```

### Local Secrets Management

### Setting up Secrets for Local Development

1. Create a `.env` file for local development:
```bash
# Create .env file from example
cp .env.example .env

# Edit .env with your values
nano .env
```

2. Create Kubernetes secrets:
```bash
# Create secrets from .env file
kubectl create secret generic app-secrets \
  --from-env-file=.env \
  --namespace=development

# Verify secrets
kubectl get secrets -n development
kubectl describe secret app-secrets -n development
```

3. Required Secret Keys:
- `DATABASE_URL`: PostgreSQL connection string
- `SESSION_SECRET`: Flask session secret key
- `TELEGRAM_BOT_TOKEN`: Your Telegram bot token
- `OPENWEATHERMAP_API_KEY`: OpenWeatherMap API key
- `ADMIN_CHAT_ID`: Telegram admin chat ID

### Managing Secrets in Development

1. Update existing secrets:
```bash
# Update a specific secret
kubectl create secret generic app-secrets \
  --from-env-file=.env \
  --namespace=development \
  -o yaml --dry-run=client | \
  kubectl replace -f -
```

2. Access secrets in pods:
```bash
# View mounted secrets
kubectl exec -it [pod-name] -- ls /etc/secrets

# Test secret mounting
kubectl exec -it [pod-name] -- env | grep DATABASE_URL
```

3. Secret Best Practices:
- Never commit `.env` files to version control
- Use different secrets for development and production
- Rotate secrets regularly
- Use sealed secrets for production deployments

### Troubleshooting Secrets

1. Verify secret mounting:
```bash
# Check pod environment
kubectl exec [pod-name] -- printenv

# Check secret volumes
kubectl describe pod [pod-name]
```

2. Common Issues:
- Secret not found: Verify namespace and secret name
- Permission issues: Check RBAC configuration
- Invalid values: Verify base64 encoding for binary data

3. Security Notes:
- Keep .env files secure and never share them
- Use different secrets for each environment
- Consider using a secrets management service for production

### Common Issues and Solutions

1. Image Pull Issues:
```bash
# Force local images
kubectl patch deployment price-monitor -p '{"spec": {"template": {"spec": {"imagePullPolicy": "Never"}}}}'
```

2. Resource Constraints:
```bash
# Adjust resource limits for development
kubectl patch deployment price-monitor -p '{"spec": {"template": {"spec": {"containers": [{"name": "price-monitor", "resources": {"limits": {"cpu": "500m", "memory": "512Mi"}, "requests": {"cpu": "250m", "memory": "256Mi"}}}]}}}}'
```

3. Database Connection:
```bash
# Port-forward database locally
kubectl port-forward svc/postgres 5432:5432

# Update connection string
export DATABASE_URL="postgresql://localhost:5432/energy_monitor"
```

### Cleanup

1. Stop all port-forwarding:
```bash
pkill -f "kubectl port-forward"
```

2. Clean up resources:
```bash
# Delete all resources in development namespace
kubectl delete namespace development

# Stop minikube
minikube stop