from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, Field

from app.models.exercise import ExerciseType

MIN_OPTIONS = 2
MAX_OPTIONS = 10
MAX_SOLUTION_CHARS = 800


class Difficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class CatalogEntry(BaseModel):
    name: str
    count: int


class CatalogSubject(CatalogEntry):
    topics: list[CatalogEntry]


class QuestionCatalog(BaseModel):
    total: int
    subjects: list[CatalogSubject]
    boards: list[CatalogEntry]

    def topics_of(self, subject: str) -> set[str]:
        return {
            topic.name for item in self.subjects if item.name == subject for topic in item.topics
        }


class QuestionFilters(BaseModel):
    subject: str | None = None
    topics: list[str] = Field(default_factory=list)
    board: str | None = None
    year_from: int | None = None
    year_to: int | None = None


class ReferenceQuestion(BaseModel):
    subject: str
    topic: str
    board: str | None
    exam: str | None
    year: int | None
    statement: str
    answer: str | None


class GenerationBrief(BaseModel):
    prompt: str
    count: int
    type: ExerciseType | None
    difficulty: Difficulty | None


class GeneratedOption(BaseModel):
    text: str = Field(description="Option text without the letter prefix")
    is_correct: bool


class GeneratedQuestion(BaseModel):
    type: ExerciseType
    subject: str
    topic: str
    title: str = Field(description="Short title, at most 120 characters")
    statement: str = Field(description="Full self-contained statement, including any support text")
    explanation: str = Field(
        description="Step-by-step solution in Brazilian Portuguese, written before the options; "
        "it ends with the final result"
    )
    options: list[GeneratedOption] = Field(
        default_factory=list,
        description="multiple_choice only: 5 options, the correct one equal to the final result "
        "of the explanation; empty for open_answer",
    )
    expected_answer: str | None = Field(
        default=None, description="Model answer for open_answer, null for multiple_choice"
    )

    def is_valid(self) -> bool:
        if not self.title.strip() or not self.statement.strip():
            return False
        if self.type is ExerciseType.MULTIPLE_CHOICE:
            correct = sum(option.is_correct for option in self.options)
            return MIN_OPTIONS <= len(self.options) <= MAX_OPTIONS and correct == 1
        return not self.options and bool(self.expected_answer and self.expected_answer.strip())

    def correct_letter(self) -> str | None:
        for index, option in enumerate(self.options):
            if option.is_correct:
                return option_letter(index)
        return None


class GeneratedQuestionSet(BaseModel):
    questions: list[GeneratedQuestion]


class Verification(BaseModel):
    solution: str = Field(description="Your own step-by-step solution in Brazilian Portuguese")
    chosen_option: str | None = Field(
        default=None,
        description="multiple_choice only: the letter of the option your solution reaches",
    )
    answer_is_correct: bool | None = Field(
        default=None, description="open_answer only: whether the proposed answer is correct"
    )
    issues: list[str] = Field(
        default_factory=list,
        description="Only problems that make the question wrong, ambiguous, unsolvable or not "
        "self-contained, in Brazilian Portuguese; empty when the question is fine",
    )


def option_letter(index: int) -> str:
    return chr(ord("A") + index)


def verification_issues(question: GeneratedQuestion, verification: Verification) -> list[str]:
    issues = [issue.strip() for issue in verification.issues if issue.strip()]
    solution = verification.solution.strip()[:MAX_SOLUTION_CHARS]
    if question.type is ExerciseType.MULTIPLE_CHOICE:
        chosen = (verification.chosen_option or "").strip().upper()[:1] or None
        correct = question.correct_letter()
        if chosen != correct:
            issues.append(
                f"Um revisor independente resolveu a questão e chegou à alternativa "
                f"{chosen or 'nenhuma'}, mas a marcada como correta é a {correct}. "
                f"Resolução do revisor: {solution}"
            )
    elif verification.answer_is_correct is False:
        issues.append(
            "Um revisor independente considerou a resposta esperada incorreta. "
            f"Resolução do revisor: {solution}"
        )
    return issues


class QuestionGenerator(Protocol):
    async def choose_filters(self, prompt: str, catalog: QuestionCatalog) -> QuestionFilters: ...

    async def generate(
        self, brief: GenerationBrief, references: list[ReferenceQuestion]
    ) -> list[GeneratedQuestion]: ...

    async def revise(
        self,
        brief: GenerationBrief,
        references: list[ReferenceQuestion],
        previous: GeneratedQuestion,
        feedback: list[str],
    ) -> GeneratedQuestion: ...

    async def verify(self, question: GeneratedQuestion) -> Verification: ...
