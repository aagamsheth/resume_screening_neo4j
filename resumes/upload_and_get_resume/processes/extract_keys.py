from upload_and_get_resume.utils.extract_text_link import extract_text_and_links
from upload_and_get_resume.utils.save_json import save_analysis_to_json, parse_response_to_json
from upload_and_get_resume.utils.vectorise_v1 import store_resume_to_neo4j
from upload_and_get_resume.utils.upload_dropbox import save_to_dropbox
import os
from dotenv import load_dotenv
import asyncio
import nest_asyncio
from groq import AsyncGroq, Groq
from openai import AsyncOpenAI
from contextlib import AsyncExitStack
from mcp.client.sse import sse_client
from mcp import ClientSession
from typing import Any, Dict, List
import json
import time
import re
import shutil
import dropbox
from dropbox.files import WriteMode
import logging


logging.basicConfig(
    filename="logs/extract_keys.log",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

loop = asyncio.get_event_loop()
if "uvloop" not in str(type(loop)):
    nest_asyncio.apply()

load_dotenv()

GROQ_MODEL = os.getenv("GROQ_MODEL")
OPENAI_API_MODEL = os.getenv("OPENAI_API_MODEL")
session = None
exit_stack = AsyncExitStack()
groq_client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
stdio = None
write = None

# Connect to Server (Async)
async def connect_to_server():
    """Connect to an MCP server."""
    global session, stdio, write, exit_stack

    try:
        # Connect to the server
        stdio_transport = await exit_stack.enter_async_context(
            sse_client("http://0.0.0.0:8050/sse")
        )
        stdio, write = stdio_transport
        session = await exit_stack.enter_async_context(ClientSession(stdio, write))

        # Initialize the connection
        await session.initialize()

        # Print success message
        print("\n Successfully connected to MCP server!")
        logging.info("Successfully connected to MCP server!")
        # List available tools
        tools_result = await session.list_tools()
        print("Available tools:")
        for tool in tools_result.tools:
            print(f"  - {tool.name}: {tool.description}")


    except Exception as e:
        print(f"\n Failed to connect to MCP server: {str(e)}")
        logging.error(f"Failed to connect to MCP server: {str(e)}")
        raise

# Get MCP Tools
async def get_mcp_tools() -> List[Dict[str, Any]]:
    """Get available tools from the MCP server in Groq-compatible and OpenAi-compatible format."""
    global session

    try:
        tools_result = await session.list_tools()
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema,
                },
            }
            for tool in tools_result.tools
        ]
    except Exception as e:
        print(f"[ERROR] Failed to fetch tools: {str(e)}")
        logging.error(f"Failed to fetch tools: {str(e)}")
        return []

# Cleanup (Async)
async def cleanup():
    """Clean up resources."""
    global exit_stack
    try:
        await exit_stack.aclose()
        print("\n[DEBUG] Resources cleaned up successfully")
        logging.info("Resources cleaned up successfully")
    except Exception as e:
        print(f"[ERROR] Cleanup failed: {str(e)}")
        logging.error(f"Cleanup failed: {str(e)}")

