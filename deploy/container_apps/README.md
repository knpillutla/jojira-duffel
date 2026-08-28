# Azure Container Apps (ACA) — Option 2 Build & Deployment Scripts

This module provides dedicated, single-command deployment scripts for Option 2 (**Build Once, Deploy to Dev, and Deploy to Prod**):

```
                                [BUILD STAGE]
                       Builds Docker image artifact ONCE
                                      │
               ┌──────────────────────┴──────────────────────┐
               ▼                                             ▼
    [DEPLOY TO DEV STAGE]                         [DEPLOY TO PROD STAGE]
 Injects envs/dev.env & AKV dev              Injects envs/prod.env & AKV prod
```

---

## Dedicated Scripts Created

| Script | Purpose | Command (PowerShell / Bash) |
| :--- | :--- | :--- |
| **`build_and_deploy_dev`** | Builds image ONCE and deploys to DEV using `envs/dev.env` | `.\build_and_deploy_dev.ps1 -Tag v1.0.0`<br>`./build_and_deploy_dev.sh v1.0.0` |
| **`deploy_prod`** | Deploys pre-built image artifact to PROD using `envs/prod.env` (NO rebuild) | `.\deploy_prod.ps1 -Tag v1.0.0`<br>`./deploy_prod.sh v1.0.0` |
| **`pipeline_dev_to_prod`** | Complete release pipeline: Builds once, deploys to DEV, and promotes to PROD | `.\pipeline_dev_to_prod.ps1 -Tag v1.0.0`<br>`./pipeline_dev_to_prod.sh v1.0.0` |

---

## Directory Structure

```
deploy/container_apps/
├── envs/
│   ├── dev.env                 # Environment variables & names for DEV
│   └── prod.env                # Environment variables & names for PROD
├── build_and_deploy_dev.sh     # Script 1: Build once & deploy to DEV (Bash)
├── build_and_deploy_dev.ps1    # Script 1: Build once & deploy to DEV (PowerShell)
├── deploy_prod.sh              # Script 2: Deploy pre-built image to PROD (Bash)
├── deploy_prod.ps1             # Script 2: Deploy pre-built image to PROD (PowerShell)
├── pipeline_dev_to_prod.sh     # Script 3: End-to-End pipeline DEV -> PROD (Bash)
├── pipeline_dev_to_prod.ps1    # Script 3: End-to-End pipeline DEV -> PROD (PowerShell)
├── deploy.sh                   # Core deployment engine (Bash)
├── deploy.ps1                  # Core deployment engine (PowerShell)
└── README.md                   # Module documentation
```

---

## Execution Guide

### 1. Build and Deploy to DEV Environment
```powershell
.\deploy\container_apps\build_and_deploy_dev.ps1 -Tag v1.0.0
```

### 2. Promote Exact Same Artifact to PROD Environment (No Rebuild)
```powershell
.\deploy\container_apps\deploy_prod.ps1 -Tag v1.0.0
```

### 3. Run Full Release Pipeline (DEV -> PROD in one command)
```powershell
.\deploy\container_apps\pipeline_dev_to_prod.ps1 -Tag v1.0.0
```
