variable "IMAGE_NAME" {
  default = "rasa/rasa"
}

variable "IMAGE_TAG" {
  default = "dev"
}

variable "IMAGE_VERSION" {
  default = "dev"
}

variable "BASE_IMAGE_HASH" {
  default = "dev"
}

variable "BASE_MITIE_IMAGE_HASH" {
  default = "dev"
}

variable "BASE_BUILDER_IMAGE_HASH" {
  default = "dev"
}

# keep this in sync with the version in .github/poetry_version.txt
# the variable is set automatically for builds in CI
variable "POETRY_VERSION" {
  default = "1.4.2"
}

group "base-images" {
  targets = ["base", "base-poetry", "base-mitie"]
}

target "base" {
  dockerfile = "docker/Dockerfile.base"
  tags       = ["${IMAGE_NAME}:base-${IMAGE_TAG}"]
  cache-to   = ["type=inline"]
}

target "base-mitie" {
  dockerfile = "docker/Dockerfile.base-mitie"
  tags       = ["${IMAGE_NAME}:base-mitie-${IMAGE_TAG}"]
  cache-to   = ["type=inline"]
}

target "base-poetry" {
  dockerfile = "docker/Dockerfile.base-poetry"
  tags       = ["${IMAGE_NAME}:base-poetry-${POETRY_VERSION}"]

  args = {
    IMAGE_BASE_NAME = "${IMAGE_NAME}"
    BASE_IMAGE_HASH = "${BASE_IMAGE_HASH}"
    POETRY_VERSION  = "${POETRY_VERSION}"
  }

  cache-to = ["type=inline"]

  cache-from = [
    "type=registry,ref=${IMAGE_NAME}:base-poetry-${POETRY_VERSION}",
  ]
}

target "base-builder" {
  dockerfile = "docker/Dockerfile.base-builder"
  tags       = ["${IMAGE_NAME}:base-builder-${IMAGE_TAG}"]

  args = {
    IMAGE_BASE_NAME = "${IMAGE_NAME}"
    POETRY_VERSION  = "${POETRY_VERSION}"
  }

  cache-to = ["type=inline"]
}

target "default" {
  dockerfile = "Dockerfile"
  tags       = ["${IMAGE_NAME}:${IMAGE_TAG}"]

  args = {
    IMAGE_BASE_NAME         = "${IMAGE_NAME}"
    BASE_IMAGE_HASH         = "${BASE_IMAGE_HASH}"
    BASE_BUILDER_IMAGE_HASH = "${BASE_BUILDER_IMAGE_HASH}"
  }

  cache-to = ["type=inline"]

  cache-from = [
    "type=registry,ref=${IMAGE_NAME}:base-${BASE_IMAGE_HASH}",
    "type=registry,ref=${IMAGE_NAME}:base-builder-${BASE_BUILDER_IMAGE_HASH}",
    "type=registry,ref=${IMAGE_NAME}:latest",
  ]
}

target "full" {
  dockerfile = "docker/Dockerfile.full"
  tags       = ["${IMAGE_NAME}:${IMAGE_TAG}-full"]

  args = {
    IMAGE_BASE_NAME         = "${IMAGE_NAME}"
    BASE_IMAGE_HASH         = "${BASE_IMAGE_HASH}"
    BASE_MITIE_IMAGE_HASH   = "${BASE_MITIE_IMAGE_HASH}"
    BASE_BUILDER_IMAGE_HASH = "${BASE_BUILDER_IMAGE_HASH}"
  }

  cache-to = ["type=inline"]

  cache-from = [
    "type=registry,ref=${IMAGE_NAME}:base-${BASE_IMAGE_HASH}",
    "type=registry,ref=${IMAGE_NAME}:base-builder-${BASE_BUILDER_IMAGE_HASH}",
    "type=registry,ref=${IMAGE_NAME}:latest-full",
  ]
}

# FIXME: lonycell begin >>> 2024-04-08
target "dialog-ai" {
  dockerfile = "docker/Dockerfile.dialog-ai"
  tags       = ["${IMAGE_NAME}:${IMAGE_VERSION}"]

  args = {
    IMAGE_BASE_NAME         = "${IMAGE_NAME}"
    IMAGE_VERSION           = "${IMAGE_VERSION}"
    BASE_IMAGE_HASH         = "${BASE_IMAGE_HASH}"
    BASE_MITIE_IMAGE_HASH   = "${BASE_MITIE_IMAGE_HASH}"
    BASE_BUILDER_IMAGE_HASH = "${BASE_BUILDER_IMAGE_HASH}"
  }

  cache-to = ["type=inline"]

  cache-from = [
    "type=registry,ref=${IMAGE_NAME}:base-${BASE_IMAGE_HASH}",
    "type=registry,ref=${IMAGE_NAME}:base-builder-${BASE_BUILDER_IMAGE_HASH}",
  ]
}