# Process Details
async def process_details(details, links):
    """
    Process extracted details and links to generate a structured evaluation report.
    parameters:
    details (str): Candidate's resume text
    links (str): Candidate's provided links
    return:
    str: Structured evaluation report
    """
    try:
        global session, groq_client #,openai_client

        # Get tool list from MCP server
        tools = await get_mcp_tools()

        if not tools:
            print("[DEBUG] No tools available from MCP server")
            logging.warning("No tools available from MCP server")
        
        # First call to  LLM to check if any tools are needed or not else analyse the resume and give response in mentioned format.

        # Uncomment below three lines to Use Groq instead of Openai and Comment first three lines of the openai_client chat completions

        # response = await openai_client.chat.completions.create(   
        #     model=OPENAI_API_MODEL,
        #     max_completion_tokens = 2048,
        response = await groq_client.chat.completions.create(
            model=GROQ_MODEL,
            max_tokens=2048,
            temperature=0.1,
            messages=[
                {
                    "role": "system",
                    "content": f"""
You are a senior talent acquisition specialist and industry expert across all professional domains. Your task is to analyze the candidate's resume ({details}) and provided links ({links}) to create a structured evaluation report. Follow these instructions precisely to ensure consistent output for programmatic parsing.

**CRITICAL INSTRUCTIONS** (do not include in output):
1. Use EXACTLY the headers and structure specified in the MANDATORY RESPONSE FORMAT below.
2. Do not add extra headers, change indentation, or deviate from the format.
3. If information is missing, use 'N/A' or 'Not specified' as specified.
4. Extract the candidate's full name from {details}. Names may belong to any global ethnicity or culture. Scan the entire resume (headers, footers, metadata) multiple times if needed. If no name is found, use LinkedIn patterns or email prefixes as clues, or assign 'Unknown Candidate [UUID]' and log as a red flag.
5. For Years of Experience, return a float (e.g., '1.2' for 1 year 2 months). Use '0' for freshers or if experience is unclear/not mentioned. Do not use 'plus' or '+'.
6. Under SKILLS, list sub-categories with a bullet point for the header only, not individual skills. Start sub-category content on a new line.
7. Proactively use tools (e.g., Google search, company website verification) to validate employer legitimacy, role responsibilities, and industry standards.
8. Be brutally honest and evidence-based. Do not inflate or sugar-coat evaluations.
9. Handle edge cases (e.g., missing data, non-standard resume formats) by cross-referencing links or inferring from context.

**CANDIDATE EVALUATION FRAMEWORK**:
- **Resume Analysis**: Extract years of experience, career progression, role transitions, skills (technical, creative, analytical, interpersonal), project complexity, team sizes, budget responsibility, leadership experience, certifications, and industry-specific achievements.
- **Links Evaluation**: Visit all {links} (LinkedIn, portfolios, etc.) to assess work quality, project outcomes, professional posts, personal branding, and consistency with resume claims.
- **Company Verification**: Research employers for legitimacy and reputation. Verify role responsibilities against company size and industry context. Check for timeline consistency or red flags.
- **Field-Specific Criteria**:
  - Experience: Does it match industry role requirements?
  - Seniority: Are there unrealistic jumps in responsibility?
  - Skills: Depth vs. breadth in relevant areas.
  - Leadership: Evidence of decision-making, strategic thinking.
  - Industry Knowledge: Understanding of market dynamics, standards.
  - Standards: Adherence to regulations, ethics, best practices.

**MANDATORY RESPONSE FORMAT**:
=== CANDIDATE PROFILE ===
Name: [Full name from resume or fallback]
Gender: [From resume or infer from name/evidence]
Age: [From resume/DOB or 'N/A']
E-mail: [From resume or 'N/A']
Phone number: [From resume or 'N/A']
Location: [From resume or infer from evidence]
Preferred Location: [From resume or 'N/A']
Interests/Hobbies: [From resume or 'N/A']
Years of Experience: [Float, e.g., '1.2' or '0']
Current/Last Designation: [Latest role or 'N/A' or 'Fresher']
Current/Last Employer: [Latest employer or 'N/A' or 'Fresher']
Current Notice Period: [From resume or 'N/A']
Expected CTC: [From resume or 'N/A']
Current CTC: [From resume or 'N/A']
Previous Employer: [List all previous employers, including internships, or 'N/A']

=== EDUCATION ===
Institution: 
- Degree/Program: [From resume]
- Grades/CGPA/Percentage: [From resume or 'N/A']
- Year of Passing: [From resume or 'N/A']
[Repeat for each institution]

=== SKILLS ===
[Sub-category]:
  [Skills, one per line, no bullet points]
[Repeat for each sub-category]

=== LANGUAGES ===
[List spoken languages from resume, if none found write 'N/A']

=== PROJECTS ===
[List projects from resume or 'N/A']

=== ACHIEVEMENTS ===
[List achievements from resume or 'N/A']

=== SUITABLE ROLES ===
[List roles from resume or inferred suitable roles]

=== LINKS ===
[Title]: [URL]
[Repeat for each link]

=== DETAILED ANALYSIS ===
**Experience Assessment**:
[Compare experience to industry standards]

**Skill Evaluation**:
[Assess skills and competencies]

**Strengths**:
[Key strengths]

**Weaknesses/Gaps**:
[Areas needing improvement]

**Red Flags**:
[Inconsistencies or concerns]

**Market Reality Check**:
[Comparison to industry standards]
"""
,
                },
                {"role": "user", "content": details},
                {"role": "user", "content": links},
            ],
            # tools=tools,
            # tool_choice="auto",
        )

        print("\n[DEBUG] Initial response received")
        logging.info("Initial response received")
        choice = response.choices[0]
        assistant_message = choice.message.content or ""
        assistant_content = []

        if choice.message.content:
            assistant_content.append({"type": "text", "text": choice.message.content})

        # Handle tool calls if present
        tool_calls = choice.message.tool_calls or []
        for tool_call in tool_calls:
            assistant_message += f"[Tool call: {tool_call.function.name}]"
            assistant_content.append(
                {
                    "type": "tool_use",
                    "id": tool_call.id,
                    "name": tool_call.function.name,
                    "input": json.loads(tool_call.function.arguments),
                }
            )

        messages = [
            {"role": "user", "content": details},
            {"role": "assistant", "content": assistant_message},
        ]

        if tool_calls:
            messages[-1]["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in tool_calls
            ]

        # Process tool calls if present
        if tool_calls:

            for tool_call in tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)
                tool_id = tool_call.id

                # print(f"[DEBUG] Tool call: {tool_name} with args: {tool_args}")

                try:
                    result = await session.call_tool(tool_name, arguments=tool_args)
                    tool_result = (
                        result.content[0].text if result.content else "No result"
                    )
                    # print(f"[DEBUG] Tool result: {tool_result}")

                    # Store tool results to be added to user message
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_id,
                            "name": tool_name,
                            "content": tool_result,
                        }
                    )

                except Exception as e:
                    print(f"[ERROR] Tool execution failed for {tool_name}: {str(e)}")
                    logging.error(f"Tool execution failed for {tool_name}: {str(e)}")
                    # Store error result
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_id,
                            "name": tool_name,
                            "content": f"Error: {str(e)}",
                        }
                    )

            # Add tool results to messages
            

            # Final Groq/OpenAi call with tool results and an enhanced synthesis prompt
            # Uncomment below three lines to use Groq AI and Comment openai_client chat completions first three lines.

            # response = await openai_client.chat.completions.create(   
            #     model=OPENAI_API_MODEL,
            #     max_completion_tokens = 4096,
            final_response = await groq_client.chat.completions.create(
                model=GROQ_MODEL,
                max_tokens=4096,
                temperature=0.1,
                messages=[
                    {
                        "role": "system",
                        "content": f"""
You are a senior talent acquisition director finalizing a structured evaluation report based on resume analysis, link verification, and tool results. Synthesize all data into a concise, evidence-based report. Follow the EXACT format below to ensure programmatic parsing.

**CRITICAL INSTRUCTIONS** (do not include in output):
1. Use EXACTLY the headers and structure specified below.
2. Do not add extra headers, change indentation, or deviate from the format.
3. If information is missing, use 'N/A' or 'Not specified' as specified.
4. Ensure candidate name is accurate, scanning {details} multiple times if needed. Use LinkedIn or email prefixes as fallbacks, or assign 'Unknown Candidate [UUID]' and log as a red flag.
5. Years of Experience must be a float (e.g., '1.2' for 1 year 2 months). Use '0' for freshers or unclear data. Avoid 'plus' or '+'.
6. SKILLS sub-categories have a bullet point for the header only, with skills listed on new lines without bullet points.
7. Cross-reference tool results (e.g., company verification, industry benchmarks) to validate claims.
8. Be brutally honest, evidence-based, and concise. Do not inflate evaluations.
9. Handle edge cases by inferring from context or links when resume data is incomplete.

**MANDATORY RESPONSE FORMAT**:
=== CANDIDATE PROFILE ===
Name: [Full name from resume or fallback]
Gender: [From resume or infer from name/evidence]
Age: [From resume/DOB or 'N/A']
E-mail: [From resume or 'N/A']
Phone number: [From resume or 'N/A']
Location: [From resume or infer from evidence]
Preferred Location: [From resume or 'N/A']
Interests/Hobbies: [From resume or 'N/A']
Years of Experience: [Float, e.g., '1.2' or '0']
Current/Last Designation: [Latest role or 'N/A' or 'Fresher']
Current/Last Employer: [Latest employer or 'N/A' or 'Fresher']
Current Notice Period: [From resume or 'N/A']
Expected CTC: [From resume or 'N/A']
Current CTC: [From resume or 'N/A']
Previous Employer: [List all previous employers, including internships, or 'N/A']

=== EDUCATION ===
Institution: 
- Degree/Program: [From resume]
- Grades/CGPA/Percentage: [From resume or 'N/A']
- Year of Passing: [From resume or 'N/A']
[Repeat for each institution]

=== SKILLS ===
[Sub-category]:
  [Skills, one per line, no bullet points]
[Repeat for each sub-category]

=== LANGUAGES ===
[List spoken languages from resume, if none found write 'N/A']

=== PROJECTS ===
[List projects from resume or 'N/A']

=== ACHIEVEMENTS ===
[List achievements from resume or 'N/A']

=== SUITABLE ROLES ===
[List roles from resume or inferred suitable roles]

=== LINKS ===
[Title]: [URL]
[Repeat for each link]

=== DETAILED ANALYSIS ===
**Experience Assessment**:
[Compare experience to industry standards]

**Skill Evaluation**:
[Assess skills and competencies]

**Strengths**:
[Key strengths]

**Weaknesses/Gaps**:
[Areas needing improvement]

**Red Flags**:
[Inconsistencies or concerns]

**Market Reality Check**:
[Comparison to industry standards]
"""
,
                    },
                    *messages,
                ],
            )

            print("[DEBUG] Final response received after tool execution")
            logging.info("Final response received after tool execution")
            # Extract final response
            final_message = final_response.choices[0].message.content
            return final_message if final_message else "No final response received"

        print("[DEBUG] No tool calls, returning assistant message")
        logging.info("No tool calls, returning assistant message")
        return assistant_message if assistant_message else "No response received"

    except Exception as e:
        print(f"[ERROR] Unable to extract keys from resume : {e}")
        logging.error(f"Unable to extract keys from resume: {e}")

