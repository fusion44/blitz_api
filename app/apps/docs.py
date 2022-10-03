get_app_status_response_docs = """
Returns a JSON list with the current status of all **installed** apps
```
[
    {
        id: 'specter',
        name: 'Specter Desktop',
        status: 'online'
    },
    {
        id: 'sphinx',
        name: 'Sphinx Chat',
        status: 'online'
    },
   ...
]
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
