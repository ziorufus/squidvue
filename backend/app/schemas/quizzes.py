from pydantic import BaseModel, Field


class QuestionIn(BaseModel):
    id: int | None = None
    position: int
    text: str
    question_type: str
    option_a: str | None = None
    option_b: str | None = None
    option_c: str | None = None
    option_d: str | None = None
    option_e: str | None = None
    correct_answer: str
    max_points: int = Field(ge=1)


class QuizIn(BaseModel):
    title: str
    question_time: int = Field(ge=1)
    countdown_time: int = Field(ge=1)
    emoji_pool: str = ''
    questions: list[QuestionIn]


class QuizOut(BaseModel):
    id: int
    code: str
    title: str
    question_time: int
    countdown_time: int
    emoji_pool: str
    status: str

    class Config:
        from_attributes = True
