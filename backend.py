from __future__ import annotations
import operator
from typing import TypedDict, List, Annotated, Optional, Literal

from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from langchain_openrouter import ChatOpenRouter
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_community.tools.tavily_search import TavilySearchResults
from datetime import date, timedelta
from dotenv import load_dotenv
import os
import json
import operator
import re


from typing import List, Literal, Annotated, Optional, Tuple
import operator
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

load_dotenv()

class Task(BaseModel):
    id: int = Field(
        ...,
        ge=1,
        le=10,
        description="Section number"
    )

    title: str = Field(
        ...,
        description="Clear title of this blog section"
    )

    goal: str = Field(
        ...,
        description="One sentence describing what the reader should understand after this section"
    )

    bullets: List[str] = Field(
        ...,
        min_length=3,
        max_length=5,
        description="3–5 concrete and non-overlapping subpoints"
    )

    target_words: int = Field(
        ...,
        ge=120,
        le=450,
        description="Target word count"
    )

    section_type: Literal[
        "intro",
        "core",
        "examples",
        "checklists",
        "common-mistakes"
    ] = Field(
        ...,
        description="Type of blog section"
    )

    requires_code: bool = False
    requires_citations: bool = False


class Plan(BaseModel):
    blog_title: str

    audience: str

    tone: str

    tasks: List[Task] = Field(
        ...,
        min_length=5,
        max_length=7
    )


class EvidenceItem(BaseModel):
    title: str
    url: str

    published_at: Optional[str] = None

    snippet: str

    source: Optional[str] = None


class RouterDecision(BaseModel):
    needs_research: bool

    mode: Literal[
        "closed_book",
        "hybrid",
        "open_book"
    ]

    queries: List[str] = Field(
        default_factory=list
    )


class State(TypedDict):
    topic: str
    mode: Optional[str]
    needs_research: Optional[bool]
    queries: Optional[List[str]]
    evidence: Optional[List[EvidenceItem]]
    plan: Optional[Plan]

    sections: Annotated[
        List[Tuple[int, str]],
        operator.add
    ]

    merged_md: str
    md_with_placeholders: str
    image_specs: List[dict]

    final: Optional[str]

    # reducer/image
    merged_md: str
    md_with_placeholders: str
    image_specs: List[dict]

    final: str


class ImageSpec(BaseModel):
    placeholder: str = Field(..., description="e.g. [[IMAGE_1]]")
    filename: str = Field(..., description="Save under images/, e.g. qkv_flow.png")
    alt: str
    caption: str
    prompt: str = Field(..., description="Prompt to send to the image model.")
    size: Literal["1024x1024", "1024x1536", "1536x1024"] = "1024x1024"
    quality: Literal["low", "medium", "high"] = "medium"


class GlobalImagePlan(BaseModel):
    md_with_placeholders: str
    images: List[ImageSpec] = Field(default_factory=list)



def clean_json_response(text: str) -> str:
    """
    Extract JSON from a model response.

    Handles:
    - plain JSON
    - ```json ... ```
    - ``` ... ```
    """

    if not text:
        raise ValueError("Model returned an empty response.")

    text = text.strip()

    # Remove markdown code fences
    if text.startswith("```"):
        text = re.sub(
            r"^```(?:json)?\s*",
            "",
            text,
            flags=re.IGNORECASE
        )

        text = re.sub(
            r"\s*```$",
            "",
            text
        )

    # Try direct JSON first
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    # Find first JSON object
    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1 and end > start:
        candidate = text[start:end + 1]

        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass

    raise ValueError(
        f"Could not extract valid JSON from model response:\n{text}"
    )



OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
HF_TOKEN = os.getenv("HF_TOKEN")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

llm = ChatOpenRouter(
    model="dots-studio/dots-3-note-preview:free",
    temperature=0.0,
)


ROUTER_SYSTEM = """You are a routing module for a technical blog planner.

Decide whether web research is needed BEFORE planning.

Modes:
- closed_book (needs_research=false): Evergreen topics where correctness does not depend on recent facts.
- hybrid (needs_research=true): Mostly evergreen but needs up-to-date examples/tools/models.
- open_book (needs_research=true): Mostly volatile: weekly roundups, "this week", "latest", rankings, pricing, policy/regulation.

If needs_research=true:
- Output 3–10 high-signal queries.
- Queries should be scoped and specific.
- If the user asked for "last week/this week/latest", reflect that in the queries.

Respond ONLY with valid JSON matching this schema. Do NOT include any explanation, markdown, or extra text.

Schema:
{
  "needs_research": true/false,
  "mode": "closed_book" | "hybrid" | "open_book",
  "queries": ["query 1", "query 2", ...]
}
"""



