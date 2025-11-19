#!/usr/bin/python3
import os
import time
from netmiko import ConnectHandler
from colorama import init, Fore, Back, Style
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import yaml
import requests
import base64

init(autoreset=True)
load_dotenv()

mainFolder = os.getcwd()
SECRETS_DIR = os.getenv("SECRETS_DIR", "/run/secrets")
BACKUP_DIR = os.getenv("BACKUP_DIR", "backup")
CRON = os.getenv("BACKUP_CRON")
INTERVAL_MINUTES = int(os.getenv("BACKUP_INTERVAL_MINUTES", "60"))
CONSUL_ADDR = os.getenv("CONSUL_HTTP_ADDR")
CONSUL_TOKEN = os.getenv("CONSUL_HTTP_TOKEN")
CONSUL_PREFIX = os.getenv("CONSUL_KV_PREFIX", "routers/")
CONSUL_BASIC_USER = os.getenv("CONSUL_BASIC_USER")
CONSUL_BASIC_PASS = os.getenv("CONSUL_BASIC_PASS")
CONSUL_SETTINGS_PREFIX = os.getenv("CONSUL_SETTINGS_PREFIX", "settings/")

KNOWN_ROUTERS = set()


def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)


def backup_path(name):
    ensure_dir(BACKUP_DIR)
    p = os.path.join(BACKUP_DIR, name)
    ensure_dir(p)
    return p


def now_str():
    return time.strftime("%d%m%Y-%H%M%S")


def export_router(name, host, port, user, password):
    try:
        port_i = int(port)
    except Exception:
        port_i = 22
    router = {
        'device_type': 'mikrotik_routeros',
        'host': host,
        'port': port_i,
        'username': user,
        'password': password,
        'read_timeout_override': 1000,
    }
    print(Style.BRIGHT + Back.YELLOW + "connecting to " + name + "...")
    try:
        sshCli = ConnectHandler(**router)
    except Exception:
        print(Fore.RED + "Can't connect to " + name + " " + host + ". Check your connection...")
        return
    print("start export backup...")
    try:
        output = sshCli.send_command("/export")
    except Exception:
        print(Fore.RED + "Something was wrong!")
        sshCli.disconnect()
        return
    print("saving backup to file...")
    p = backup_path(name)
    fn = os.path.join(p, name + now_str() + ".txt")
    try:
        with open(fn, "w", encoding="utf-8") as f:
            f.write(output)
    except Exception:
        print(Fore.RED + "Can't open file!")
    else:
        print(Fore.GREEN + "success!")
        sshCli.disconnect()
        print("Saved in " + p)


def read_secrets_configs():
    cfgs = []
    if not os.path.isdir(SECRETS_DIR):
        return cfgs
    for e in os.scandir(SECRETS_DIR):
        if not e.is_file():
            continue
        try:
            with open(e.path, "r", encoding="utf-8") as f:
                d = yaml.safe_load(f) or {}
        except Exception:
            continue
        n = str(d.get("name") or os.path.splitext(os.path.basename(e.path))[0])
        h = d.get("host")
        u = d.get("user")
        pw = d.get("password")
        pt = d.get("port") or 22
        if h and u and pw:
            cfgs.append({'name': n, 'host': h, 'user': u, 'password': pw, 'port': pt})
    return cfgs


def read_xml_configs():
    cfgs = []
    try:
        import xml.etree.cElementTree as ET
    except ImportError:
        import xml.etree.ElementTree as ET
    try:
        t = ET.ElementTree(file='config.xml')
        r = t.getroot()
    except Exception:
        return cfgs
    i = 0
    for child in r:
        n = child.tag
        h = r[i][0].text
        u = r[i][1].text
        pw = r[i][2].text
        pt = r[i][3].text
        try:
            ptv = int(pt)
        except Exception:
            ptv = 22
        cfgs.append({'name': n, 'host': h, 'user': u, 'password': pw, 'port': ptv})
        i += 1
    return cfgs


