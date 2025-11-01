import asyncio
import base64
import json
import os
import random
import time
import uuid
from copy import deepcopy
from typing import Any, AsyncGenerator, List

import tiktoken
from dotenv import load_dotenv

from ..core.enums import LLMName
from ..core.models import LLMChunk, LLMToolParam, LLMToolResponse, LLMUsage
from ..core.utils import join_msg_contents, print_messages, print_util

load_dotenv()


class LLMTool:
    name: str
    description: str
    parameters: List[LLMToolParam]
    type: str = "builtin"

    async def run(self, params: dict) -> LLMToolResponse:
        pass

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": [p.model_dump() for p in self.parameters],
        }


class LLMClient:
    def __init__(self, llm_name: LLMName, call_id: str = None, verbose: bool = False):
        self.call_id = call_id
        self.llm_name = llm_name
        self.verbose = verbose
        self.raw_response_chunks = []
        self.init_client()

    @classmethod
    def from_llm_name_sync(
        cls, llm_name: LLMName, call_id: str = None, verbose: bool = False
    ) -> "LLMClient":
        if "gemini" in llm_name.name.lower():
            return VertexGenAIClient(llm_name, call_id=call_id, verbose=verbose)
        return cls(llm_name, call_id=call_id, verbose=verbose)

    @classmethod
    async def from_llm_name(
        cls, llm_name: LLMName, call_id: str = None, verbose: bool = False
    ) -> "LLMClient":
        return await asyncio.to_thread(
            cls.from_llm_name_sync, llm_name, call_id, verbose
        )

    def init_client(self):
        self.client = None
        raise NotImplementedError

    def get_model_name(self):
        return self.llm_name.value

    def get_token_count(self, string: str) -> int:
        if hasattr(self, "encoding") and self.encoding:
            pass  # use cached encoding
        else:
            try:
                self.encoding = tiktoken.encoding_for_model(self.get_model_name())
            except KeyError:
                print(f"Could not find encoding for model {self.get_model_name()}, using gpt-4o")
                self.encoding = tiktoken.encoding_for_model("gpt-4o")
        num_tokens = len(self.encoding.encode(string))
        return num_tokens

    def _build_tool_parameters_schema(self, tool: LLMTool) -> dict:
        properties = {}
        required = []
        for param in tool.parameters:
            if isinstance(param.type, dict):
                param_schema = {**param.type}
                if "description" not in param_schema and getattr(
                    param, "description", None
                ):
                    param_schema["description"] = param.description
                param_schema["additionalProperties"] = False
            else:
                param_schema = {"type": param.type, "description": param.description}
            properties[param.name] = param_schema
            if getattr(param, "required", True):
                required.append(param.name)
        schema = {
            "type": "object",
            "properties": properties,
            "additionalProperties": False,
            "required": required,
        }
        return schema

    def preprocess_messages(
        self, system_message: str, messages: List[dict], tools: List[LLMTool] = None
    ):
        if tools:
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": self._build_tool_parameters_schema(tool),
                        "strict": True
                        if all(p.required for p in tool.parameters)
                        else False,
                    },
                }
                for tool in tools
            ]
        messages = deepcopy(messages)
        processed_messages = []
        for msg in messages:
            if msg.get("role") == "user":
                msg.pop("id", None)
            if (
                processed_messages
                and processed_messages[-1]["role"] == "user"
                and msg["role"] == "user"
            ):
                processed_messages[-1]["content"] = join_msg_contents(
                    processed_messages[-1]["content"], msg["content"]
                )
            else:
                processed_messages.append(msg)
        return system_message, processed_messages, tools

    async def get_response_stream_generator(
        self,
        system_message: str,
        messages: List[dict],
        tools: List[LLMTool] = None,
        thinking_budget: int = None,
        reasoning_effort: str = None,
        tool_choice=None,
        **kwargs,
    ) -> AsyncGenerator:
        system_message, messages, tools = self.preprocess_messages(
            system_message, messages, tools=tools
        )
        client_kwargs = {
            "model": self.get_model_name(),
            "messages": [{"role": "system", "content": system_message}] + messages,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if not self.llm_name.supports_reasoning():
            client_kwargs["temperature"] = 0.0
        else:
            if reasoning_effort is not None:
                client_kwargs["reasoning"]["effort"] = reasoning_effort
            if thinking_budget is not None:
                client_kwargs["thinking_budget"] = thinking_budget
        if tools:
            client_kwargs["tools"] = tools
            if tool_choice is not None:
                client_kwargs["tool_choice"] = tool_choice
        kwargs_to_print = {
            k: v
            for k, v in client_kwargs.items()
            if k not in ["tools", "messages", "system_message"]
        }
        if kwargs_to_print:
            print_util(
                json.dumps(kwargs_to_print, indent=2, ensure_ascii=False),
                header="Client kwargs",
            )
        return await self.client.chat.completions.create(**client_kwargs)

    async def generate_response_stream(self, num_retries: int = 3, **kwargs):
        if "tools" in kwargs:
            print_util(
                json.dumps(
                    [
                        (tool.to_dict() if isinstance(tool, LLMTool) else tool)
                        for tool in kwargs["tools"]
                    ],
                    indent=2,
                    ensure_ascii=False,
                ),
                header="Tools",
            )
        if "messages" in kwargs:
            print_messages(kwargs["messages"], system_message=kwargs["system_message"])
        self.raw_response_chunks = []
        start_time = time.time()
        ttft = None
        async for chunk in await self.get_response_stream_generator(**kwargs):
            self.raw_response_chunks.append(chunk)
            async for resp in self.process_and_yield_from_response_chunk(chunk):
                if ttft is None and (
                    resp.text
                    or resp.tool_call_name
                    or resp.tool_call_args
                    or resp.tool_call_id
                ):
                    ttft = time.time() - start_time
                    print(
                        {"LLMName": self.llm_name.name, "Text TTFT": f"{ttft:.3f}"}
                    )
                yield resp
        usage = self.get_usage()
        if usage and not usage.output_tokens and num_retries > 0:
            print(
                f"No output tokens found {usage=}, retrying {num_retries} more times"
            )
            await asyncio.sleep(random.random() * 2 + 1)
            async for chunk in self.generate_response_stream(
                num_retries=num_retries - 1, **kwargs
            ):
                yield chunk

    async def generate_text(self, timeout: float = None, max_tries: int = 1, **kwargs) -> str:
        async def _generate_text():
            chunks: List[LLMChunk] = []
            async for chunk in self.generate_response_stream(**kwargs):
                chunks.append(chunk)
            thoughts = "".join([c.thought or "" for c in chunks if c.thought])
            text = "".join([c.text or "" for c in chunks]) if chunks else ""
            if "</think>" in text:
                thoughts = text.split("</think>")[0]
                thoughts = (
                    thoughts.split("<think>")[1].lstrip()
                    if "<think>" in thoughts
                    else thoughts
                )
                text = text.split("</think>")[1].lstrip()
            if thoughts:
                print_util("".join(thoughts), header="Thoughts")
            print_util(text, header="Response")
            return text

        while max_tries > 0:
            try:
                resp = await asyncio.wait_for(_generate_text(), timeout=timeout)
                return resp
            except asyncio.TimeoutError:
                if max_tries > 0:
                    max_tries -= 1
                    continue
                raise

    async def process_and_yield_from_response_chunk(self, chunk: Any):
        if not chunk.choices or len(chunk.choices) == 0:
            return
        choice = chunk.choices[0]
        delta = choice.delta
        if delta.content is not None:
            yield LLMChunk(text=delta.content)
        if delta.tool_calls:
            for tool_call in delta.tool_calls:
                if tool_call.id:
                    yield LLMChunk(tool_call_id=tool_call.id, index=tool_call.index)
                if tool_call.function and tool_call.function.name:
                    yield LLMChunk(
                        tool_call_name=tool_call.function.name, index=tool_call.index
                    )
                if tool_call.function and tool_call.function.arguments:
                    yield LLMChunk(
                        tool_call_args=tool_call.function.arguments,
                        index=tool_call.index,
                    )
        if hasattr(delta, "reasoning") and delta.reasoning:
            yield LLMChunk(thought=delta.reasoning)

    def get_usage(self) -> LLMUsage:
        usage = LLMUsage()
        for chunk in self.raw_response_chunks:
            if hasattr(chunk, "usage") and chunk.usage:
                if hasattr(chunk.usage, "prompt_tokens") and chunk.usage.prompt_tokens:
                    usage.input_tokens = chunk.usage.prompt_tokens
                if (
                    hasattr(chunk.usage, "completion_tokens")
                    and chunk.usage.completion_tokens
                ):
                    usage.output_tokens = chunk.usage.completion_tokens
                if (
                    hasattr(chunk.usage, "prompt_tokens_details")
                    and chunk.usage.prompt_tokens_details
                ):
                    if hasattr(chunk.usage.prompt_tokens_details, "cached_tokens"):
                        usage.cache_read_tokens = (
                            chunk.usage.prompt_tokens_details.cached_tokens
                        )
        return usage


class VertexGenAIClient(LLMClient):
    def init_client(self):
        from google import genai
        self.client = genai.Client()

    def preprocess_messages(
        self, system_message: str, messages: List[dict], tools: List[LLMTool] = None
    ):
        from google.genai import types

        if tools:
            tools = [
                types.Tool(
                    function_declarations=[
                        types.FunctionDeclaration(
                            name=tool.name,
                            description=tool.description,
                            parameters=self._build_tool_parameters_schema(tool),
                        )
                        for tool in tools
                    ]
                )
            ]
        system_message = system_message or next(
            (msg["content"] for msg in messages if msg.get("role") == "system"), None
        )
        thinking_config = types.ThinkingConfig(
            include_thoughts=True,
            thinking_budget=1024,
        )
        generation_config = types.GenerateContentConfig(
            system_instruction=system_message,
            temperature=0.0,
            thinking_config=thinking_config,
        )
        if tools:
            generation_config.tools = tools
            generation_config.automatic_function_calling = (
                types.AutomaticFunctionCallingConfig(disable=True)
            )
            generation_config.tool_config = types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(
                    mode=types.FunctionCallingConfigMode.AUTO
                )
            )

        contents: List[types.Content] = []

        def _get_parts_from_content(content):
            if isinstance(content, str):
                return [types.Part(text=content)]
            elif isinstance(content, list):
                parts = []
                for c in content:
                    if c.get("type") == "text":
                        parts.append(types.Part(text=c.get("text")))
                    elif c.get("type").startswith("image"):
                        image_bytes = base64.b64decode(
                            c["image_url"]["url"].split(",")[1]
                        )
                        mime_type = (
                            c["image_url"]["url"]
                            .split(",")[0]
                            .split(":")[1]
                            .split(";")[0]
                        )
                        parts.append(
                            types.Part(
                                image=types.Image(data=image_bytes, mime_type=mime_type)
                            )
                        )
                    elif c.get("type") == "thinking":
                        parts.append(
                            types.Part(
                                text=c.get("thinking") or "",
                                thought=True,
                                thought_signature=(
                                    c["signature"].encode("latin-1")
                                    if c.get("signature")
                                    else None
                                ),
                            )
                        )
                    else:
                        raise ValueError(f"Invalid content: {c}")
                return parts
            else:
                raise ValueError(f"Invalid content: {content}")

        tool_call_id_to_name = {}
        for msg in messages:
            if msg.get("role") == "user":
                contents.append(
                    types.Content(
                        parts=_get_parts_from_content(msg.get("content")), role="user"
                    )
                )
            elif msg.get("role") == "assistant":
                if msg.get("tool_calls"):
                    parts = []
                    for tool_call in msg.get("tool_calls"):
                        tool_call_id_to_name[tool_call["id"]] = tool_call[
                            "function"
                        ].get("name")
                        parts.append(
                            types.Part(
                                function_call=types.FunctionCall(
                                    id=tool_call["id"],
                                    name=tool_call["function"].get("name"),
                                    args=json.loads(
                                        tool_call["function"].get("arguments", "{}")
                                    ),
                                )
                            )
                        )
                    contents.append(types.Content(parts=parts, role="model"))
                else:
                    contents.append(
                        types.Content(
                            parts=_get_parts_from_content(msg.get("content")),
                            role="model",
                        )
                    )
            elif msg.get("role") == "tool":
                contents.append(
                    types.Content(
                        parts=[
                            types.Part(
                                function_response=types.FunctionResponse(
                                    id=msg.get("tool_call_id"),
                                    name=tool_call_id_to_name[msg.get("tool_call_id")],
                                    response={"result": msg.get("content")},
                                )
                            )
                        ],
                        role="user",
                    )
                )
            elif msg.get("role") == "system":
                pass

        return generation_config, contents

    async def get_response_stream_generator(
        self,
        system_message: str,
        messages: List[dict],
        tools: List[LLMTool] = None,
        thinking_budget: int = None,
        reasoning_effort: str = None,
        tool_choice=None,
        **kwargs,
    ) -> AsyncGenerator:
        generation_config, contents = self.preprocess_messages(
            system_message, messages, tools=tools
        )
        model = self.get_model_name()
        if "-think-" in model:
            budget = model.split("-think-")[1]
            generation_config.thinking_config.thinking_budget = int(budget)
            if generation_config.thinking_config.thinking_budget == 0:
                generation_config.thinking_config.include_thoughts = False
            model = model.split("-think-")[0]
        if thinking_budget is not None:
            generation_config.thinking_config.thinking_budget = thinking_budget
        if (
            generation_config
            and generation_config.thinking_config
            and generation_config.thinking_config.include_thoughts
            and not generation_config.thinking_config.thinking_budget
        ):
            generation_config.thinking_config.include_thoughts = False
        if tool_choice is not None:
            generation_config.tool_config.function_calling_config.mode = tool_choice
        print_util(
            json.dumps(
                {"model": model, "config": generation_config.to_json_dict()},
                indent=2,
                ensure_ascii=False,
            ),
            header="Client kwargs",
        )
        return await self.client.aio.models.generate_content_stream(
            model=model, contents=contents, config=generation_config
        )

    async def process_and_yield_from_response_chunk(self, chunk: Any):
        from google.genai import types

        chunk: types.GenerateContentResponse = chunk
        content = chunk.candidates[0].content if chunk.candidates else None
        if not content or not content.parts:
            return
        parts = content.parts
        function_call_id = None
        for part in parts:
            if part.text and part.thought:
                yield LLMChunk(thought=part.text)
            if part.thought_signature:
                yield LLMChunk(
                    thought_signature=part.thought_signature.decode("latin-1")
                )
            if part.text and not part.thought:
                yield LLMChunk(text=part.text)
            if part.function_call:
                function_call_id = (
                    uuid.uuid4().hex if part.function_call.name else function_call_id
                )
                yield LLMChunk(
                    tool_call_id=function_call_id,
                    tool_call_name=part.function_call.name,
                    tool_call_args=json.dumps(part.function_call.args)
                    if part.function_call.args
                    else "",
                    index=function_call_id,
                )

    def get_usage(self) -> LLMUsage:
        from google.genai import types

        usage = LLMUsage()
        for chunk in self.raw_response_chunks:
            chunk: types.GenerateContentResponse = chunk
            if chunk.usage_metadata:
                if chunk.usage_metadata.prompt_token_count:
                    usage.input_tokens = chunk.usage_metadata.prompt_token_count
                if chunk.usage_metadata.candidates_token_count:
                    usage.output_tokens = (
                        chunk.usage_metadata.candidates_token_count
                        + (chunk.usage_metadata.thoughts_token_count or 0)
                    )
                if chunk.usage_metadata.cached_content_token_count:
                    usage.cache_read_tokens = (
                        chunk.usage_metadata.cached_content_token_count
                    )
        return usage