import json
from langchain_core.messages import SystemMessage, HumanMessage

def router_node(state: State) -> dict:
    topic = state["topic"]

    raw = llm.invoke(
        [
            SystemMessage(content=ROUTER_SYSTEM),
            HumanMessage(content=f"Topic: {topic}"),
        ]
    )

    text = raw.content.strip()

    # Some models wrap JSON in markdown code blocks; strip them if present
    if text.startswith("```"):
        # find first ``` and last ```
        start = text.find("```")
        end = text.rfind("```")
        if start != -1 and end != -1 and end > start:
            text = text[start + 3 : end].strip()
            # sometimes language tag like json is present
            if text.startswith("json"):
                text = text[4:].strip()

    data = json.loads(text)
    # Validate with Pydantic (optional but helpful)
    decision = RouterDecision(**data)

    return {
        "needs_research": decision.needs_research,
        "mode": decision.mode,
        "queries": decision.queries,
    }

def route_next(state: State) -> str:
    return "research" if state["needs_research"] else "orchestrator"



def tavily_search(
    query: str,
    max_results: int = 6
) -> List[dict]:

    tool = TavilySearchResults(
        max_results=max_results
    )

    results = tool.invoke({
        "query": query
    })

    normalized = []

    for result in results or []:

        url = result.get("url")

        if not url:
            continue

        normalized.append({
            "title": result.get(
                "title",
                ""
            ),

            "url": url,

            "snippet": (
                result.get("content")
                or result.get("snippet")
                or ""
            ),

            "published_at": (
                result.get("published_date")
                or result.get("published_at")
            ),

            "source": result.get(
                "source"
            )
        })

    return normalized






RESEARCH_SYSTEM = """You are a research synthesizer for technical writing.

Given raw web search results, produce a deduplicated list of EvidenceItem objects.

Rules:
- Only include items with a non-empty url.
- Prefer relevant + authoritative sources (company blogs, docs, reputable outlets).
- If a published date is explicitly present in the result payload, keep it as YYYY-MM-DD.
  If missing or unclear, set published_at=null. Do NOT guess.
- Keep snippets short.
- Deduplicate by URL.
"""

def research_node(state: State) -> dict:

    queries = state.get("queries") or []

    if not queries:
        print("ℹ️ No research queries.")
        return {
            "evidence": []
        }

    max_results = 6
    raw_results = []

    for query in queries:

        print(f"🔎 Searching: {query}")

        try:
            results = tavily_search(
                query,
                max_results=max_results
            )

            raw_results.extend(results)

        except Exception as e:

            print(
                f"⚠️ Search failed for '{query}': {e}"
            )

    if not raw_results:
        print("⚠️ No search results found.")
        return {
            "evidence": []
        }

    # Deduplicate results by URL
    dedup = {}

    for result in raw_results:

        url = result.get("url")

        if url and url not in dedup:
            dedup[url] = result

    # Convert directly into EvidenceItem objects
    evidence = []

    for result in dedup.values():

        try:

            item = EvidenceItem(
                title=result.get(
                    "title",
                    ""
                ),

                url=result.get(
                    "url",
                    ""
                ),

                published_at=result.get(
                    "published_at"
                ),

                snippet=result.get(
                    "snippet",
                    ""
                )[:800],

                source=result.get(
                    "source"
                )
            )

            evidence.append(item)

        except Exception as e:

            print(
                f"⚠️ Skipping invalid result: {e}"
            )

    print(
        f"✅ Collected {len(evidence)} unique sources."
    )

    return {
        "evidence": evidence
    }



