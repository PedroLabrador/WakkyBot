import endpoints
import json
import os
import requests
from collections import namedtuple
from json.decoder import JSONDecodeError


class Request():
    headers = { "Authorization": f"Token { os.getenv('SERVER_TOKEN') }" }

    @staticmethod
    def get(url):
        return requests.get(url, headers=Request.headers)

    @staticmethod
    def post(url):
        return requests.post(url, headers=Request.headers)


class Server:
    SELECT_TASK = 0
    SELECT_OPT  = 1

    @staticmethod
    def get_tasks_list(username):
        response = Request.get(endpoints.ALWAYS_ON.format(username=username))
        if response.status_code == 200:
            try:
                return json.loads(response.content, object_hook=lambda d: namedtuple('AlwaysOn', d.keys())(*d.values()))
            except JSONDecodeError:
                pass
        return None

    @staticmethod
    def restart_task(username, task_id):
        response = Request.post(endpoints.ALWAYS_ON_ID_RESTART.format(username=username, id=task_id))
        if response.status_code == 200:
            return True
        return None
