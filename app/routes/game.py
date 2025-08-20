from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from src.orchestrator import GameOrchestrator

router = APIRouter()

orchestrator = GameOrchestrator()


class StartResponse(BaseModel):
	question: str
	round: int
	ai_candidates: List[str]
	game_id: str


class UserAnswer(BaseModel):
	game_id: str
	answer: str


class AnswerResponse(BaseModel):
	decision: str  # "respond" | "use_tool"
	guess: Optional[int] = None  # index among [user(0), ai1(1), ai2(2), ai3(3)]
	question: Optional[str] = None
	round: int
	ai_candidates: Optional[List[str]] = None
	is_game_over: bool
	winner: Optional[str] = None
	reason: Optional[str] = None


@router.post("/start", response_model=StartResponse)
async def start() -> StartResponse:
	try:
		state = await orchestrator.start_game()
		return StartResponse(
			question=state["current_question"],
			round=state["round"],
			ai_candidates=state["ai_candidates"],
			game_id=state["game_id"],
		)
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@router.post("/answer", response_model=AnswerResponse)
async def answer(payload: UserAnswer) -> AnswerResponse:
	try:
		result = await orchestrator.process_user_answer(game_id=payload.game_id, user_answer=payload.answer)
		return AnswerResponse(**result)
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))