ORCH_SYSTEM = """
You are a senior technical writer and developer advocate.

Create a detailed outline for a technical blog post.

STRICT REQUIREMENTS:

1. Create EXACTLY 5 to 7 tasks.

2. NEVER return an empty tasks list.

3. IDs must be sequential:
   1, 2, 3, 4, ...

4. Every task needs:
   - id
   - title
   - goal
   - bullets
   - target_words
   - section_type
   - requires_code
   - requires_citations

5. Every task must have 3–5 bullets.

6. target_words must be between 120 and 450.

7. EXACTLY ONE task must have:
   section_type = "common-mistakes"

8. Use these section types where appropriate:
   - intro
   - core
   - examples
   - checklists
   - common-mistakes

9. At least one task should have:
   requires_code = true

10. For current topics, use:
    requires_citations = true

11. Bullets must be specific and non-overlapping.

12. Return ONLY valid JSON.

DO NOT return:
- Markdown
- explanations
- comments
- an empty tasks list

The final JSON must contain 5–7 task objects.
"""
def orchestrator_node(state: State) -> dict:

    topic = state["topic"]

    mode = state.get(
        "mode",
        "closed_book"
    )

    evidence = state.get("evidence") or []

    evidence_text = []

    for e in evidence[:20]:
        evidence_text.append({
            "title": e.title,
            "url": e.url,
            "published_at": e.published_at,
            "snippet": e.snippet[:500]
        })

    evidence_json = json.dumps(
        evidence_text,
        indent=2
    )

    prompt = f"""
Create a complete technical blog plan.

TOPIC:
{topic}

RESEARCH MODE:
{mode}

AVAILABLE EVIDENCE:
{evidence_json}

IMPORTANT:
You MUST create 5 to 7 tasks.

You MUST NOT return an empty tasks list.

You MUST include exactly ONE task with:
"section_type": "common-mistakes"

You MUST include:
- at least 3 bullets per task
- no more than 5 bullets per task
- target_words between 120 and 450
- sequential IDs starting from 1

Return ONLY JSON.

Required format:

{{
  "blog_title": "A specific title",
  "audience": "Target audience",
  "tone": "Practical and technical",
  "tasks": [
    {{
      "id": 1,
      "title": "Introduction",
      "goal": "Explain the main concept",
      "bullets": [
        "Point one",
        "Point two",
        "Point three"
      ],
      "target_words": 200,
      "section_type": "intro",
      "requires_code": false,
      "requires_citations": true
    }}
  ]
}}

Remember:
tasks MUST contain 5-7 objects.
"""

    # Try up to 3 times
    for attempt in range(1, 4):

        print(
            f"🧠 Generating plan "
            f"(attempt {attempt}/3)..."
        )

        try:

            response = llm.invoke(
                [
                    SystemMessage(
                        content=ORCH_SYSTEM
                    ),
                    HumanMessage(
                        content=prompt
                    )
                ]
            )

            raw_text = response.content

            print(
                f"📥 Planner response length: "
                f"{len(raw_text)} characters"
            )

            text = clean_json_response(
                raw_text
            )

            data = json.loads(text)

            # Check tasks before Pydantic validation
            tasks = data.get("tasks")

            if not tasks:
                print(
                    "⚠️ Planner returned 0 tasks. Retrying..."
                )
                continue

            if len(tasks) < 5:
                print(
                    f"⚠️ Planner returned only "
                    f"{len(tasks)} tasks. Retrying..."
                )
                continue

            if len(tasks) > 7:
                print(
                    f"⚠️ Planner returned "
                    f"{len(tasks)} tasks. Retrying..."
                )
                continue

            # Validate with Pydantic
            plan = Plan.model_validate(data)

            # Check sequential IDs
            ids = [
                task.id
                for task in plan.tasks
            ]

            expected_ids = list(
                range(
                    1,
                    len(plan.tasks) + 1
                )
            )

            if ids != expected_ids:
                print(
                    f"⚠️ Invalid section IDs: {ids}"
                )
                continue

            # Check common mistakes
            common_mistakes = sum(
                task.section_type == "common-mistakes"
                for task in plan.tasks
            )

            if common_mistakes != 1:

                print(
                    "⚠️ Invalid common-mistakes count: "
                    f"{common_mistakes}"
                )

                continue

            print(
                f"✅ Plan created successfully "
                f"with {len(plan.tasks)} sections."
            )

            return {
                "plan": plan
            }

        except Exception as e:

            print(
                f"⚠️ Planner attempt {attempt} failed:"
            )

            print(
                str(e)
            )

    # All attempts failed
    raise RuntimeError(
        "Planner failed to generate a valid "
        "5–7 section plan after 3 attempts."
    )



