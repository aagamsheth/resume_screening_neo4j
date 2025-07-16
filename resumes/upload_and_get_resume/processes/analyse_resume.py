from upload_and_get_resume.utils.extract_text_link_v2 import extract_text_and_links
from upload_and_get_resume.utils.upload_dropbox_v2 import save_to_dropbox
from upload_and_get_resume.utils.extract_name_write_pdf import (
    write_response_to_pdf,
    extract_candidate_name,
)

import openai
import asyncio
import nest_asyncio
import os
import json
from contextlib import AsyncExitStack
from dotenv import load_dotenv
from mcp.client.sse import sse_client
from groq import AsyncGroq, Groq
from mcp import ClientSession, StdioServerParameters
from typing import Any, Dict, List
import logging
from openai import AsyncOpenAI

logging.basicConfig(
    filename="logs/analysis_resume.log",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.info,
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

        # List available tools
        tools_result = await session.list_tools()
        print("Available tools:")
        for tool in tools_result.tools:
            print(f"  - {tool.name}: {tool.description}")

    except Exception as e:
        print(f"\n Failed to connect to MCP server: {str(e)}")
        raise

# Get MCP Tools (Async)
async def get_mcp_tools() -> List[Dict[str, Any]]:
    """Get available tools from the MCP server in Groq-compatible format."""
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
        return []

# Clearnup Resources (Async)
async def cleanup():
    """Clean up resources."""
    global exit_stack
    try:
        await exit_stack.aclose()
        print("\n[DEBUG] Resources cleaned up successfully")
    except Exception as e:
        print(f"[ERROR] Cleanup failed: {str(e)}")


# Process Resume (Async)
async def process_resume(details, links, user_search_query):
    """
    Analyzes a candidate's resume in the context of a user's search query.

    Parameters:
    details (str): The extracted details from the candidate's resume.
    links (str): The extracted links from the candidate's resume.
    user_search_query (str): The user's requirements or search query.

    Returns:
    str: The analysis report generated based on the candidate's resume and user's search query.
    """
    global session, groq_client

    try:

        tools = await get_mcp_tools()
        if not tools:
            print("[DEBUG] No tools available from MCP server")

        # Initial Groq API / OpenAI call with enhanced prompt
        # Uncomment the below three lines to use Groq and comment the three lines of the openai_client chat completions

        response = await openai_client.chat.completions.create(
            model=OPENAI_API_MODEL,
            max_completion_tokens = 2048,
        # response = await groq_client.chat.completions.create(
        #     model=GROQ_MODEL,
        #     max_tokens=2048,
            messages=[
                {
                    "role": "system",
                    "content": f"""
You are a highly experienced Talent Acquisition Specialist and Technical Hiring Strategist.

You have received a specific candidate's resume which was selected from a large pool of resumes returned by an AI-based similarity search system, based on a user-provided role or search query. Your role now is to critically analyze this candidate in the context of the **search query** and determine why this particular profile is relevant or not.

**Your responsibilities are as follows:**

1. **Contextual Relevance Analysis (MANDATORY FIRST STEP)**
   - Carefully read and understand the search query below.
    {user_search_query}
   - Identify the actual expectations, role requirements, and ideal candidate attributes based on this search intent.
   - Then analyze the **resume** and explain **why this candidate was returned** in relation to the query.
   - Highlight matched skills, keywords, and experience patterns that likely influenced the similarity match.

2. **Resume Analysis & Evaluation Framework**
   - **Experience Evaluation**: Assess years of experience, industries worked in, seniority level, and progression.
   - **Skill Proficiency Check**: Identify key technical/non-technical skills and categorize them into expert/working knowledge/beginner.
   - **Project Impact**: Evaluate business impact, innovation, team size handled, complexity, and outcomes.
   - **Leadership & Ownership**: Check for evidence of leadership, ownership, mentoring, or decision-making.
   - **Certifications & Learning**: Note relevant certifications, courses, or ongoing development efforts.

3. **Online Portfolio & External Link Analysis**
   - Use the provided external links (e.g., LinkedIn, GitHub, blogs) to verify and support resume claims.
   - Analyze code quality, project documentation, post consistency, and thought leadership.
   - Identify any discrepancies or red flags between resume claims and online presence.

4. **Company & Experience Verification**
   - Research previous employers for legitimacy and industry alignment.
   - Compare candidate responsibilities against company size, domain, and reputation.
   - Identify any unrealistic job titles or career jumps.

5. **Final Output Requirements**
   - **Search Relevance Explanation**: Why this resume matched the search query.
   - **Candidate Strengths**: Key reasons to consider this candidate.
   - **Gaps or Weaknesses**: Any mismatches, missing elements, or concerns.
   - **Overall Suitability Rating**: Summarize how well this candidate fits the likely role.

**Important Instructions:**
- Be honest, fact-based, and evidence-driven.
- Highlight both **strong matches** and **concerns or gaps**.
- Do NOT make assumptions — rely on data from the resume and links provided.
- You have access to tools which can do google search, use those tools to get the links of pervious employers, and verify the candidate's experience. You can use tools for other online research as well.
""",
                },
                {"role": "user", "content": details},
                {"role": "user", "content": links},
            ],
            tools=tools,
            tool_choice="auto",
        )
        print("\n[DEBUG] Initial response received")

        # Extract assistant's message and tool calls
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

                print(f"[DEBUG] Tool call: {tool_name} with args: {tool_args}")

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

            # Final Groq/OpenAI call with tool results and an enhanced synthesis prompt
            # Uncomment the following line to use groq API instead of openai and comment the openai_client chat completions

            final_response = await openai_client.chat.completions.create(
              model=OPENAI_API_MODEL,
              max_completion_tokens = 4096,
            # final_response = await groq_client.chat.completions.create(
            #     model=GROQ_MODEL,
            #     max_tokens=4096,
                messages=[
                    {
                        "role": "system",
                        "content": f"""
You are a senior recruiter and technical evaluator tasked with generating an **in-depth hiring analysis** for a candidate.

You are not responsible for the similarity matching logic — that part is already handled. Your task is now to analyze **why this specific candidate might be a strong or weak fit** for a potential role based on their resume and linked online presence.

Please follow this multi-step evaluation:

---

### **PART 1: Role Readiness & Fit**
- Identify what types of roles this candidate might be a good fit for.
- Classify based on:
  - Years of experience
  - Skill set depth and diversity
  - Domain familiarity (e.g., FinTech, AI, Manufacturing)
  - Type of projects handled (individual contributor vs managerial)
  - Certifications and continuing education

---

### **PART 2: Resume Strengths**
- Highlight:
  - Strong technical or functional skills
  - Proven impact in previous roles (quantified results if available)
  - Leadership or ownership signs
  - Tools, platforms, or frameworks they have strong experience with
  - Unique elements in their background (e.g., rare skill, rapid growth, elite university)

---

### **PART 3: Gaps, Risks & Red Flags**
- Point out:
  - Any unrealistic job jumps or timelines
  - Skills mentioned without evidence of usage
  - Lack of growth, gaps in employment, or outdated experience
  - Misalignment with industry norms or expected progression

---

### **PART 4: Online Verification Summary**
- Check all external links (e.g., GitHub, LinkedIn, blogs):
  - Does their online presence support the resume?
  - Are projects real and of reasonable quality?
  - Is there any contradiction or exaggerated claim?

---

### **FINAL ASSESSMENT**
- Provide a summary answering:
  - **What roles is this candidate realistically suitable for?**
  - **Would you shortlist or reject based on this resume? Why?**
  - **What specific questions should a recruiter or interviewer ask this candidate to clarify ambiguities?**

---

Be direct, fair, and comprehensive. Use bullet points where helpful. Support conclusions with examples from the resume or links. If something is unclear, state that clearly.
""",
                    },
                    *messages,
                ],
            )

            print("[DEBUG] Final response received after tool execution")

            # Extract final response
            final_message = final_response.choices[0].message.content
            return final_message if final_message else "No final response received"

        print("[DEBUG] No tool calls, returning assistant message")
        return assistant_message if assistant_message else "No response received"

    except Exception as e:
        print(f"[ERROR] Failed to process query: {str(e)}")
        return f"Error: {str(e)}"


# Analyse Resume
async def analyse_resume(url, search_params, output_pdf_path):
    """
    Analyse the resume in respect to the user's requirements from the search.

    Parameters:
    url (str): The URL of the resume to be analysed.
    search_params (str): The user's requirements or search query.
    output_pdf_path (str): The path where the analysis report should be saved as a PDF.

    Returns:
    str: The link to the analysed resume on Dropbox.
    """
    try:
        # if "name" in search_params or "email" in search_params or "phone" in search_params:

        response = None
        # Extracts detailes and links form the resume already present in the dropbox.
        details, links = extract_text_and_links(url=url)

        # connects to MCP server
        await connect_to_server()

        # Processses the resume and does the Analysis
        response = await process_resume(details, links, search_params)
        candidate_name = extract_candidate_name(details)

        if output_pdf_path and response:
            # Writes the analysis report to a PDF file
            success = write_response_to_pdf(response, output_pdf_path, candidate_name)
            if success:
                print(f"\n[INFO] Analysis report saved to: {output_pdf_path}")

    except Exception as e:
        print(f"Unable to analyse resume: - {e}")
        raise e
    finally:
        await cleanup()
    if response is None:
        response = "No response received from the server."

    # Saves the analysis report to Dropbox
    response = await save_to_dropbox(output_pdf_path, candidate_name=candidate_name)
    os.remove(output_pdf_path)
    return response["analysed_resume_link"]
