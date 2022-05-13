
# datapipe

A data processing pipeline that (currently) extracts audio clips from youtube videos and generates two transcription candidates with a Vosk (Kaldi) and a Wav2Vec2 model. The goal of the software is to ease the generation of datasets for ASR by automatically extracting and processing large audio sources.



## Installation

Install k3s

```bash
curl -sfL https://get.k3s.io | sh -s - --write-kubeconfig-mode 644

# Check for Ready node,takes maybe 30 seconds
k3s kubectl get node

#Create alias for Kubectl
KUBECONFIG="~/.kube/config:/etc/rancher/k3s/k3s.yaml"

```

Install kustomize

```bash
  curl -s "https://raw.githubusercontent.com/kubernetes-sigs/kustomize/master/hack/install_kustomize.sh" --output install_kustomize.sh
  chmod  +x install_kustomize.sh
  ./install_kustomize.sh
  sudo mv kustomize /usr/local/bin/ && rm install_kustomize.sh
```


## Setup cluster
```bash
#Create namespace
kubectl create namespace assistent
```

Encode secret password
```bash
#Get BASE64 encoded password
echo -n "password123#$" | base64 -i -
```

Create secret file and paste encoded password (k8s/postgresql/secret.ymal)
```yml
apiVersion: v1
kind: Secret
metadata:
  namespace: assistent
  name: datapipe-db-secret
data:
  POSTGRES_PASSWORD: "cGFzc3dvcmQxMjMjJA=="
```
Apply secret
```bash
kubectl apply -f k8s/postgresql/secret.ymal
```

## Deploy

```bash
make deploy 
  ```

## Database setup

Wait until datapipe-db-0 pod is ready and then do the following steps
```bash
kubectl -n assistent exec -it datapipe-db-0 bash
apt update -y  && apt install -y wget 
wget -O tables.sql https://temu.bsc.es/datapipe/tables.sql
psql -U postgres
  ```

Create database/user and grant privileges
```sql
CREATE DATABASE datapipe;
CREATE USER datapipe WITH ENCRYPTED PASSWORD 'password123#$';
GRANT ALL PRIVILEGES ON DATABASE datapipe TO datapipe;

\c datapipe
\i tables.sql

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO datapipe;
```
Restarts all pods
```bash
kubectl -n assistent rollout restart deploy
```
## Authors

- Ciaran O'Reilly