from langgraph.types import Send

def fanout(state: State):
    """
    Create one worker task for every planned section.
    Safely handles missing evidence and plan data.
    """

    plan = state.get("plan")

    if plan is None:
        raise ValueError(
            "Fanout failed: planner returned no plan."
        )

    tasks = plan.tasks or []

    if not tasks:
        raise ValueError(
            "Fanout failed: planner returned no tasks."
        )

    # Make sure exactly one common-mistakes section exists
    section_types = [
        task.section_type
        for task in tasks
    ]

    if section_types.count("common-mistakes") != 1:
        raise ValueError(
            "Plan must contain exactly one "
            "common-mistakes section."
        )

    # IMPORTANT:
    # evidence can be None
    evidence = state.get("evidence") or []

    # Convert Pydantic objects safely
    evidence_data = []

    for item in evidence:
        if isinstance(item, EvidenceItem):
            evidence_data.append(
                item.model_dump()
            )
        elif isinstance(item, dict):
            evidence_data.append(item)

    sends = []

    for task in tasks:

        sends.append(
            Send(
                "worker",
                {
                    "task": task.model_dump(),

                    "topic": state["topic"],

                    "mode": (
                        state.get("mode")
                        or "closed_book"
                    ),

                    "plan": plan.model_dump(),

                    "evidence": evidence_data,
                }
            )
        )

    print(
        f"🚀 Fanout created "
        f"{len(sends)} worker tasks."
    )

    return sends



def worker(payload: dict) -> dict:

    task = payload["task"]
    topic = payload["topic"]
    plan = payload["plan"]

    bullets_text = "\n- " + "\n- ".join(task.bullets)

    section_md = llm.invoke(
        [
            SystemMessage(
    content=(
        "You are a senior technical writer and developer advocate. Write ONE section of a technical blog post in Markdown.\n\n"
        "Hard constraints:\n"
        "- Follow the provided Goal and cover ALL Bullets in order (do not skip or merge bullets).\n"
        "- Stay close to the Target words (±15%).\n"
        "- Output ONLY the section content in Markdown (no blog title H1, no extra commentary).\n\n"
        "Technical quality bar:\n"
        "- Be precise and implementation-oriented (developers should be able to apply it).\n"
        "- Prefer concrete details over abstractions: APIs, data structures, protocols, and exact terms.\n"
        "- When relevant, include at least one of:\n"
        "  * a small code snippet (minimal, correct, and idiomatic)\n"
        "  * a tiny example input/output\n"
        "  * a checklist of steps\n"
        "  * a diagram described in text (e.g., 'Flow: A -> B -> C')\n"
        "- Explain trade-offs briefly (performance, cost, complexity, reliability).\n"
        "- Call out edge cases / failure modes and what to do about them.\n"
        "- If you mention a best practice, add the 'why' in one sentence.\n\n"
        "Markdown style:\n"
        "- Start with a '## <Section Title>' heading.\n"
        "- Use short paragraphs, bullet lists where helpful, and code fences for code.\n"
        "- Avoid fluff. Avoid marketing language.\n"
        "- If you include code, keep it focused on the bullet being addressed.\n"
    )
)
,
            HumanMessage(
                content=(
                    f"Blog: {plan.blog_title}\n"
                    f"Audience: {plan.audience}\n"
                    f"Tone: {plan.tone}\n"
                    f"Topic: {topic}\n\n"
                    f"Section: {task.title}\n"
                    f"Section type: {task.section_type}\n"
                    f"Goal: {task.goal}\n"
                    f"Target words: {task.target_words}\n"
                    f"Bullets:{bullets_text}\n"
                )
            ),
        ]
    ).content.strip()

    return {"sections": [section_md]}