target "rasa-addons" {
  dockerfile = "docker/Dockerfile.rasa-addons"
  tags       = ["${IMAGE_NAME}:${IMAGE_TAG}-rasa-addons"]

  args = {
    IMAGE_BASE_NAME         = "${IMAGE_NAME}"
    BASE_IMAGE_HASH         = "${BASE_IMAGE_HASH}"
    BASE_MITIE_IMAGE_HASH   = "${BASE_MITIE_IMAGE_HASH}"
    BASE_BUILDER_IMAGE_HASH = "${BASE_BUILDER_IMAGE_HASH}"
  }

  cache-to = ["type=inline"]

  cache-from = [
    "type=registry,ref=${IMAGE_NAME}:base-${BASE_IMAGE_HASH}",
    "type=registry,ref=${IMAGE_NAME}:base-builder-${BASE_BUILDER_IMAGE_HASH}",
    "type=registry,ref=${IMAGE_NAME}:latest-rasa-addons",
  ]
}
# FIXME: lonycell end <<< 2024-04-08

target "mitie-en" {
  dockerfile = "docker/Dockerfile.pretrained_embeddings_mitie_en"
  tags       = ["${IMAGE_NAME}:${IMAGE_TAG}-mitie-en"]

  args = {
    IMAGE_BASE_NAME         = "${IMAGE_NAME}"
    BASE_IMAGE_HASH         = "${BASE_IMAGE_HASH}"
    BASE_MITIE_IMAGE_HASH   = "${BASE_MITIE_IMAGE_HASH}"
    BASE_BUILDER_IMAGE_HASH = "${BASE_BUILDER_IMAGE_HASH}"
  }

  cache-to = ["type=inline"]

  cache-from = [
    "type=registry,ref=${IMAGE_NAME}:base-${BASE_IMAGE_HASH}",
    "type=registry,ref=${IMAGE_NAME}:base-mitie-${BASE_MITIE_IMAGE_HASH}",
    "type=registry,ref=${IMAGE_NAME}:base-builder-${BASE_BUILDER_IMAGE_HASH}",
    "type=registry,ref=${IMAGE_NAME}:latest-mitie-en",
  ]
}

target "spacy-de" {
  dockerfile = "docker/Dockerfile.pretrained_embeddings_spacy_de"
  tags       = ["${IMAGE_NAME}:${IMAGE_TAG}-spacy-de"]

  args = {
    IMAGE_BASE_NAME         = "${IMAGE_NAME}"
    BASE_IMAGE_HASH         = "${BASE_IMAGE_HASH}"
    BASE_BUILDER_IMAGE_HASH = "${BASE_BUILDER_IMAGE_HASH}"
  }

  cache-to = ["type=inline"]

  cache-from = [
    "type=registry,ref=${IMAGE_NAME}:base-${BASE_IMAGE_HASH}",
    "type=registry,ref=${IMAGE_NAME}:base-builder-${BASE_BUILDER_IMAGE_HASH}",
    "type=registry,ref=${IMAGE_NAME}:latest-spacy-de",
  ]
}

target "spacy-it" {
  dockerfile = "docker/Dockerfile.pretrained_embeddings_spacy_it"
  tags       = ["${IMAGE_NAME}:${IMAGE_TAG}-spacy-it"]

  args = {
    IMAGE_BASE_NAME         = "${IMAGE_NAME}"
    BASE_IMAGE_HASH         = "${BASE_IMAGE_HASH}"
    BASE_BUILDER_IMAGE_HASH = "${BASE_BUILDER_IMAGE_HASH}"
  }

  cache-to = ["type=inline"]

  cache-from = [
    "type=registry,ref=${IMAGE_NAME}:base-${BASE_IMAGE_HASH}",
    "type=registry,ref=${IMAGE_NAME}:base-builder-${BASE_BUILDER_IMAGE_HASH}",
    "type=registry,ref=${IMAGE_NAME}:latest-spacy-it",
  ]
}

target "spacy-en" {
  dockerfile = "docker/Dockerfile.pretrained_embeddings_spacy_en"
  tags       = ["${IMAGE_NAME}:${IMAGE_TAG}-spacy-en"]

  args = {
    IMAGE_BASE_NAME         = "${IMAGE_NAME}"
    BASE_IMAGE_HASH         = "${BASE_IMAGE_HASH}"
    BASE_BUILDER_IMAGE_HASH = "${BASE_BUILDER_IMAGE_HASH}"
  }

  cache-to = ["type=inline"]

  cache-from = [
    "type=registry,ref=${IMAGE_NAME}:base-${BASE_IMAGE_HASH}",
    "type=registry,ref=${IMAGE_NAME}:base-builder-${BASE_BUILDER_IMAGE_HASH}",
    "type=registry,ref=${IMAGE_NAME}:latest-spacy-en",
  ]
}
