import argparse
import asyncio
import os
import pandas as pd
from datetime import datetime
import json
import dotenv
from src.agent import JudgeAgent
from src.schemas import RagRow, EvaluationResult

# Load environment variables from .env file
dotenv.load_dotenv()

# Verify Gemini API key is set
if not os.environ.get("GEMINI_API_KEY"):
    raise ValueError("GEMINI_API_KEY not found in environment variables.")

DIMENSIONS = [
    "Relevance",
    "Groundedness",
    "Completeness",
    "Factual Accuracy",
    "Coherence",
    "Contextual Awareness",
]

WEIGHTS = {
    "Relevance": 0.25,
    "Groundedness": 0.25,
    "Completeness": 0.15,
    "Factual Accuracy": 0.15,
    "Coherence": 0.10,
    "Contextual Awareness": 0.10,
}

def generate_reports(results: list[EvaluationResult], output_dir: str):
    """
    Generates and saves the evaluation reports.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 1. Scored Dataset (CSV)
    results_df = pd.DataFrame([res.model_dump() for res in results])
    # Unpack the nested EvaluationScore dictionaries into separate columns
    for dim in DIMENSIONS:
        dim_lower = dim.lower().replace(" ", "_")
        results_df[f"{dim_lower}_score"] = results_df[dim_lower].apply(lambda x: x['score'])
        results_df[f"{dim_lower}_reasoning"] = results_df[dim_lower].apply(lambda x: x['reasoning'])
        results_df = results_df.drop(columns=[dim_lower])

    csv_path = os.path.join(output_dir, f"scored_dataset_{timestamp}.csv")
    results_df.to_csv(csv_path, index=False)
    print(f"Scored dataset saved to: {csv_path}")

    # 2. Aggregate Stats (JSON)
    agg_stats = {
        "total_rows_evaluated": len(results),
        "average_final_score": results_df["final_score"].mean(),
        "median_final_score": results_df["final_score"].median(),
        "std_dev_final_score": results_df["final_score"].std(),
        "per_dimension_stats": {
            dim: {
                "average_score": results_df[f"{dim.lower().replace(' ', '_')}_score"].mean(),
                "median_score": results_df[f"{dim.lower().replace(' ', '_')}_score"].median(),
                "std_dev_score": results_df[f"{dim.lower().replace(' ', '_')}_score"].std(),
            }
            for dim in DIMENSIONS
        },
    }
    json_path = os.path.join(output_dir, f"aggregate_stats_{timestamp}.json")
    with open(json_path, "w") as f:
        json.dump(agg_stats, f, indent=4)
    print(f"Aggregate stats saved to: {json_path}")

    # 3. Evaluation Report (Markdown)
    md_path = os.path.join(output_dir, f"evaluation_report_{timestamp}.md")
    with open(md_path, "w") as f:
        f.write("# RAG Evaluation Report\n\n")
        f.write(f"**Report generated on:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("## Executive Summary\n\n")
        f.write(f"- **Total Rows Evaluated:** {agg_stats['total_rows_evaluated']}\n")
        f.write(f"- **Average Final Score:** {agg_stats['average_final_score']:.2f}\n")
        f.write(f"- **Median Final Score:** {agg_stats['median_final_score']:.2f}\n\n")
        f.write("## Dimension-wise Analysis\n\n")
        f.write("| Dimension            | Average Score | Median Score | Std Dev |\n")
        f.write("|----------------------|---------------|--------------|---------|\n")
        for dim, stats in agg_stats["per_dimension_stats"].items():
            f.write(f"| {dim:<20} | {stats['average_score']:<13.2f} | {stats['median_score']:<12.2f} | {stats['std_dev_score']:<7.2f} |\n")
        f.write("\n")
        f.write("## Failure Case Analysis\n\n")
        f.write("Top 5 lowest-scoring rows:\n\n")
        lowest_scores = results_df.nsmallest(5, "final_score")
        for i, row in lowest_scores.iterrows():
            f.write(f"### Row Index: {i} (Final Score: {row['final_score']:.2f})\n")
            # This part assumes the original data is available alongside the results.
            # For simplicity, we'll just show the scores and reasonings.
            for dim in DIMENSIONS:
                dim_lower = dim.lower().replace(" ", "_")
                f.write(f"- **{dim}:** {row[f'{dim_lower}_score']} - *{row[f'{dim_lower}_reasoning']}*\n")
            f.write("\n")

    print(f"Markdown report saved to: {md_path}")

async def run_evaluation(args):
    """
    Runs the evaluation process for the given CSV file.
    """
    try:
        df = pd.read_csv(args.csv)
        df.fillna("", inplace=True)
    except FileNotFoundError:
        print(f"Error: The file '{args.csv}' was not found.")
        return

    results = []

    for i in range(len(df)):
        row = df.iloc[i]
        rag_row = RagRow(
            current_user_question=row.get("Current User Question", ""),
            conversation_history=row.get("Conversation History", ""),
            fragment_texts=row.get("Fragment Texts", ""),
            assistant_answer=row.get("Assistant Answer", ""),
        )

        scores = {}
        print(f"Evaluating row {i + 1}/{len(df)}...")

        for dimension in DIMENSIONS:
            print(f"  - Evaluating dimension: {dimension}")
            agent = JudgeAgent(
                dimension_name=dimension,
                temperature=args.temperature,
            )
            score = await agent.evaluate(rag_row)
            scores[dimension.lower().replace(" ", "_")] = score

        # Calculate final score
        final_score = sum(
            scores[dim.lower().replace(" ", "_")].score * WEIGHTS[dim] for dim in DIMENSIONS
        )

        evaluation_result = EvaluationResult(
            relevance=scores["relevance"],
            groundedness=scores["groundedness"],
            completeness=scores["completeness"],
            factual_accuracy=scores["factual_accuracy"],
            coherence=scores["coherence"],
            contextual_awareness=scores["contextual_awareness"],
            final_score=final_score,
        )
        results.append(evaluation_result)
        print(f"  - Final score for row {i + 1}: {final_score:.2f}")

    print("\nEvaluation complete.")
    generate_reports(results, args.output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate RAG answers using an AI Judge.")
    parser.add_argument("--csv", type=str, required=True, help="Path to the CSV file to evaluate.")
    parser.add_argument("--output", type=str, required=True, help="Directory to save the output reports.")
    parser.add_argument("--temperature", type=float, default=0.0, help="Temperature for the LLM.")

    args = parser.parse_args()
    asyncio.run(run_evaluation(args))