# Weather Dashboard — CI/CD with Jenkins, Docker, and AWS EC2 + ECR

A full-stack weather dashboard deployed with a fully automated CI/CD pipeline using **Jenkins**, **Docker**, and **AWS (ECR + EC2)**.  
This project demonstrates how to containerize a web app, store it on AWS ECR, and automatically deploy new builds to an EC2 instance.

---

## Architecture Overview

**Local → GitHub → Jenkins → AWS ECR → EC2 (Docker Run)**

1. **Developer Workflow:**
   - Code is committed and pushed to **GitHub**.
   - GitHub acts as the **SCM (Source Code Management)** system.

2. **CI (Continuous Integration) — Jenkins:**
   - Jenkins automatically checks out the latest code from GitHub.
   - Builds the Docker image.
   - Pushes the image to **Amazon Elastic Container Registry (ECR)**.

3. **CD (Continuous Deployment):**
   - Jenkins connects to an **EC2 instance** via SSH.
   - It pulls the latest image from ECR.
   - Deploys and runs it inside Docker on EC2.

4. **Result:**
   - The weather dashboard is live on your EC2 public IP (`http://<ec2-public-ip>`).

---

## Components

| Component | Purpose |
|------------|----------|
| **GitHub Repo** | Hosts the application source code and `Jenkinsfile`. |
| **Docker** | Containerizes the app for consistent deployment. |
| **AWS ECR** | Stores the Docker images built by Jenkins. |
| **AWS EC2** | Hosts and runs the live application. |
| **Jenkins** | Manages the full CI/CD pipeline. |

---

## Tech Stack

- **Frontend:** HTML, CSS, JS (Weather dashboard UI)
- **Backend:** Flask (Python)
- **CI/CD:** Jenkins Pipeline (Declarative)
- **Infrastructure:** AWS EC2, ECR
- **Containerization:** Docker

---

## Jenkins Pipeline Stages

### 1️⃣ Checkout
Fetches the latest code from GitHub using Jenkins’ SCM configuration.

### 2️⃣ Get AWS Account
Retrieves AWS account ID using `aws sts get-caller-identity`.

### 3️⃣ Login to ECR
Authenticates Jenkins to AWS ECR using IAM credentials.

### 4️⃣ Build Docker Image
Builds the Docker image locally inside Jenkins from the `Dockerfile`.

### 5️⃣ Tag & Push to ECR
Tags the image with the Jenkins build number and pushes it to ECR.

### 6️⃣ Resolve EC2 IP
Finds the public IP of a running EC2 instance (tagged as `weather-new`) using AWS CLI.

### 7️⃣ Deploy to EC2
SSHs into the EC2 instance, pulls the latest ECR image, and runs it using Docker.

---

## Jenkins Credentials Setup

| ID | Type | Description |
|----|------|-------------|
| `aws-creds` | Username + Password | Your AWS Access Key ID and Secret Access Key. |
| `ec2-ssh` | SSH Username with Private Key | EC2 login credentials (`ubuntu` + PEM key content). |
| (Optional) GitHub credentials | Username + Token | Needed if the repo is private. |

---

## Environment Variables (Jenkinsfile)

| Variable | Description | Example |
|-----------|--------------|---------|
| `AWS_REGION` | AWS region where EC2 and ECR are hosted | `eu-north-1` |
| `ECR_REPO` | Name of your ECR repository | `weather-dashboard` |
| `AWS_ACCOUNT_ID` | Automatically resolved AWS account ID | `491519648367` |
| `EC2_HOST` | Public IP of EC2 (auto-detected by pipeline) | e.g. `16.170.229.87` |

---

## Docker Commands (for local testing)

```bash
# Build locally
docker build -t weather-dashboard .

# Run locally
docker run -d -p 5000:5000 weather-dashboard
```

---

## Visualization

+------------------+
|  Developer Push  |
+--------+---------+
         |
         v
+------------------+
|    GitHub Repo   |
+--------+---------+
         |
         v
+------------------+
| Jenkins Pipeline |
+--------+---------+
         |
         v
+--------------------------+
|  AWS ECR (Image Store)   |
+--------+-----------------+
         |
         v
+--------------------------+
| AWS EC2 (Deployed App)   |
+--------------------------+

---

## Accessing the App

http://<EC2-Public-IP>

# Access locally
http://localhost:5000
