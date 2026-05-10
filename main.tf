provider "google" {
  project = var.project_id
  region  = var.location
}

variable "project_id" {
  type        = string
  description = "The Google Cloud project ID"
}

variable "project_number" {
  type        = string
  description = "The Google Cloud project number"
}

variable "location" {
  type        = string
  default     = "us-central1"
  description = "The location for resources"
}

# API 활성화
resource "google_project_service" "vertexai" {
  service = "aiplatform.googleapis.com"
  disable_on_destroy = false
}

# 에이전트 엔진 서비스 계정에 권한 부여
resource "google_project_iam_member" "reasoning_engine_viewer" {
  project = var.project_id
  role    = "roles/aiplatform.viewer"
  member  = "serviceAccount:service-${var.project_number}@gcp-sa-aiplatform-re.iam.gserviceaccount.com"

  depends_on = [google_project_service.vertexai]
}