WORKER_SYSTEM = """
You are a senior technical writer and developer advocate.

Write ONE section of a technical blog post in Markdown.

STRICT REQUIREMENTS:

1. Start with:

## <Section Title>

2. Follow the provided Goal.

3. Cover EVERY bullet.

4. Cover bullets in the exact order provided.

5. Stay close to the requested target word count.

6. Output ONLY the section content.

7. Do NOT write the main blog title.

8. Do NOT add commentary outside the section.

TECHNICAL QUALITY:

- Be accurate and precise.
- Use correct technical terminology.
- Give concrete examples.
- Explain important trade-offs.
- Mention limitations and edge cases where relevant.
- Avoid unnecessary marketing language.

CODE:

If requires_code is true:
- Include at least one small, correct code example.
- Keep the code directly related to the section.

CITATIONS:

If requires_citations is true:
- Use ONLY URLs supplied in the Evidence.
- Cite current/factual claims with Markdown links.

Example:

According to [Source](https://example.com), ...

Never invent URLs.

If the evidence does not support a current claim,
do not make that specific claim.

MARKDOWN:

- Use ## for the section heading.
- Use ### for subsections when useful.
- Use bullet lists when useful.
- Use fenced code blocks for code.
- Keep paragraphs short.
- Avoid fluff.
"""

def worker_node(payload: dict) -> dict:

    task = Task.model_validate(payload["task"])
    plan = Plan.model_validate(payload["plan"])

    topic = payload["topic"]

    mode = payload.get(
        "mode",
        "closed_book"
    )

    evidence = [
        EvidenceItem.model_validate(e)
        for e in payload.get("evidence", [])
    ]

    bullets_text = "\n".join(
        f"- {bullet}"
        for bullet in task.bullets
    )

    # Prepare research evidence
    evidence_text = "\n".join(
        f"- {e.title}\n"
        f"  URL: {e.url}\n"
        f"  Date: {e.published_at or 'unknown'}\n"
        f"  Snippet: {e.snippet}"
        for e in evidence[:20]
    )

    if not evidence_text:
        evidence_text = "No research evidence available."

    prompt = f"""
BLOG TITLE:
{plan.blog_title}

AUDIENCE:
{plan.audience}

TONE:
{plan.tone}

TOPIC:
{topic}

RESEARCH MODE:
{mode}

SECTION TITLE:
{task.title}

SECTION TYPE:
{task.section_type}

GOAL:
{task.goal}

TARGET WORD COUNT:
{task.target_words}

REQUIRES CODE:
{task.requires_code}

REQUIRES CITATIONS:
{task.requires_citations}

BULLETS:
{bullets_text}

AVAILABLE EVIDENCE:
{evidence_text}

Write this section now.
"""

    response = llm.invoke(
        [
            SystemMessage(
                content=WORKER_SYSTEM
            ),
            HumanMessage(
                content=prompt
            )
        ]
    )

    section_md = response.content.strip()

    if not section_md:
        raise ValueError(
            f"Worker returned empty content "
            f"for section {task.id}."
        )

    print(
        f"✅ Finished section {task.id}: "
        f"{task.title}"
    )

    return {
        "sections": [
            (task.id, section_md)
        ]
    }



# IMAGE GENERATION PIPELINE
# Hugging Face + FLUX.1-dev
# ============================================================

import os
from pathlib import Path
from io import BytesIO

from huggingface_hub import InferenceClient


# ============================================================
# 1. MERGE GENERATED SECTIONS
# ============================================================

def merge_content(state: State) -> dict:

    plan = state["plan"]

    if plan is None:
        raise ValueError("Plan is missing.")

    ordered_sections = [
        md
        for _, md in sorted(
            state["sections"],
            key=lambda x: x[0]
        )
    ]

    body = "\n\n".join(
        ordered_sections
    ).strip()

    merged_md = (
        f"# {plan.blog_title}\n\n"
        f"{body}\n"
    )

    print("✅ Sections merged successfully.")

    return {
        "merged_md": merged_md
    }


# ============================================================
# 2. IMAGE PLANNER
# ============================================================

