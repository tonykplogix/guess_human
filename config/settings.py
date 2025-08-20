"""
Application settings for Guess Human app
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
	# Server
	host: str = "0.0.0.0"
	port: int = 8000
	debug: bool = True

	# Paths
	upload_dir: str = "./uploads"
	static_dir: str = "./static"
	database_url: str = "sqlite:///./database/guess_human.db"

	# AI
	ai_temperature: float = 0.3
	ai_top_p: float = 0.9
	ai_max_tokens: int = 256
	gemini_model: str = "gemini-2.5-flash-lite"

	# Game
	max_questions: int = 3

	# Env
	model_config = {"env_file": ".env", "case_sensitive": False, "extra": "ignore"}


settings = Settings()
