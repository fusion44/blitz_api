get_app_status_response_docs = """
Returns a JSON list with the current status of all available apps
```
{
  "data": [
    {
      "id": "btcpayserver",
      "version": "v1.13.0",
      "installed": false,
      "configured": false,
      "status": "offline",
      "local_ip": null,
      "http_port": null,
      "https_port": null,
      "https_forced": null,
      "https_self_signed": null,
      "hidden_service": null,
      "address": null,
      "auth_method": null,
      "details": null,
      "error": null
    },
    {
      "id": "btc-rpc-explorer",
      "version": "v3.4.0",
      "installed": false,
      "configured": false,
      "status": "offline",
      "local_ip": null,
      ...
    },
    ...
  ],
  "errors": [
    {
      "id": "rtl",
      "error": "App status script execution failed.\n├╴at /home/blitzapi/blitz_api/app/apps/impl/raspiblitz.py:92:10\n├╴script_name: /home/admin/config.scripts/bonus.rtl.sh status\n│\n╰─▶ 500: Something went wrong!\n    ╰╴at /home/blitzapi/blitz_api/app/apps/impl/raspiblitz.py:92:10"
    },
    ...
  ]
}
```
"""

get_app_status_sub_response_docs = """
Sends a JSON object with the status of an app if it changes.
```
{
    id: 'specter',
    name: 'Specter Desktop',
    status: 'online'
},
```
"""
