from __future__ import annotations

import os
import uuid
import random
from typing import Any, Dict, List, Optional, Literal

from config.settings import settings

# Observability (safe no-ops if not configured)
try:
	from src.utils.observability import observe, log_event
except Exception:
	def observe():
		def _noop(f):
			return f
		return _noop
	def log_event(*args, **kwargs):
		return False

# Gemini client
from google import genai
from google.genai import types

# LangGraph minimal use for state flow
from langgraph.graph import StateGraph, END
from pydantic import BaseModel


class GameState(BaseModel):
	game_id: str
	round: int
	max_rounds: int
	history: List[Dict[str, Any]]  # list of {question, user, ai_candidates, decision, guess, reason}
	current_question: str
	ai_candidates: List[str]  # 3 AI answers generated for current question
	status: Literal["ongoing", "ai_won", "human_won"]


class GuessingAI:
	def __init__(self):
		self.client = genai.Client(api_key=os.getenv("TONY_GOOGLE_API_KEY"))
		self.model = settings.gemini_model

	@observe()
	def decide(self, question: str, user_answer: str, ai_candidates: List[str]) -> Dict[str, Any]:
		"""
		Return decision: "respond" or "use_tool"; if respond, provide guess index (0..3) and reason.
		We show the model 4 anonymized answers: one is user, three are AIs.
		"""
		schema = {
			"type": "object",
			"properties": {
				"decision": {"type": "string", "enum": ["respond", "use_tool"]},
				"guess": {"type": "integer", "description": "Index of predicted human among [user, ai1, ai2, ai3]"},
				"reason": {"type": "string", "description": "Short explanation of why that answer seems human-generated"},
			},
			"required": ["decision"],
		}
		prompt = (
			"You are playing 'Guess Human'. You see 4 short answers to the same question. "
			"Exactly one is from a human, the other three are from AIs. "
			"Decide whether to guess now (respond) or ask for another distinguishing question (use_tool).\n\n"
			f"Question: {question}\n"
			f"Answers (index: text):\n"
			+ "\n".join([f"{i}: {a}" for i, a in enumerate([user_answer] + ai_candidates)])
			+ "\n\nRules:\n- If you are highly confident, set decision='respond' and give 'guess' index (0..3) for the human.\n"
			"- Always include a concise 'reason' explaining markers of human style for your choice.\n"
			"- Otherwise set decision='use_tool'."
		)
		cfg = types.GenerateContentConfig(
			temperature=settings.ai_temperature,
			max_output_tokens=200,
			response_mime_type="application/json",
			response_schema=schema,  # structured output
		)
		resp = self.client.models.generate_content(model=self.model, contents=prompt, config=cfg)
		import json
		try:
			data = json.loads((resp.text or "{}").strip()) if resp else {}
		except Exception:
			data = {"decision": "use_tool", "reason": "Could not parse; ask another question."}
		return data or {"decision": "use_tool"}


class QuestionTool:
	def __init__(self):
		self.client = genai.Client(api_key=os.getenv("TONY_GOOGLE_API_KEY"))
		self.model = settings.gemini_model

	@observe()
	def generate_initial_question(self) -> str:
		"""Generate five creative, short discriminative questions and pick one randomly."""
		schema = {
			"type": "object",
			"properties": {
				"questions": {
					"type": "array",
					"items": {"type": "string"},
					"minItems": 5,
					"maxItems": 5
				}
			},
			"required": ["questions"],
		}
		prompt = (
			"Your task is to identify who is the real human player among 4 players. "
			"The human is trying to pretend to be an AI. "
			"Ask smart, short questions (max ~20 words) to distinguish human from AI style.\n\n"
			"Return 5 different, creative, varied questions as JSON only: {\"questions\":[...]}."
		)
		cfg = types.GenerateContentConfig(
			temperature=0.7,
			max_output_tokens=200,
			response_mime_type="application/json",
			response_schema=schema,
		)
		resp = self.client.models.generate_content(model=self.model, contents=prompt, config=cfg)
		import json
		try:
			data = json.loads((resp.text or "{}").strip()) if resp else {}
			qs = [q.strip() for q in (data.get("questions") or []) if isinstance(q, str)]
			if len(qs) >= 5:
				return random.choice(qs)
		except Exception:
			pass
		return "In one sentence, how would you approach solving an unfamiliar problem?"

	@observe()
	def generate_new_question(self, history: List[Dict[str, Any]]) -> str:
		"""
		Given full game history, produce 3-5 improved, short discriminative questions and pick one randomly.
		"""
		history_text = "\n\n".join(
			[f"Q: {h.get('question')}\nUser: {h.get('user')}\nAI candidates: {h.get('ai_candidates')}\nDecision: {h.get('decision')}\nReason: {h.get('reason')}" for h in history]
		)
		schema = {
			"type": "object",
			"properties": {
				"questions": {
					"type": "array",
					"items": {"type": "string"},
					"minItems": 3,
					"maxItems": 5
				}
			},
			"required": ["questions"],
		}
		prompt = (
			"We are playing 'Guess Human'. Based on the past rounds (questions and all 4 answers), "
			"propose improved, short questions (max ~20 words) that better distinguish a human from AI.\n\n"
			f"Past results:\n{history_text}\n\n"
			"Return JSON only: {\"questions\":[...]} with 3 to 5 options."
		)
		cfg = types.GenerateContentConfig(
			temperature=0.6,
			max_output_tokens=200,
			response_mime_type="application/json",
			response_schema=schema,
		)
		resp = self.client.models.generate_content(model=self.model, contents=prompt, config=cfg)
		import json
		try:
			data = json.loads((resp.text or "{}").strip()) if resp else {}
			qs = [q.strip() for q in (data.get("questions") or []) if isinstance(q, str)]
			if len(qs) >= 1:
				return random.choice(qs)
		except Exception:
			pass
		return "Give one sentence describing a subtle preference you have in daily life."

	def generate_ai_candidates(self, question: str) -> List[str]:
		"""
		Ask Gemini to produce 3 distinct, short answers likely from AIs in a single structured output.
		"""
		schema = {
			"type": "object",
			"properties": {
				"answers": {
					"type": "array",
					"items": {"type": "string"},
					"minItems": 3,
					"maxItems": 3,
				}
			}
		}
		prompt = (
			"Create three distinct, concise answers (1 sentence each) to the following question, "
			"written in a neutral AI style. Return only JSON with field 'answers' (3 items).\n\n"
			f"Question: {question}"
		)
		cfg = types.GenerateContentConfig(
			temperature=0.3,
			max_output_tokens=120,
			response_mime_type="application/json",
			response_schema=schema,
		)
		resp = self.client.models.generate_content(model=self.model, contents=prompt, config=cfg)
		import json
		try:
			data = json.loads((resp.text or "{}").strip()) if resp else {}
			answers = data.get("answers") or []
			answers = [a.strip() for a in answers if isinstance(a, str)]
			if len(answers) >= 3:
				return answers[:3]
		except Exception:
			pass
		# Fallback
		return [
			"I would choose a practical option based on available data.",
			"My response depends on optimizing for clear objectives and constraints.",
			"I would consider trade-offs and select the most consistent approach.",
		]