def sanitize_filename(name):
    try:
        return re.sub(r'[\\/*?:"<>|]', "", name)
    except Exception as e:
        print(f"[ERROR] Failed to sanitize filename '{name}': {e}")
        logging.error(f"Failed to sanitize filename '{name}': {e}")

# Get Unique Output Paths
def get_unique_output_paths(output_dir, base_name):
    """
    Makes Unique path for the resume and Json by checking local storage if some other candidate with same name exists or not.
    """
    i = 0
    while True:
        resume_filename = f"{base_name}_{i}.pdf"
        json_filename = f"{base_name}_{i}_Analysis_Report.json"

        resume_path = os.path.join(output_dir, resume_filename)
        json_path = os.path.join(
            "/analysis_json",
            json_filename,
        )
        if not os.path.exists(resume_path) and not os.path.exists(json_path):
            return resume_path, json_path, i
        i += 1

# Extract Keys (Async)
async def extract_keys(file_path):
    """
    Extraction of text and keys from the resume and processing.

    Parameters:
    file_path (str): The path to the resume file.

    Returns:
    dict: A dictionary containing the parsed resume data and analysis report.
    """
    try:
        response = None
        if os.path.dirname(file_path):
            # Extract Text and links from the resume
            details, links = extract_text_and_links(file_path=file_path)

            # print(f"[DEBUG] Extracted details: {details}")
            # print(f"[DEBUG] Extracted links: {links}")

            # Connect to MCP server
            await connect_to_server()

            # Process all the detailes and links extracted from resume using LLM
            response = await process_details(details=details, links=links)

            if response is None:
                response = "No response received from the server."
            
            # print(f"[DEBUG] Response from server: {response}")
            
            # Convert whole response received into Json and also extract Years of Experience from that.
            json_data, years_of_experience = parse_response_to_json(response)
            
            # Make File name using candidate's name
            candidate_name = sanitize_filename(json_data["candidate_profile"]["name"])
            print(candidate_name)

            """
            Below Block is to save tha Json file and the resume of the candidate into local machine.
            """
            # output_resume_dir = (
            #     "<Your local path where you want to save resume>"
            # )
            # output_json_dir = (
            #     "<Your local path where you want to save json>"
            # )

            # os.makedirs(output_resume_dir, exist_ok=True)
            # os.makedirs(output_json_dir, exist_ok=True)
            # resume_path, json_path, version = get_unique_output_paths(
            #     output_resume_dir, candidate_name
            # )

            # shutil.move(file_path, resume_path)

            # await save_analysis_to_json(json_data, json_path)

            # Save Resume and Json to Dropbox
            dropbox_result = await save_to_dropbox(file_path, json_data, candidate_name)
            if not dropbox_result:
                print("[ERROR] Dropbox upload failed")
                logging.error("Dropbox upload failed")
                return None

            print(f"[INFO] Resume and JSON saved to Dropbox: {dropbox_result}")
            logging.info(f"Resume and JSON saved to Dropbox: {dropbox_result}")
            # Stores All the data into Neo4J Graph DB by converting all the data into nodes and connecting them with relevent reletionships(edges)
            await  store_resume_to_neo4j(
                details=response,
                resume_file_path=dropbox_result["resume_link"],
                json_file_path=dropbox_result["json_link"],
                years_of_experience=years_of_experience,
            )
            print(f"[INFO] Saved as version _{dropbox_result['version']}")
            logging.info(f"Saved as version _{dropbox_result['version']}")
            # print(f"[INFO] Saved as version _{version}")
            # logging.info(f"Saved as version _{version}")
            return json_data
    except Exception as e:
        print(f"[ERROR] An error occurred while extracting keys: {e}")
        logging.error(f"An error occurred while extracting keys: {e}")
        raise e
    finally:
        # Cleanup
        await cleanup()



