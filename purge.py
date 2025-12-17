#!/usr/bin/env python3
import os
import pwd
import subprocess
import signal
import time

# ---- CHECK ROOT ----
if os.geteuid() != 0:
    raise SystemExit("Esegui come root.")

current_user = os.getenv("SUDO_USER") or pwd.getpwuid(os.getuid()).pw_name
print("Utente preservato:", current_user)

# ---- 1. ELIMINA ALTRI UTENTI UMANI ----
for p in pwd.getpwall():
    if p.pw_uid >= 1000 and p.pw_name != current_user:
        subprocess.run(
            ["userdel", "-r", "-f", p.pw_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

# ---- 2. MASCHERA CTRL+ALT+DEL ----
subprocess.run(
    ["systemctl", "mask", "ctrl-alt-del.target"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL
)

# ---- 3. BLOCCA EGRESS (STOP MINING SUBITO) ----
subprocess.run(
    ["iptables", "-P", "OUTPUT", "DROP"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL
)

# ---- 4. DISABILITA CRON ----
subprocess.run(["systemctl", "stop", "cron"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
subprocess.run(["systemctl", "mask", "cron"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
subprocess.run(["rm", "-f", "/var/spool/cron/crontabs/root"],
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# ---- 5. DISABILITA UNITÀ SYSTEMD SOSPETTE ----
try:
    units = subprocess.check_output(
        ["systemctl", "list-unit-files"],
        text=True,
        errors="ignore"
    )
    for line in units.splitlines():
        l = line.lower()
        if any(x in l for x in ["xmrig", "miner", "crypt", "cpu"]):
            unit = line.split()[0]
            subprocess.run(
                ["systemctl", "disable", "--now", unit],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
except:
    pass

# ---- 6. RIMOZIONE BINARI NOTI ----
paths = [
    "/tmp/xmrig",
    "/usr/bin/xmrig",
    "/usr/local/bin/xmrig",
    "/dev/shm/xmrig",
    "/tmp/.xmrig",
    "/dev/shm/.xmrig"
]

for p in paths:
    subprocess.run(["rm", "-rf", p],
                   stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)

# ---- 7. PULIZIA PERSISTENZE ----
persistence_dirs = [
    "/etc/cron.d",
    "/etc/cron.hourly",
    "/etc/cron.daily",
    "/etc/cron.weekly",
    "/etc/cron.monthly",
    "/var/spool/cron",
    "/etc/systemd/system",
    "/lib/systemd/system"
]

for base in persistence_dirs:
    if os.path.isdir(base):
        for root, dirs, files in os.walk(base):
            for f in files:
                fl = f.lower()
                if any(x in fl for x in ["xmrig", "miner", "crypt", "cpu"]):
                    try:
                        os.remove(os.path.join(root, f))
                    except:
                        pass

# ---- 8. KILL RIPETUTO (ANTI-RESPAWN) ----
BAD = ["xmrig", "cryptonight", "minerd", "pool", "--algo", "--url"]

for _ in range(12):
    ps = subprocess.check_output(
        ["ps", "-eo", "pid,pcpu,cmd"],
        text=True,
        errors="ignore"
    ).splitlines()[1:]

    for line in ps:
        try:
            pid, cpu, cmd = line.strip().split(None, 2)
            cpu = float(cpu)
            cl = cmd.lower()

            if cpu >= 90.0 or any(b in cl for b in BAD):
                os.kill(int(pid), signal.SIGKILL)
        except:
            pass

    time.sleep(1)

# ---- 9. RELOAD SYSTEMD ----
subprocess.run(
    ["systemctl", "daemon-reexec"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL
)

print("Bonifica completata. Sistema ridotto all'essenziale.")
print("Utente rimasto:", current_user)