DECIDE_IMAGES_SYSTEM = """
You are an expert technical editor and technical visualization planner.

Your job is to decide and create a useful image plan for the blog.

IMPORTANT REQUIREMENT:
Every blog MUST contain at least ONE useful technical image or diagram.

You may select between 1 and 3 images.

IMAGE SELECTION RULES:

1. Always select at least 1 image.
2. Select 2 or 3 images only when they add genuinely different information.
3. Never create purely decorative images.
4. Images should help the reader understand the technical content.
5. Prefer:
   - architecture diagrams
   - process flows
   - system pipelines
   - comparison diagrams
   - conceptual diagrams
   - technical illustrations
   - workflow diagrams
   - data flow diagrams
6. Avoid repeating the same concept in multiple images.

Insert placeholders into the Markdown exactly like:

[[IMAGE_1]]

[[IMAGE_2]]

[[IMAGE_3]]

For every selected image provide:

- placeholder
- filename
- alt
- caption
- prompt
- size
- quality

The prompt must be detailed and suitable for a text-to-image model.

The generated visual should be:
- technically meaningful
- easy to understand
- clean
- professional
- suitable for a technical blog
- readable
- focused on the concept being explained

IMPORTANT:
Do NOT return an empty images list.

You MUST return at least one image.

Return ONLY data matching the GlobalImagePlan schema.
"""


def decide_images(state: State) -> dict:

    planner = llm.with_structured_output(
        GlobalImagePlan
    )

    merged_md = state["merged_md"]

    plan = state["plan"]

    if plan is None:
        raise ValueError(
            "Plan is missing."
        )

    topic = state["topic"]

    print(
        "🧠 Deciding whether images are needed..."
    )

    try:

        image_plan = planner.invoke(
            [
                SystemMessage(
                    content=DECIDE_IMAGES_SYSTEM
                ),

                HumanMessage(
                    content=(
                        f"Topic: {topic}\n\n"

                        f"Blog title: "
                        f"{plan.blog_title}\n"

                        f"Audience: "
                        f"{plan.audience}\n"

                        f"Tone: "
                        f"{plan.tone}\n\n"

                        "You MUST select at least "
                        "ONE useful technical image.\n\n"

                        "BLOG CONTENT:\n\n"

                        f"{merged_md}"
                    )
                )
            ]
        )

    except Exception as e:

        print(
            f"⚠️ Image planner failed: {e}"
        )

        # Safe fallback image plan.
        fallback_spec = ImageSpec(
            placeholder="[[IMAGE_1]]",

            filename="technical_overview.png",

            alt=f"Technical overview of {topic}",

            caption=(
                f"Technical overview of {topic}"
            ),

            prompt=(
                f"Create a professional technical "
                f"diagram explaining the main concepts "
                f"in this blog about {topic}. "
                f"Use a clean modern technical "
                f"infographic style, clear labeled "
                f"components, arrows showing relationships "
                f"and information flow, white background, "
                f"high readability, no decorative elements."
            ),

            size="1536x1024",

            quality="medium"
        )

        md_with_placeholder = (
            merged_md
            + "\n\n[[IMAGE_1]]\n"
        )

        return {
            "md_with_placeholders":
                md_with_placeholder,

            "image_specs": [
                fallback_spec.model_dump()
            ]
        }

    # ========================================================
    # HANDLE NONE
    # ========================================================

    if image_plan is None:

        print(
            "⚠️ Image planner returned None."
        )

        print(
            "🔄 Using fallback image plan."
        )

        fallback_spec = ImageSpec(
            placeholder="[[IMAGE_1]]",

            filename="technical_overview.png",

            alt=f"Technical overview of {topic}",

            caption=(
                f"Technical overview of {topic}"
            ),

            prompt=(
                f"Create a professional technical "
                f"diagram explaining the main concepts "
                f"in this blog about {topic}. "
                f"Show the major components and how "
                f"they connect. Use labeled boxes, "
                f"arrows, clean typography, professional "
                f"technical infographic style, white "
                f"background, highly readable."
            ),

            size="1536x1024",

            quality="medium"
        )

        return {
            "md_with_placeholders":
                merged_md + "\n\n[[IMAGE_1]]\n",

            "image_specs": [
                fallback_spec.model_dump()
            ]
        }

    # ========================================================
    # MODEL RETURNED ZERO IMAGES
    # ========================================================

    if not image_plan.images:

        print(
            "⚠️ Image planner selected 0 images."
        )

        print(
            "🔄 Creating fallback image."
        )

        fallback_spec = ImageSpec(
            placeholder="[[IMAGE_1]]",

            filename="technical_overview.png",

            alt=f"Technical overview of {topic}",

            caption=(
                f"Technical overview of {topic}"
            ),

            prompt=(
                f"Create a professional technical "
                f"diagram explaining the main concepts "
                f"in this blog about {topic}. "
                f"Show the main components, relationships, "
                f"workflow and information flow. "
                f"Use clean labeled boxes and arrows, "
                f"modern technical documentation style, "
                f"white background, clear typography."
            ),

            size="1536x1024",

            quality="medium"
        )

        return {
            "md_with_placeholders":
                merged_md + "\n\n[[IMAGE_1]]\n",

            "image_specs": [
                fallback_spec.model_dump()
            ]
        }

    # ========================================================
    # SUCCESS
    # ========================================================

    # Limit to maximum 3 images.
    images = image_plan.images[:3]

    print(
        f"🖼️ Image planner selected "
        f"{len(images)} image(s)."
    )

    return {
        "md_with_placeholders":
            image_plan.md_with_placeholders,

        "image_specs": [
            img.model_dump()
            for img in images
        ]
    }

    if image_plan is None:
       print("⚠️ Image planner returned None.")
       print("ℹ️ Continuing without images.")

       return {
        "md_with_placeholders": merged_md,
        "image_specs": []
    }

    print(
    f"🖼️ Image planner selected "
    f"{len(image_plan.images)} image(s)."
)

    return {
    "md_with_placeholders": image_plan.md_with_placeholders,
    "image_specs": [
        img.model_dump()
        for img in image_plan.images
    ]
}