class GameEngine:
	def __init__(self):
		self.ai = GuessingAI()
		self.tool = QuestionTool()

	def start(self) -> GameState:
		game_id = str(uuid.uuid4())
		first_question = self.tool.generate_initial_question()
		ai_candidates = self.tool.generate_ai_candidates(first_question)
		return GameState(
			game_id=game_id,
			round=1,
			max_rounds=settings.max_questions,
			history=[],
			current_question=first_question,
			ai_candidates=ai_candidates,
			status="ongoing",
		)

	def step(self, state: GameState, user_answer: str) -> Dict[str, Any]:
		# Collect answers ordered as [user, ai1, ai2, ai3]
		decision = self.ai.decide(state.current_question, user_answer, state.ai_candidates)
		dec = (decision.get("decision") or "use_tool").strip()
		guess = decision.get("guess")
		reason = decision.get("reason")

		state.history.append({
			"question": state.current_question,
			"user": user_answer,
			"ai_candidates": state.ai_candidates,
			"decision": dec,
			"guess": guess,
			"reason": reason,
		})

		if dec == "respond":
			# guess index is among 0..3 where 0 is user
			winner = "ai" if (isinstance(guess, int) and guess == 0) else "human"
			state.status = "ai_won" if winner == "ai" else "human_won"
			return {
				"decision": dec,
				"guess": int(guess) if isinstance(guess, int) else None,
				"round": state.round,
				"is_game_over": True,
				"winner": winner,
				"reason": reason,
			}

		# use_tool path
		if state.round >= state.max_rounds:
			state.status = "human_won"
			return {
				"decision": dec,
				"round": state.round,
				"is_game_over": True,
				"winner": "human",
				"reason": reason,
			}

		# Ask a new question (history-informed, pick randomly from LLM list)
		new_question = self.tool.generate_new_question(state.history)
		ai_candidates = self.tool.generate_ai_candidates(new_question)
		state.round += 1
		state.current_question = new_question
		state.ai_candidates = ai_candidates
		return {
			"decision": dec,
			"question": new_question,
			"ai_candidates": ai_candidates,
			"round": state.round,
			"is_game_over": False,
			"reason": reason,
		}


class GameOrchestrator:
	"""Thin wrapper exposing async methods used by FastAPI routes."""
	def __init__(self):
		self.engine = GameEngine()
		self._sessions: Dict[str, GameState] = {}

	async def start_game(self) -> Dict[str, Any]:
		state = self.engine.start()
		self._sessions[state.game_id] = state
		log_event("game_started", input=None, output={"game_id": state.game_id})
		return {
			"game_id": state.game_id,
			"round": state.round,
			"current_question": state.current_question,
			"ai_candidates": state.ai_candidates,
		}

	async def process_user_answer(self, game_id: str, user_answer: str) -> Dict[str, Any]:
		state = self._sessions.get(game_id)
		if not state:
			from fastapi import HTTPException
			raise HTTPException(status_code=404, detail="Game session not found")
		res = self.engine.step(state, user_answer)
		if res.get("is_game_over"):
			log_event("game_finished", input={"game_id": game_id}, output=res)
			# cleanup
			self._sessions.pop(game_id, None)
		else:
			log_event("game_progress", input={"game_id": game_id}, output=res)
		return res
