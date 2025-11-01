import json
import os
from typing import Any, Dict, List, Union


def join_msg_contents(
    content1: Union[List[Dict[str, Any]], str],
    content2: Union[List[Dict[str, Any]], str],
) -> str:
    if isinstance(content1, str) and isinstance(content2, str):
        return content1 + "\n" + content2
    elif isinstance(content1, list) and isinstance(content2, list):
        return content1 + content2
    elif isinstance(content1, str) and isinstance(content2, list):
        return [{"type": "text", "text": content1}] + content2
    elif isinstance(content1, list) and isinstance(content2, str):
        return content1 + [{"type": "text", "text": content2}]
    else:
        return content1 + content2


def print_util(x: Union[List[Dict[str, Any]], str, Dict[str, Any]], header: str = None):
    if os.getenv("ENV") and os.getenv("ENV").lower().startswith('prod'):
        return
    if header:
        print("=============== " + header + " ===============")
    if isinstance(x, (list, dict)):
        x = json.dumps(x, indent=2, ensure_ascii=False)
    print(x)


def print_messages(
    messages: Union[List[Dict[str, Any]], str, Dict[str, Any]],
    system_message: str = None,
):
    if system_message:
        print_util(system_message, header="System Message")
    else:
        system_message = next(
            iter(msg for msg in messages if msg.get("role") == "system"), None
        )
        if system_message:
            print_util(system_message, header="System Message")
    if isinstance(messages, str):
        messages = [{"role": "message", "content": messages}]
    if isinstance(messages, dict):
        messages = [messages]
    for message in messages:
        if message.get("content"):
            if isinstance(message["content"], str):
                content_str = message["content"]
            elif (
                isinstance(message["content"], list)
                and len(message["content"]) == 1
                and message["content"][0].get("type") == "text"
            ):
                content_str = message["content"][0]["text"]
            else:
                content_str = json.dumps(message["content"], indent=2)
        else:
            content_str = str(message)
        print_util(content_str, header=message.get("role", message.get("type", "item")))
