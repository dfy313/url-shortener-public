#!/bin/bash

# Step 1: Update and install Docker
apt-get update -y
apt-get install -y docker.io

# Step 2: Enable and start Docker
systemctl enable docker
systemctl start docker

# Step 3: Pull and run your Docker image
docker pull <PASTE_YOUR_DOCKERHUB_USERNAME>/url-shortener-read
docker run -d -p 5000:5000 <PASTE_YOUR_DOCKERHUB_USERNAME>/url-shortener-read
