#!/usr/bin/env python3
"""
Creates a base LXC template on Proxmox by:
  1. Downloading the Ubuntu 24.04 CT template (if not present)
  2. Creating an LXC container from it
  3. Provisioning it (packages, venv, hardening)
  4. Converting it to a template

Run once manually or via the packer.yml workflow.
"""
import os
import sys
import time
import json
import subprocess
import urllib.request
import urllib.error
import ssl

PROXMOX_URL       = os.environ["PROXMOX_URL"].strip()
PROXMOX_NODE      = os.environ.get("PROXMOX_NODE", "pve").strip()
PROXMOX_USER      = os.environ["PROXMOX_USER"].strip()
PROXMOX_TOKEN_ID  = os.environ["PROXMOX_TOKEN_ID"].strip()
PROXMOX_API_TOKEN = os.environ["PROXMOX_API_TOKEN"].strip()
PROXMOX_STORAGE   = os.environ.get("PROXMOX_STORAGE", "local").strip()
TEMPLATE_VMID     = int(os.environ.get("TEMPLATE_VMID", "9000"))
TEMPLATE_NAME     = os.environ.get("PROXMOX_TEMPLATE", "miles-challenge-base").strip()
CT_TEMPLATE       = "ubuntu-24.04-standard_24.04-2_amd64.tar.zst"
BRIDGE            = os.environ.get("PROXMOX_BRIDGE", "vmbr0").strip()

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
print("[debug] SSL verification disabled (insecure mode)")