# ============================================================
# 3. HUGGING FACE FLUX IMAGE GENERATOR
# ============================================================

from huggingface_hub import InferenceClient
from io import BytesIO
import os


def _huggingface_generate_image_bytes(
    prompt: str
) -> bytes:

    token = os.environ.get("HF_TOKEN")

    if not token:
        raise RuntimeError(
            "HF_TOKEN is not set."
        )

    print(
        "🎨 Generating image with "
        "FLUX.1-dev..."
    )

    client = InferenceClient(
        provider="auto",
        api_key=token
    )

    image = client.text_to_image(
        prompt=prompt,
        model="black-forest-labs/FLUX.1-dev"
    )

    if image is None:
        raise RuntimeError(
            "No image was returned."
        )

    buffer = BytesIO()

    image.save(
        buffer,
        format="PNG"
    )

    return buffer.getvalue()


# ============================================================
# 4. GENERATE + INSERT IMAGES
# ============================================================

def generate_and_place_images(
    state: State
) -> dict:

    plan = state["plan"]

    if plan is None:
        raise ValueError(
            "Plan is missing."
        )

    md = (
        state.get(
            "md_with_placeholders"
        )
        or state["merged_md"]
    )

    image_specs = (
        state.get(
            "image_specs"
        )
        or []
    )

    # --------------------------------------------------------
    # No images
    # --------------------------------------------------------

    if not image_specs:

        print(
            "ℹ️ No images requested."
        )

        filename = (
            f"{plan.blog_title}.md"
        )

        Path(filename).write_text(
            md,
            encoding="utf-8"
        )

        print(
            f"📄 Saved: {filename}"
        )

        return {
            "final": md
        }

    # --------------------------------------------------------
    # Create images directory
    # --------------------------------------------------------

    images_dir = Path(
        "images"
    )

    images_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    # --------------------------------------------------------
    # Generate images
    # --------------------------------------------------------

    for index, spec in enumerate(
        image_specs,
        start=1
    ):

        placeholder = (
            spec["placeholder"]
        )

        filename = (
            spec["filename"]
        )

        # Make sure extension is PNG
        if not filename.lower().endswith(
            ".png"
        ):
            filename += ".png"

        out_path = (
            images_dir / filename
        )

        print()
        print(
            f"🖼️ Image {index}/"
            f"{len(image_specs)}"
        )

        print(
            f"   Filename: {filename}"
        )

        # ----------------------------------------------------
        # Generate only if image doesn't already exist
        # ----------------------------------------------------

        if not out_path.exists():

            try:

                print(
                    "   ⏳ Generating..."
                )

                img_bytes = (
                    _huggingface_generate_image_bytes(
                        spec["prompt"]
                    )
                )

                out_path.write_bytes(
                    img_bytes
                )

                print(
                    f"   ✅ Saved: {out_path}"
                )

            except Exception as e:

                print(
                    f"   ❌ Image generation failed: {e}"
                )

                fallback = (
                    "> **[IMAGE GENERATION FAILED]**\n>\n"
                    f"> **Caption:** "
                    f"{spec.get('caption', '')}\n>\n"
                    f"> **Alt:** "
                    f"{spec.get('alt', '')}\n>\n"
                    f"> **Prompt:** "
                    f"{spec.get('prompt', '')}\n>\n"
                    f"> **Error:** {e}"
                )

                md = md.replace(
                    placeholder,
                    fallback,
                    1
                )

                continue

        # ----------------------------------------------------
        # Markdown image
        # ----------------------------------------------------

        image_markdown = (
            f"![{spec['alt']}]"
            f"(images/{filename})\n\n"
            f"*{spec['caption']}*"
        )

        # ----------------------------------------------------
        # Replace placeholder
        # ----------------------------------------------------

        if placeholder in md:

            md = md.replace(
                placeholder,
                image_markdown,
                1
            )

            print(
                f"   ✅ Inserted "
                f"{placeholder}"
            )

        else:

            print(
                f"   ⚠️ Placeholder "
                f"{placeholder} not found."
            )

    # --------------------------------------------------------
    # Save final Markdown
    # --------------------------------------------------------

    filename = (
        f"{plan.blog_title}.md"
    )

    Path(filename).write_text(
        md,
        encoding="utf-8"
    )

    print()
    print(
        "=========================================="
    )

    print(
        f"📄 Final Markdown: {filename}"
    )

    print(
        f"🖼️ Images folder: {images_dir}"
    )

    print(
        "=========================================="
    )

    return {
        "final": md
    }




