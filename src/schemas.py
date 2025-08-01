from pydantic import BaseModel, Field

class EvaluationScore(BaseModel):
    """A model to structure the output for a single evaluation dimension."""
    score: int = Field(..., description="The score from 0 to 10.", ge=0, le=10)
    reasoning: str = Field(..., description="The reasoning behind the score.")

class EvaluationResult(BaseModel):
    """A model to aggregate the scores for all dimensions for a single row of data."""
    relevance: EvaluationScore
    groundedness: EvaluationScore
    completeness: EvaluationScore
    factual_accuracy: EvaluationScore
    coherence: EvaluationScore
    contextual_awareness: EvaluationScore
    final_score: float = Field(..., description="The final weighted score.")

class RagRow(BaseModel):
    """Represents a single row from the RAG evaluation CSV."""
    current_user_question: str
    conversation_history: str
    fragment_texts: str
    assistant_answer: str