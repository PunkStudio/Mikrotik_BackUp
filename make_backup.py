#!/usr/bin/python3
try:
    import xml.etree.cElementTree as ET
except importError:
    import xml.etree.ElementTree as ET

import netmiko
from netmiko import ConnectHandler
import time
import os
from colorama import init, Fore, Back, Style

init(autoreset=True)
mainFolder = os.getcwd()

def SetConnection(ho, po,us,pa):
        router = {
             'device_type':'mikrotik_routeros',
             'host':ho,
             'port':po,
             'username':us,
             'password':pa,
             'read_timeout_override': 1000,
             } 
        #set time
        nowTime = time.strftime("%d%m%Y-%H%M%S")

#start connection
        print (Style.BRIGHT + Back.YELLOW + "connecting to "+ name+"...")
        try:
            sshCli = ConnectHandler(**router)
        except:
            print(Fore.RED + "Can't connect to "+name+" "+ho+"."+" Check your connection...")
        else:
            
#send command
            print("start export backup...")
            command = "/export"
            try:
                output = sshCli.send_command(command)
            except:
                print(Fore.RED + "Something was wrong!")
            else:
                

#save file
                print("saving backup to file...")
                try:
                    file = open(name+nowTime+".txt", "w")
                except:
                    print(Fore.RED + "Can't open file!")
                else:    
                    file.write(output)
                    file.close()
                    print(Fore.GREEN + "success!")

#close connection
                   # print("closing connection...")
                    sshCli.disconnect()
                   # print(Fore.GREEN + "success!")

def createBackupFolder():
    if not os.path.exists("backup"): os.makedirs("backup")


def hostNewFolder(folderName):
    if not os.path.exists(folderName): os.makedirs(folderName)
    os.chdir(folderName)
  
   
tree = ET.ElementTree(file='config.xml')

root = tree.getroot()
root.tag, root.attrib
('doc', {})
i=0
for child in root:
    #get name
    name = child.tag
    print("Getting " + name + " settings...")
    #get address
    host = root[i][0].text
    #get username
    user = root[i][1].text
    #get password
    passwd = root[i][2].text
    #get port
    port = root[i][3].text
    i=i+1
    #set connection settings
    createBackupFolder()
    os.chdir("backup")
    hostNewFolder(name)
#    SetConnection(host, port, user, passwd)  
    print("Saved in " + os.getcwd())
    os.chdir(mainFolder)
