packer {
  required_plugins {
    proxmox = {
      version = ">= 1.1.3"
      source  = "github.com/hashicorp/proxmox"
    }
  }
}

# ── Variables ────────────────────────────────────────────────────────────────
variable "proxmox_url"          { type = string }
variable "proxmox_username"     { type = string }
variable "proxmox_password"     { type = string sensitive = true }
variable "proxmox_node"         { type = string default = "pve" }
variable "proxmox_storage"      { type = string default = "local" }
variable "template_name"        { type = string default = "miles-challenge-base" }
variable "ubuntu_version"       { type = string default = "22.04" }

# ── Source: Proxmox LXC ───────────────────────────────────────────────────────
source "proxmox-lxc" "ubuntu_base" {
  proxmox_url              = var.proxmox_url
  username                 = var.proxmox_username
  password                 = var.proxmox_password
  insecure_skip_tls_verify = false
  node                     = var.proxmox_node

  # Base OS — Ubuntu 22.04 LXC template from Proxmox CT templates
  lxc_os_type              = "ubuntu"
  os                       = "local:vztmpl/ubuntu-24.04-standard_24.04-2_amd64.tar.zst"

  # Container settings
  template_name            = var.template_name
  template_description     = "Miles Challenge base image — built by Packer"
  storage                  = var.proxmox_storage
  memory                   = 2048
  cores                    = 4

  network_interface {
    name   = "eth0"
    bridge = "vmbr0"
  }

  # SSH communicator — Packer uses this to run provisioners
  communicator             = "ssh"
  ssh_username             = "admin"
  ssh_timeout              = "10m"
}

# ── Build ─────────────────────────────────────────────────────────────────────
build {
  sources = ["source.proxmox-lxc.ubuntu_base"]

  # 1. System update + install all runtime dependencies
  provisioner "shell" {
    inline = [
      "apt-get update -qq",
      "DEBIAN_FRONTEND=noninteractive apt-get upgrade -y",
      "DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends",
      "  python3 python3-venv python3-pip",
      "  nginx certbot python3-certbot-nginx",
      "  postgresql postgresql-contrib",
      "  acl curl",
      # Clean up to keep the template lean
      "apt-get clean",
      "rm -rf /var/lib/apt/lists/*",
    ]
  }

  # 2. Create app directory and virtualenv
  provisioner "shell" {
    inline = [
      "mkdir -p /app/venv",
      "python3 -m venv /app/venv",
      # Pre-install dependencies so deploys only need to install miles-challenge
      "/app/venv/bin/pip install --upgrade pip",
      "/app/venv/bin/pip install flask gunicorn psycopg2-binary python-dotenv",
      "chown -R www-data:www-data /app",
    ]
  }

  # 3. Create www-data owned log directories
  provisioner "shell" {
    inline = [
      "mkdir -p /var/log/gunicorn",
      "chown www-data:www-data /var/log/gunicorn",
    ]
  }

  # 4. Harden SSH
  provisioner "shell" {
    inline = [
      "sed -i 's/#PermitRootLogin.*/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config",
      "sed -i 's/#PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config",
    ]
  }
}