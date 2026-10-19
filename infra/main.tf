terraform {
  required_version = ">= 1.0"
  required_providers {
    kind = {
      source  = "tehcyx/kind"
      version = "~> 0.11.0"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 3.3.0"
    }
  }
}

provider "kind" {}

provider "helm" {
  kubernetes = {
    host                   = kind_cluster.mlops_cluster.endpoint
    cluster_ca_certificate = kind_cluster.mlops_cluster.cluster_ca_certificate
    client_certificate     = kind_cluster.mlops_cluster.client_certificate
    client_key             = kind_cluster.mlops_cluster.client_key
  }
}

resource "kind_cluster" "mlops_cluster" {
  name           = "mlops-cluster"
  wait_for_ready = true

  kind_config {
    kind        = "Cluster"
    api_version  = "kind.x-k8s.io/v1alpha4"

    node {
      role = "control-plane"
      extra_port_mappings {
        container_port = 30000
        host_port      = 5005
        protocol       = "TCP"
      }
    }
  }
}

resource "helm_release" "mlops_stack" {
  name             = "mlops-stack"
  chart            = "./mlops-lab-chart"
  namespace        = "mlops-lab"
  create_namespace = true

  depends_on = [kind_cluster.mlops_cluster]
}