def read_consul_configs():
    cfgs = []
    if not CONSUL_ADDR:
        return cfgs
    url = CONSUL_ADDR.rstrip('/') + '/v1/kv/' + CONSUL_PREFIX + '?recurse=true'
    headers = {}
    if CONSUL_TOKEN:
        headers['X-Consul-Token'] = CONSUL_TOKEN
    auth = None
    if CONSUL_BASIC_USER and CONSUL_BASIC_PASS:
        auth = (CONSUL_BASIC_USER, CONSUL_BASIC_PASS)
    try:
        r = requests.get(url, headers=headers, auth=auth, timeout=5)
        if r.status_code == 404:
            return cfgs
        r.raise_for_status()
    except Exception:
        return cfgs
    try:
        items = r.json()
    except Exception:
        return cfgs
    for it in items:
        val = it.get('Value')
        if not val:
            continue
        try:
            decoded = base64.b64decode(val).decode('utf-8')
            if '\\n' in decoded or '\\r\\n' in decoded:
                decoded = decoded.replace('\\r\\n', '\n').replace('\\n', '\n')
            d = yaml.safe_load(decoded) or {}
        except Exception:
            continue
        n = str(d.get("name") or os.path.basename(it.get('Key', '')).split('/')[-1])
        h = d.get("host")
        u = d.get("user")
        pw = d.get("password")
        pt = d.get("port") or 22
        if h and u and pw:
            cfgs.append({'name': n, 'host': h, 'user': u, 'password': pw, 'port': pt})
    return cfgs


def run_backup_all():
    cfgs = read_consul_configs()
    print("consul configs count:", len(cfgs))
    if not cfgs:
        cfgs = read_secrets_configs()
    if not cfgs:
        cfgs = read_xml_configs()
    for c in cfgs:
        export_router(c['name'], c['host'], c['port'], c['user'], c['password'])
    KNOWN_ROUTERS.update([c['name'] for c in cfgs])


def watch_new_routers():
    cfgs = read_consul_configs()
    names = set([c['name'] for c in cfgs])
    new_names = names - KNOWN_ROUTERS
    if new_names:
        print("new routers detected:", ", ".join(sorted(new_names)))
    for c in cfgs:
        if c['name'] in new_names:
            export_router(c['name'], c['host'], c['port'], c['user'], c['password'])
    KNOWN_ROUTERS.update(new_names)


def consul_kv_get(key):
    if not CONSUL_ADDR:
        return None
    url = CONSUL_ADDR.rstrip('/') + '/v1/kv/' + key
    headers = {}
    if CONSUL_TOKEN:
        headers['X-Consul-Token'] = CONSUL_TOKEN
    auth = None
    if CONSUL_BASIC_USER and CONSUL_BASIC_PASS:
        auth = (CONSUL_BASIC_USER, CONSUL_BASIC_PASS)
    try:
        r = requests.get(url, headers=headers, auth=auth, timeout=5)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        items = r.json()
        if not items:
            return None
        val = items[0].get('Value')
        if not val:
            return None
        decoded = base64.b64decode(val).decode('utf-8')
        if '\\r\\n' in decoded or '\\n' in decoded:
            decoded = decoded.replace('\\r\\n', '\n').replace('\\n', '\n')
        return decoded.strip()
    except Exception:
        return None


def read_consul_schedule():
    cron = consul_kv_get(CONSUL_SETTINGS_PREFIX + 'backup_cron')
    interval_str = consul_kv_get(CONSUL_SETTINGS_PREFIX + 'backup_interval_minutes')
    interval = None
    try:
        if interval_str:
            interval = int(interval_str)
    except Exception:
        interval = None
    return {'cron': cron, 'interval': interval}


def main():
    ensure_dir(BACKUP_DIR)
    s = BackgroundScheduler()
    sched = read_consul_schedule()
    use_cron = bool(sched.get('cron'))
    if use_cron:
        s.add_job(run_backup_all, CronTrigger.from_crontab(sched['cron']), id='backup_job', replace_existing=True)
    else:
        minutes = sched.get('interval') or INTERVAL_MINUTES
        s.add_job(run_backup_all, 'interval', minutes=minutes, id='backup_job', replace_existing=True)
    s.add_job(watch_new_routers, 'interval', seconds=15, id='watch_new', replace_existing=True)

    run_backup_all()
    s.start()
    try:
        last = sched
        while True:
            time.sleep(10)
            curr = read_consul_schedule()
            if curr != last:
                print("schedule updated from consul", curr)
                try:
                    s.remove_job('backup_job')
                except Exception:
                    pass
                if curr.get('cron'):
                    s.add_job(run_backup_all, CronTrigger.from_crontab(curr['cron']), id='backup_job', replace_existing=True)
                else:
                    minutes = curr.get('interval') or INTERVAL_MINUTES
                    s.add_job(run_backup_all, 'interval', minutes=minutes, id='backup_job', replace_existing=True)
                last = curr
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
