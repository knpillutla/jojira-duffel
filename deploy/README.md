# Jojira Duffel — Azure ACR, AKS & ArgoCD Deployment Pipeline

This directory contains automated scripts and Kubernetes manifests to build Docker images, push them to **Azure Container Registry (ACR)**, manage secrets with **Azure Key Vault**, and continuously deploy using **ArgoCD GitOps** on **Azure Kubernetes Service (AKS)**.

---

## Directory Structure

```
deploy/
├── config.env                    # Central variables file (ACR, Key Vault, AKS, Resource Group, Subscription)
├── build_and_push.sh             # Bash script to build and push Docker images to Azure ACR
├── build_and_push.ps1            # PowerShell script to build and push Docker images to Azure ACR
├── deploy_argocd.sh              # Bash script to connect to AKS & register ArgoCD GitOps application
├── deploy_argocd.ps1             # PowerShell script to connect to AKS & register ArgoCD Application
├── k8s/                          # Kubernetes Manifests (synced by ArgoCD)
│   ├── configmap.yaml            # Environment non-sensitive configuration
│   ├── secretproviderclass.yaml  # Azure Key Vault Secrets Store CSI Driver config
│   ├── api-deployment.yaml       # Duffel REST API Deployment (Replicas: 2)
│   ├── user-service-deployment.yaml # User Service Deployment (Replicas: 2)
│   ├── processor-deployment.yaml # Order Processor Worker Deployment (Replicas: 1)
│   └── services.yaml             # Kubernetes Services (ClusterIP)
└── argocd/
    └── application.yaml          # ArgoCD Application CRD manifest
```

---

## Prerequisites & One-Time Setup

1. **Azure CLI (`az`) & `kubectl`**: Installed and logged in (`az login`).
2. **Docker**: Installed and running locally.
3. **Azure Infrastructure**:
   - Azure Resource Group
   - Azure Container Registry (ACR)
   - Azure Kubernetes Service (AKS) cluster attached to ACR (`az aks update --attach-acr <ACR_NAME>`)
   - Azure Key Vault containing secrets (`duffel-api-token`, `openai-api-key`, `postgres-password`, etc.)

---

## Do We Need a Git Repo for ArgoCD Deploy?

**YES!** ArgoCD operates on the **GitOps principle**.
- ArgoCD runs inside your AKS cluster and continuously monitors a Git repository (e.g. `https://github.com/knpillutla/jojira-duffel.git`).
- It syncs the Kubernetes manifests located in the `deploy/k8s/` directory directly into your cluster.
- When you update image tags or manifests in Git, ArgoCD automatically performs a zero-downtime rolling update on AKS.

---

## Step-by-Step Deployment Instructions

### Step 1: Configure Your Azure Variables
Edit `deploy/config.env` and plug in your Azure details:

```bash
AZURE_SUBSCRIPTION_ID="your-subscription-id"
AZURE_RESOURCE_GROUP="rg-jojira-prod"
AZURE_ACR_NAME="jojiraacr"
AZURE_AKS_CLUSTER="jojira-aks"
AZURE_KEYVAULT_NAME="jojira-kv"
AZURE_TENANT_ID="your-tenant-id"

ARGOCD_GIT_REPO_URL="https://github.com/knpillutla/jojira-duffel.git"
```

---

### Step 2: Build & Push Images to Azure ACR

#### Linux / macOS:
```bash
chmod +x deploy/*.sh
./deploy/build_and_push.sh
```

#### Windows PowerShell:
```powershell
.\deploy\build_and_push.ps1
```

---

### Step 3: Register & Sync with ArgoCD

#### Linux / macOS:
```bash
./deploy/deploy_argocd.sh
```

#### Windows PowerShell:
```powershell
.\deploy\deploy_argocd.ps1
```

---

## Verification Commands

Check ArgoCD deployment status in AKS:
```bash
kubectl get application jojira-duffel-app -n argocd
kubectl get pods -n jojira
kubectl get svc -n jojira
```
