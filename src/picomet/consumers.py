from json import dumps
from typing import Any

from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer


class HmrConsumer(WebsocketConsumer):
    def connect(self) -> None:
        async_to_sync(self.channel_layer.group_add)("hmr", self.channel_name)
        self.accept()

    def disconnect(self, close_code: Any) -> None:
        async_to_sync(self.channel_layer.group_discard)("hmr", self.channel_name)

    def send_message(self, event: Any) -> None:
        message = event["message"]
        self.send(text_data=dumps(message))
