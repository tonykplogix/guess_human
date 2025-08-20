"""
Observability helpers for Langfuse with safe fallbacks.
"""
from __future__ import annotations
from typing import Any, Optional, Dict

_observe = None
_client = None


def _init_client():
	global _client
	if _client is not None:
		return _client
	try:
		from langfuse import Langfuse  # type: ignore
		_client = Langfuse()
	except Exception:
		_client = None
	return _client


def get_client():
	return _init_client()


def log_event(name: str, input: Any = None, output: Any = None, metadata: Optional[Dict[str, Any]] = None):
	client = _init_client()
	if not client:
		return False
	try:
		client.event(name=name, input=input, output=output, metadata=metadata or {})
		return True
	except Exception:
		return False


def observe():  # decorator factory compatible with @observe()
	global _observe
	if _observe is None:
		try:
			from langfuse.decorators import observe as _obs  # type: ignore
			_observe = _obs
		except Exception:
			def _noop_decorator(func):
				return func
			_observe = _noop_decorator
	return _observe
