# Build rasa-core docker image

### 1. Change docker image name and tag
- open root/Makefile
- find make target 'ai'
- change image name: IMAGE_NAME=hmaas/rasa-core
- change image tag: IMAGE_VERSION=v3.7.0-dev

### 2. Make docker image
```
> make ai
```
- Result
```bash
(3.10) $ docker images
REPOSITORY               TAG                 IMAGE ID       CREATED              SIZE
hmaas/rasa-core          v3.7.0-dev          929c36069228   About a minute ago   3.26GB
...
botfront/duckling        latest              257be8a3f16c   3 years ago          120MB
```

### 3. Push docker image to dockerhub
```bash
> docker tag hmaas/rasa-core:v3.7.0-dev hmaas/rasa-core:v3.7.0
> docker push hmaas/rasa-core:v3.7.0
```

### 4. Copy and prepaire 'Agent' folder
- find 'agent' folder: current folders are
  ```
  .
  ..
  > agent <--- * THIS is agent folder *
  > binder
  > changelog
  > data
  > docker
  > rasa
  > rasa_addons
  > ...
  > ...
  ```

# Run agent
- this folder mainly contains "docker-compose.yml" file.
- edit '.env' file as you whish.
- run this agent as docker containers
  ```bash
  > docker-compose up -d
  ```
- you can show the log as like this
  ```bash
    Network agent-20240411_botfront-network  Created
    Container botfront-rasa  Creating
    Container botfront-duckling  Created
    Container botfront-actions  Created
    Container botfront-rasa  Created
    Container botfront-mongo  Created
    Container botfront-app  Created
    Attaching to botfront-actions, botfront-app, botfront-duckling, botfront-mongo, botfront-rasa
    botfront-actions   | 2024-04-11 01:32:46 INFO     rasa_sdk.endpoint  - Starting action endpoint server...
    
    ...
    ...
  ```