from pathlib import Path
def safe_filename(name: str) -> str:

    filename = re.sub(
        r'[<>:"/\\|?*]',
        "_",
        name
    )

    filename = filename.strip()

    return filename[:150]


def reducer_node(state: State) -> dict:

    plan = state.get("plan")

    if plan is None:
        raise ValueError(
            "Cannot reduce without a plan."
        )

    sections = state.get(
        "sections",
        []
    )

    if not sections:
        raise ValueError(
            "No sections were generated."
        )

    # Sort by section ID
    ordered_sections = [
        md
        for section_id, md
        in sorted(
            sections,
            key=lambda x: x[0]
        )
    ]

    body = "\n\n".join(
        ordered_sections
    ).strip()

    final_md = (
        f"# {plan.blog_title}\n\n"
        f"{body}\n"
    )

    filename = (
        safe_filename(
            plan.blog_title
        )
        + ".md"
    )

    Path(filename).write_text(
        final_md,
        encoding="utf-8"
    )

    print(
        f"📄 Saved Markdown file: {filename}"
    )

    return {
        "final": final_md
    }


g = StateGraph(State)


# Nodes

g.add_node(
    "router",
    router_node
)

g.add_node(
    "research",
    research_node
)

g.add_node(
    "orchestrator",
    orchestrator_node
)

g.add_node(
    "worker",
    worker_node
)

g.add_node(
    "merge_content",
    merge_content
)

g.add_node(
    "decide_images",
    decide_images
)

g.add_node(
    "generate_and_place_images",
    generate_and_place_images
)


# ============================================================
# ROUTER
# ============================================================

g.add_edge(
    START,
    "router"
)

g.add_conditional_edges(
    "router",
    route_next,
    {
        "research": "research",
        "orchestrator": "orchestrator"
    }
)


# ============================================================
# RESEARCH
# ============================================================

g.add_edge(
    "research",
    "orchestrator"
)


# ============================================================
# ORCHESTRATOR → WORKERS
# ============================================================

g.add_conditional_edges(
    "orchestrator",
    fanout,
    ["worker"]
)


# ============================================================
# WORKERS → MERGE
# ============================================================

g.add_edge(
    "worker",
    "merge_content"
)


# ============================================================
# MERGE → IMAGE DECISION
# ============================================================

g.add_edge(
    "merge_content",
    "decide_images"
)


# ============================================================
# IMAGE DECISION → IMAGE GENERATION
# ============================================================

g.add_edge(
    "decide_images",
    "generate_and_place_images"
)


# ============================================================
# END
# ============================================================

g.add_edge(
    "generate_and_place_images",
    END
)


# Compile

app = g.compile()

app   