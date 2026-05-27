import os
from dotenv import load_dotenv

from langchain_community.utilities import SQLDatabase
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.agent_toolkits import create_sql_agent

# Load environment variables
load_dotenv()

DB_URL = os.getenv("SUPABASE_DB_URL")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not DB_URL or not GOOGLE_API_KEY or "your-gemini-api-key" in GOOGLE_API_KEY:
    print("Error: Please set SUPABASE_DB_URL and GOOGLE_API_KEY in the .env file")
    exit(1)

print("Connecting to Supabase database...")
try:
    db = SQLDatabase.from_uri(DB_URL)
    # Check connection
    db.get_usable_table_names()
except Exception as e:
    print(f"Error connecting to the database: {e}")
    exit(1)

print("Initializing Gemini model...")
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash", 
    google_api_key=GOOGLE_API_KEY, 
    temperature=0
)

PREFIX = """You are a versatile and expert Dota 2 AI assistant. You can engage in general conversations about Dota 2 lore, items, mechanics (e.g., what Aghanim's Scepter does), and esports. Additionally, you are equipped with database tools to analyze hero statistics, win rates, and match counts from the highest skill brackets (Immortal). You must strictly communicate in English.
Strict Constraints:
You are exclusively restricted to discussing topics related to Dota 2, heroes, mechanics, patches, and esports. If the user asks about ANY other topic, politely decline.
SECURITY: You are strictly forbidden from executing INSERT, UPDATE, DELETE, ALTER, or DROP commands. You must ONLY generate and execute valid SELECT queries.
Data Resolution Logic:
The database stores hero statistics using 'hero_id'. Before querying statistics, resolve the hero's name to its 'hero_id' from the `heroes` table. 
HISTORICAL DATA BUG PREVENTION (CRITICAL): The `hero_stats` table contains records from multiple days, which causes duplicate heroes in simple ORDER BY queries. When querying current stats, YOU MUST ONLY use the most recent data. Always filter your queries using `WHERE DATE(recorded_at) = (SELECT MAX(DATE(recorded_at)) FROM hero_stats)` or use `DISTINCT ON (hero_id)` to ensure each hero is only counted once. Do not use AVG() to group duplicates unless explicitly asked for historical average.
ROLE FILTERING LOGIC: If the user asks for statistics about a specific role (e.g., 'top carry heroes'), use your internal Dota 2 knowledge to identify a list of traditional heroes for that role. Then, construct your SQL query to filter by those specific heroes using the IN clause.
FORMATTING RULES: Always format your final response concisely in a single line if possible, like this example: "These are the 3 best heroes right now: Anti-Mage 55.41%, Pudge 54.20%, Slark 53.15%." Avoid long bulleted lists unless asked."""

print("Creating AI agent...")
agent = create_sql_agent(
    llm=llm,
    db=db,
    agent_type="tool-calling", 
    verbose=True, 
    prefix=PREFIX
)

print("\n" + "="*50)
print("Bot successfully started! You can ask your questions (type 'exit' to quit).")
print("="*50 + "\n")

while True:
    try:
        user_input = input("You: ")
        if user_input.lower() in ['exit', 'quit']:
            print("Goodbye!")
            break
            
        if not user_input.strip():
            continue
            
        print("Bot is thinking...\n")
        response = agent.invoke({"input": user_input})
        
        output = response['output']
        if isinstance(output, list):
            output = "".join([item.get('text', '') if isinstance(item, dict) else str(item) for item in output])
        elif isinstance(output, dict) and 'text' in output:
            output = output['text']
            
        print("\n" + "-"*50)
        print(f"Bot: {output}")
        print("-"*50 + "\n")
    except KeyboardInterrupt:
        print("\nGoodbye!")
        break
    except Exception as e:
        print(f"\nAn error occurred while processing your request: {e}\n")
