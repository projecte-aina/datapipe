
# datapipe

A data processing pipeline that (currently) extracts audio clips from youtube videos and generates two transcription candidates with a Vosk (Kaldi) and a Wav2Vec2 model. The goal of the software is to ease the generation of datasets for ASR by automatically extracting and processing large audio sources.



## Installation

Install microk8s

```bash
  sudo snap install microk8s --classic
  sudo usermod -a -G microk8s $USER
  sudo chown -f -R $USER ~/.kube
  newgrp microk8s
  microk8s enable dashboard dns registry istio
```
Create alias for Kubectl

```bash
  sudo snap alias microk8s.kubectl kubectl
```


Install kustomize

```bash
  curl -s "https://raw.githubusercontent.com/kubernetes-sigs/kustomize/master/hack/install_kustomize.sh" --output install_kustomize.sh
  chmod  +x install_kustomize.sh
  ./install_kustomize.sh
  sudo mv kustomize /usr/local/bin/
  rm install_kustomize.sh
```


## Setup 
```bash
#Create namespace
kubectl create namespace assistent

#Get BASE64 encoded password
echo -n "password123#$" | base64 -i -

#Create k8s/postgresql/secret.ymal

apiVersion: v1
kind: Secret
metadata:
  namespace: assistent
  name: datapipe-db-secret
data:
  POSTGRES_PASSWORD: cGFzc3dvcmQxMjMjJA==

#Apply secret
kubectl apply -f k8s/postgresql/secret.ymal

#List of pods
kubectl --namespace assistent  get pods

#Logs 
kubectl --namespace assistent logs preprocessor-

```
## Deploy

```bash
  make deploy 
  ```

## Authors

- Ciaran O'Reilly



