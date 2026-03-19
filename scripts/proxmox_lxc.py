#!/usr/bin/env python3
"""
Proxmox LXC lifecycle manager.
Usage:
  proxmox_lxc.py create  --vmid 200 --ip 10.10.10.50
  proxmox_lxc.py destroy --vmid 200
  proxmox_lxc.py list
"""
import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
import ssl

# ── Config from environment ──────────────────────────────────────────────────
PROXMOX_URL       = os.environ["PROXMOX_URL"].strip()
PROXMOX_NODE      = os.environ.get("PROXMOX_NODE", "pve").strip()
PROXMOX_USER      = os.environ["PROXMOX_USER"].strip()
PROXMOX_TOKEN_ID  = os.environ["PROXMOX_TOKEN_ID"].strip()
PROXMOX_API_TOKEN = os.environ["PROXMOX_API_TOKEN"].strip()
TEMPLATE_NAME     = os.environ.get("PROXMOX_TEMPLATE", "miles-challenge-base").strip()
BRIDGE            = os.environ.get("PROXMOX_BRIDGE", "vmbr0").strip()
STORAGE           = os.environ.get("PROXMOX_STORAGE", "local").strip()
GW                = os.environ.get("LXC_GATEWAY", "10.10.10.1").strip()
DEPLOY_PUBKEY     = os.environ["LXC_DEPLOY_PUBLIC_KEY"].strip()

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


class ProxmoxAPI:
    def __init__(self):
        self.base    = PROXMOX_URL.rstrip("/")
        self.headers = {
            "Authorization": f"PVEAPIToken={PROXMOX_USER}!{PROXMOX_TOKEN_ID}={PROXMOX_API_TOKEN}",
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
            print(f"HTTP {e.code}: {body}", file=sys.stderr)
            raise

    def get(self, path):           return self._req("GET",    path)
    def post(self, path, payload): return self._req("POST",   path, payload)
    def put(self, path, payload):  return self._req("PUT",    path, payload)
    def delete(self, path):        return self._req("DELETE", path)

    def wait_for_task(self, upid, timeout=120):
        node     = upid.split(":")[1]
        path     = f"/nodes/{node}/tasks/{urllib.request.quote(upid, safe='')}/status"
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
            time.sleep(3)
        raise TimeoutError(f"Task {upid} did not complete within {timeout}s")

    def find_template_vmid(self):
        """Resolve template name to VMID."""
        nodes = self.get("/nodes")["data"]
        all_templates = []
        for node in nodes:
            lxcs = self.get(f"/nodes/{node['node']}/lxc")["data"]
            for lxc in lxcs:
                if lxc.get("template") == 1:
                    all_templates.append(lxc)

        for t in all_templates:
            if t.get("name") == TEMPLATE_NAME:
                print(f"Found template '{TEMPLATE_NAME}' — VMID {t['vmid']}")
                return t["vmid"]

        names = [t.get("name", "unnamed") for t in all_templates]
        print(f"Available templates: {names}", file=sys.stderr)
        raise ValueError(
            f"Template '{TEMPLATE_NAME}' not found. "
            f"Available: {names}. "
            f"Set PROXMOX_TEMPLATE to one of these names."
        )

    # ── Public actions ────────────────────────────────────────────────────────

    def create(self, vmid: int, ip: str):
        """Clone the base template into a new LXC and start it."""
        template_vmid = self.find_template_vmid()
        print(f"Cloning template {template_vmid} → VMID {vmid} ({ip})")

        upid = self.post(f"/nodes/{PROXMOX_NODE}/lxc/{template_vmid}/clone", {
            "newid":    vmid,
            "full":     1,
            "hostname": f"miles-challenge-{vmid}",
            "storage":  STORAGE,
        })["data"]
        self.wait_for_task(upid)

        # Configure networking
        self.put(f"/nodes/{PROXMOX_NODE}/lxc/{vmid}/config", {
            "net0": f"name=eth0,bridge={BRIDGE},ip={ip}/24,gw={GW},type=veth",
        })

        # Inject deploy SSH public key
        self.put(f"/nodes/{PROXMOX_NODE}/lxc/{vmid}/config", {
            "ssh-public-keys": DEPLOY_PUBKEY,
        })

        # Start
        upid = self.post(f"/nodes/{PROXMOX_NODE}/lxc/{vmid}/status/start", None)["data"]
        self.wait_for_task(upid)
        print(f"LXC {vmid} started at {ip}")
        return ip

    def destroy(self, vmid: int):
        """Stop and destroy an LXC container."""
        print(f"Stopping LXC {vmid}")
        try:
            upid = self.post(f"/nodes/{PROXMOX_NODE}/lxc/{vmid}/status/stop", None)["data"]
            self.wait_for_task(upid)
        except Exception:
            pass  # already stopped

        print(f"Destroying LXC {vmid}")
        upid = self.delete(f"/nodes/{PROXMOX_NODE}/lxc/{vmid}")["data"]
        self.wait_for_task(upid)
        print(f"LXC {vmid} destroyed")

    def list_containers(self):
        containers = self.get(f"/nodes/{PROXMOX_NODE}/lxc")["data"]
        for c in containers:
            print(f"{c['vmid']:>6}  {c.get('name',''):<30}  {c['status']}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    p   = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("create")
    c.add_argument("--vmid", type=int, required=True)
    c.add_argument("--ip",   required=True)

    d = sub.add_parser("destroy")
    d.add_argument("--vmid", type=int, required=True)

    sub.add_parser("list")

    args = p.parse_args()
    api  = ProxmoxAPI()

    if args.cmd == "create":
        api.create(args.vmid, args.ip)
    elif args.cmd == "destroy":
        api.destroy(args.vmid)
    elif args.cmd == "list":
        api.list_containers()


if __name__ == "__main__":
    main()