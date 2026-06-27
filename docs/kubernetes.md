# Kubernetes Deployment

The deployment uses namespace `vtlib`; the manifests do not create it.

Generate kustomize inputs from `.env`:

```sh
python3 scripts/render_k8s_env.py
```

This writes ignored files under `k8s/generated/`:

- `config.env`: non-sensitive runtime config.
- `secret.env`: Alma API key and MCP bearer token.
- `dockerconfigjson`: registry pull secret material.
- `deployment-image-patch.yaml`: image reference from `MCP_IMAGE`.
- `ingress-patch.yaml`: host and path from `MCP_URL`.

Preview:

```sh
kubectl --kubeconfig endeavour.yaml -n vtlib kustomize k8s
```

Deploy:

```sh
kubectl --kubeconfig endeavour.yaml apply -k k8s
```

Check rollout:

```sh
kubectl --kubeconfig endeavour.yaml -n vtlib rollout status deployment/alma-mcp
kubectl --kubeconfig endeavour.yaml -n vtlib get pods,svc,ingress -l app.kubernetes.io/name=alma-mcp
```

If `MCP_URL` contains a path prefix, the app accepts requests with that
prefix and also continues to answer internal probe paths without the prefix.
