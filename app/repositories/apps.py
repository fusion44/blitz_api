import asyncio
import json
import random


def get_app_status():
    return [
        {
            "id": 'specter',
            "name": 'Specter Desktop',
            "status": 'online'
        },
        {
            "id": 'sphinx',
            "name": 'Sphinx Chat',
            "status": 'online'
        },
        {
            "id": 'btc-pay',
            "name": 'BTCPay Server',
            "status": 'offline'
        },
        {
            "id": 'rtl',
            "name": 'Ride the Lightning',
            "status": 'online'
        },
        {
            "id": 'bos',
            "name": 'Balance of Satoshis',
            "status": 'offline'
        }
    ]


async def get_app_status_sub():
    switch = True
    while True:
        status = "online" if switch else "offline"
        app_list = [
            {
                "id": 'specter',
                "name": 'Specter Desktop',
                "status": status
            },
            {
                "id": 'sphinx',
                "name": 'Sphinx Chat',
                "status": status
            },
            {
                "id": 'btc-pay',
                "name": 'BTCPay Server',
                "status": status
            },
            {
                "id": 'rtl',
                "name": 'Ride the Lightning',
                "status": status
            },
            {
                "id": 'bos',
                "name": 'Balance of Satoshis',
                "status": status
            }
        ]
        i = random.randint(1, len(app_list))
        yield json.dumps(app_list[i-1])
        await asyncio.sleep(4)
        switch = not switch
