import asyncio
from dataclasses import dataclass
from pydantic import ValidationError
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.models.gemini import GeminiModel
from pydantic_ai.settings import ModelSettings
from src.schemas import RagRow, EvaluationScore

# The dependency for the agent is the row data, which changes for each evaluation.
@dataclass
class EvaluationDependencies:
    row: RagRow

class JudgeAgent:
    """
    An agent that evaluates a RAG system's response based on a specific dimension.
    """
    _agent: Agent[EvaluationDependencies, EvaluationScore]

    def __init__(self, dimension_name: str, temperature: float):
        """
        Initializes the JudgeAgent for a specific evaluation dimension.

        Args:
            dimension_name: The name of the evaluation dimension (e.g., "relevance").
            temperature: The temperature for the LLM.
        """
        model = GeminiModel('gemini-2.0-flash')

        # Temperature is passed via ModelSettings to the Agent.
        model_settings = ModelSettings(
            temperature=temperature,
        )

        system_prompt = f"""
        You are an impartial AI evaluator. Your task is to assess the quality of an AI assistant's answer based on the dimension: '{dimension_name}'.

        **Instructions:**
        1.  Review the user's question, conversation history, the context provided, and the assistant's answer.
        2.  Evaluate the assistant's answer ONLY on the '{dimension_name}' dimension.
        3.  Provide a score from 0 to 10, where 0 is the worst and 10 is the best.
        4.  Provide a concise reasoning for your score.
        5.  Return ONLY the score and reasoning in the specified format.
        """

        self._agent = Agent(
            model,
            deps_type=EvaluationDependencies,
            output_type=EvaluationScore,
            system_prompt=system_prompt,
            model_settings=model_settings,
        )

    async def evaluate(self, row: RagRow) -> EvaluationScore:
        """
        Evaluates a single row of RAG data for the specified dimension with retry logic.

        Args:
            row: A RagRow object containing the data to be evaluated.

        Returns:
            An EvaluationScore object with the score and reasoning.
        """
        deps = EvaluationDependencies(row=row)
        history_section = (
            f"Conversation History:\n{row.conversation_history}\n"
            if row.conversation_history and row.conversation_history.strip()
            else "Conversation History:\nNo previous conversation history.\n"
        )

        user_prompt = f"""
        **Evaluation Data:**
        User Question:
        {row.current_user_question}

        {history_section}
        Context Provided to Assistant:
        {row.fragment_texts}

        Assistant's Answer:
        {row.assistant_answer}
        """

        max_retries = 3
        for attempt in range(max_retries):
            try:
                result = await self._agent.run(user_prompt, deps=deps)
                return result.output
            except ModelHTTPError as e:
                if e.status_code == 503 and attempt < max_retries - 1:
                    wait_time = 2 ** (attempt + 1)
                    print(f"  - Model is overloaded. Retrying in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                else:
                    print(f"  - Evaluation failed after {max_retries} retries: {e}")
                    return EvaluationScore(score=0, reasoning=f"API error: {e}")
            except ValidationError as e:
                if attempt < max_retries - 1:
                    print("  - Model returned an invalid score. Retrying...")
        
        return EvaluationScore(score=0, reasoning="Evaluation failed after all retries.")