import os
from netmiko import ConnectHandler

device = {
    "device_type": "cisco_ios",
    "host": "10.255.255.1",
    "username": os.getenv("NETWORK_USERNAME", "automation"),
    "password": os.getenv("NETWORK_PASSWORD"),
}

connection = ConnectHandler(**device)

output = connection.send_command("show version")

print(output)

connection.disconnect()
