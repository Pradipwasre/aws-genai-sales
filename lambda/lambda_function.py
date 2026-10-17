import os, time, boto3
from openai import OpenAI

try:
    from dotenv import load_dotenv
    load_dotenv("../.env")   # only matters locally
except ImportError:
    pass

REGION = "us-east-1"
athena = boto3.client("athena", region_name=REGION)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SQL = """
SELECT region, SUM(sales) AS total_sales
FROM sales_data
GROUP BY region
ORDER BY total_sales DESC
"""

def run_athena(query):
    qid = athena.start_query_execution(
        QueryString=query,
        QueryExecutionContext={"Database": "salesdb"},
        ResultConfiguration={"OutputLocation": "s3://pradip-athena-results-859934688423/"},
    )["QueryExecutionId"]

    while True:
        status = athena.get_query_execution(QueryExecutionId=qid)["QueryExecution"]["Status"]
        if status["State"] in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
        time.sleep(1)
    if status["State"] != "SUCCEEDED":
        raise Exception(f"Athena failed: {status.get('StateChangeReason')}")

    rows = athena.get_query_results(QueryExecutionId=qid)["ResultSet"]["Rows"]
    return "\n".join(" | ".join(c.get("VarCharValue", "") for c in r["Data"]) for r in rows)

def lambda_handler(event, context):
    question = event.get("question", "Explain the sales performance.")
    athena_result = run_athena(SQL)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": f"You are a business analyst. Explain the data simply.\n\nAthena result:\n{athena_result}"},
            {"role": "user", "content": question},
        ],
    )
    return {"statusCode": 200, "body": response.choices[0].message.content}