class ProxmoxAPI:
    def __init__(self):
        self.base = PROXMOX_URL.rstrip("/")
        auth = f"PVEAPIToken={PROXMOX_USER}!{PROXMOX_TOKEN_ID}={PROXMOX_API_TOKEN}"
        masked = PROXMOX_API_TOKEN[:6] + "..." + PROXMOX_API_TOKEN[-4:]
        print(f"[debug] PROXMOX_URL      = {self.base}")
        print(f"[debug] PROXMOX_USER     = {PROXMOX_USER!r}")
        print(f"[debug] PROXMOX_TOKEN_ID = {PROXMOX_TOKEN_ID!r}")
        print(f"[debug] PROXMOX_NODE     = {PROXMOX_NODE!r}")
        print(f"[debug] API_TOKEN        = {masked}")
        print(f"[debug] Auth header      = PVEAPIToken={PROXMOX_USER}!{PROXMOX_TOKEN_ID}=<uuid>")
        self.headers = {
            "Authorization": auth,
            "Content-Type":  "application/json",
        }

    def _req(self, method, path, payload=None):
        url     = f"{self.base}/api2/json{path}"
        data    = json.dumps(payload).encode() if payload is not None else None
        headers = dict(self.headers)
        if data is None:
            headers.pop("Content-Type", None)
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            print(f"[debug] HTTP {e.code} {method} {url}", file=sys.stderr)
            print(f"[debug] Response body: {body}", file=sys.stderr)
            raise

    def get(self, path):           return self._req("GET",    path)
    def post(self, path, payload): return self._req("POST",   path, payload)
    def delete(self, path):        return self._req("DELETE", path)

    def wait_for_task(self, upid, timeout=300):
        node     = upid.split(":")[1]
        encoded  = upid.replace(":", "%3A").replace("/", "%2F")
        path     = f"/nodes/{node}/tasks/{encoded}/status"
        deadline = time.time() + timeout
        while time.time() < deadline:
            result     = self.get(path)["data"]
            status     = result.get("status")
            exitstatus = result.get("exitstatus", "")
            if status == "stopped":
                print(f"  task finished with exitstatus: {exitstatus!r}")
                if exitstatus == "OK" or exitstatus.startswith("WARNINGS"):
                    return
                raise RuntimeError(f"Task {upid} failed with: {exitstatus}")
            print(f"  waiting for task... ({status})")
            time.sleep(5)
        raise TimeoutError(f"Task {upid} did not complete within {timeout}s")

    def template_exists(self):
        try:
            lxcs = self.get(f"/nodes/{PROXMOX_NODE}/lxc")["data"]
            return any(
                c.get("name") == TEMPLATE_NAME and c.get("template") == 1
                for c in lxcs
            )
        except Exception:
            return False

    def download_ct_template(self):
        """Download Ubuntu CT template to Proxmox storage if not present."""
        print(f"Checking for CT template {CT_TEMPLATE}...")
        content  = self.get(
            f"/nodes/{PROXMOX_NODE}/storage/{PROXMOX_STORAGE}/content"
        )["data"]
        existing = [c["volid"] for c in content if CT_TEMPLATE in c.get("volid", "")]
        if existing:
            print(f"  CT template already present: {existing[0]}")
            return

        print(f"  Downloading {CT_TEMPLATE} from Proxmox mirrors...")
        upid = self.post(
            f"/nodes/{PROXMOX_NODE}/aplinfo",
            {
                "storage":  PROXMOX_STORAGE,
                "template": f"system/{CT_TEMPLATE}",
            }
        )["data"]
        self.wait_for_task(upid)
        print("  Download complete.")

    def create_base_template(self):
        print(f"Creating base LXC container (VMID {TEMPLATE_VMID})...")

        # Delete existing container with same VMID if present
        try:
            self.get(f"/nodes/{PROXMOX_NODE}/lxc/{TEMPLATE_VMID}/status/current")
            print(f"  VMID {TEMPLATE_VMID} exists — removing it first")
            try:
                self.post(f"/nodes/{PROXMOX_NODE}/lxc/{TEMPLATE_VMID}/status/stop", {})
                time.sleep(3)
            except Exception:
                pass
            upid = self.delete(f"/nodes/{PROXMOX_NODE}/lxc/{TEMPLATE_VMID}")["data"]
            self.wait_for_task(upid)
        except urllib.error.HTTPError:
            pass  # doesn't exist yet

        # Create LXC container
        net0_val = f"name=eth0,bridge={BRIDGE},ip=dhcp,type=veth"
        print(f"[debug] net0 = {net0_val}")
        upid = self.post(f"/nodes/{PROXMOX_NODE}/lxc", {
            "vmid":         TEMPLATE_VMID,
            "hostname":     TEMPLATE_NAME,
            "ostemplate":   f"{PROXMOX_STORAGE}:vztmpl/{CT_TEMPLATE}",
            "rootfs":       f"{PROXMOX_STORAGE}:8",
            "memory":       512,
            "cores":        1,
            "net0":         net0_val,
            "unprivileged": 1,
            "start":        0,
        })["data"]
        self.wait_for_task(upid)
        print("  Container created.")

        # Start it for provisioning
        print("  Starting container for provisioning...")
        upid = self.post(
            f"/nodes/{PROXMOX_NODE}/lxc/{TEMPLATE_VMID}/status/start", None
        )["data"]
        self.wait_for_task(upid)
        time.sleep(5)

        # Provision via pct exec
        print("  Provisioning packages and virtualenv...")
        cmds = [
            "apt-get update -qq",
            "DEBIAN_FRONTEND=noninteractive apt-get upgrade -y",
            "DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "
            "python3 python3-venv python3-pip nginx certbot python3-certbot-nginx "
            "postgresql postgresql-contrib acl curl",
            "apt-get clean && rm -rf /var/lib/apt/lists/*",
            "mkdir -p /app/venv",
            "python3 -m venv /app/venv",
            "/app/venv/bin/pip install --upgrade pip",
            "/app/venv/bin/pip install flask gunicorn psycopg2-binary python-dotenv",
            "chown -R www-data:www-data /app",
            "mkdir -p /var/log/gunicorn && chown www-data:www-data /var/log/gunicorn",
            "sed -i 's/#PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config",
        ]
        for cmd in cmds:
            print(f"    + {cmd[:60]}...")
            result = subprocess.run(
                ["ssh", "-o", "StrictHostKeyChecking=no",
                 f"root@{PROXMOX_NODE}", f"pct exec {TEMPLATE_VMID} -- bash -c '{cmd}'"],
                capture_output=True, text=True
            )
            if result.returncode != 0:
                print(f"    WARN: {result.stderr.strip()}")

        # Stop and convert to template
        print("  Stopping container...")
        upid = self.post(
            f"/nodes/{PROXMOX_NODE}/lxc/{TEMPLATE_VMID}/status/stop", None
        )["data"]
        self.wait_for_task(upid)

        print("  Converting to template...")
        self.post(f"/nodes/{PROXMOX_NODE}/lxc/{TEMPLATE_VMID}/template", None)


if __name__ == "__main__":
    api = ProxmoxAPI()
    if api.template_exists():
        print(f"Template '{TEMPLATE_NAME}' already exists — nothing to do.")
        print("Pass --force to rebuild it.")
        if "--force" not in sys.argv:
            sys.exit(0)
    api.download_ct_template()
    api.create_base_template()