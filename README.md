# Mikrotik_BackUp
## New version v0.0.2
### 19.11.2025
#### What's new in this version
 * Removed config.yaml from build
 * The entire service can be run in Docker
 * Consul has been added to the build for storing router data and backup time settings.
 * Сonsul rises to port 8500, in .env in the column ```CONSUL_HTTP_TOKEN``` is set as a token for accessing application secrets
 * Successful backups are saved to local storage in the root of the ```/data/backup``` project.
 * The router settings should be set in the "routers" folder as follows:
 ```
name: test
host: 192.168.1.1
user: admin
password: strongpass
port: 22
```
 * The schedule is read and updated from Consul: output schedule updated from consul {'cron': ..., 'interval': ...} when keys change.
 * The backup schedule is set in Consul as follows:
 
    for cron schedule:
```
key: settings/backup_cron
value: 0 0 * * *
```
for interval schedule:
```
key: settings/backup_interval_minutes
value: 720
```
 * When adding a new router, an automatic backup is performed to verify the connection to the router. Monitor container logs and input data to avoid data loss.

## To run the project, run the commands
```
git clone https://github.com/PunkStudio/Mikrotik_BackUp.git
docker-compose up -d
```
 #### Challenges for the future
  * Add the ability to send notifications via Telegram about backup errors
***
in future \
github action

29.06.2022 v 0.0.1b \
added requirements.txt

28.06.2022 v 0.0.1a \
format code with pycharm

v.0.0.1
change config.xml with your.\
password is not encrypted!!!\
check it for well formatted as template.\
the script will create a new folder in the execution folder.\
folders will be created inside it according to the given names in the configuration.
