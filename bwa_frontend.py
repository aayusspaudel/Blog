import streamlit as st

from pathlib import Path
from datetime import datetime

import contextlib
import io
import html
import re
import json
import base64
import tempfile

import markdown

# ============================================================
# YOUR LANGGRAPH BACKEND
# ============================================================
#
# Keep backend.py and this file in the same folder.
#
from backend import app


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="AI Technical Blog Studio",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.header("BLOG BLAST")


# ============================================================
# MODERN UI
# ============================================================

st.markdown(
    """
    <style>

    @import url(
        'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap'
    );

    html, body, [class*="css"] {
        font-family: Inter, sans-serif;
    }

    .stApp {
        background:
            radial-gradient(
                circle at 10% 0%,
                rgba(99,102,241,.12),
                transparent 28%
            ),
            radial-gradient(
                circle at 90% 8%,
                rgba(14,165,233,.10),
                transparent 25%
            ),
            #080b12;
    }

    [data-testid="stHeader"] {
        background: rgba(8,11,18,.75);
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(
            180deg,
            #0d111b,
            #090c13
        );

        border-right: 1px solid rgba(255,255,255,.07);
    }

    #MainMenu, footer {
        visibility: hidden;
    }

    .hero {
        padding: 30px;
        border-radius: 24px;

        border: 1px solid rgba(255,255,255,.09);

        background:
            linear-gradient(
                135deg,
                rgba(99,102,241,.18),
                rgba(14,165,233,.07)
            ),
            rgba(15,18,28,.86);

        box-shadow:
            0 25px 80px rgba(0,0,0,.28);

        margin-bottom: 22px;
    }

    .hero h1 span {
    background: linear-gradient(
        90deg,
        #818cf8,
        #38bdf8,
        #c084fc,
        #818cf8
    );
    background-size: 300% auto;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    animation: shimmer 5s linear infinite;
}

@keyframes shimmer {
    to {
        background-position: 300% center;
    }
}

    .hero h1 {
        font-size: clamp(
            2.1rem,
            4vw,
            3.35rem
        );

        line-height: 1.04;

        letter-spacing: -2px;

        margin: 12px 0 10px;

        font-weight: 800;
    }

    .hero p {
        color: #aeb7c8;

        max-width: 820px;

        margin: 0;
    }

    .stage {
        border:
            1px solid rgba(255,255,255,.08);

        border-radius: 20px;

        background:
            rgba(15,19,29,.78);

        padding: 18px 20px;

        margin: 12px 0;
    }

    .stage-title {
        font-size: 1.05rem;

        font-weight: 800;
    }

    .stage-subtitle {
        color: #8994a8;

        font-size: .82rem;

        margin-top: 3px;
    }

    .log {
        font-family:
            ui-monospace,
            SFMono-Regular,
            Consolas,
            monospace;

        font-size: .82rem;

        line-height: 1.65;

        color: #cbd5e1;

        background: #090d15;

        border:
            1px solid rgba(255,255,255,.06);

        padding: 12px 14px;

        border-radius: 12px;

        margin-top: 12px;

        white-space: pre-wrap;
    }

    .source {
        padding: 12px 14px;

        border:
            1px solid rgba(255,255,255,.07);

        border-radius: 13px;

        background:
            rgba(9,13,21,.65);

        margin: 7px 0;
    }

    .source a {
        color: #93c5fd;

        text-decoration: none;

        font-weight: 700;
    }

    .source-meta {
        color: #7f8a9e;

        font-size: .75rem;

        margin-top: 4px;
    }

    .metric {
        border:
            1px solid rgba(255,255,255,.08);

        background:
            rgba(15,19,29,.78);

        border-radius: 16px;

        padding: 16px;
    }

    .metric-label {
        color: #7f8a9e;

        font-size: .7rem;

        text-transform: uppercase;

        letter-spacing: .7px;
    }

    .metric-value {
        font-size: 1.35rem;

        font-weight: 800;

        margin-top: 4px;
    }

    .task-card {
        border:
            1px solid rgba(255,255,255,.08);

        background:
            rgba(9,13,21,.72);

        border-radius: 15px;

        padding: 15px;

        margin: 8px 0;
    }

    .task-id {
        color: #a5b4fc;

        font-size: .73rem;

        font-weight: 800;

        text-transform: uppercase;

        letter-spacing: .7px;
    }

    .task-title {
        font-size: 1.05rem;

        font-weight: 750;

        margin: 4px 0;
    }

    .muted {
        color: #929db0;
    }

    .section-content {
        border-top:
            1px solid rgba(255,255,255,.06);

        margin-top: 14px;

        padding-top: 12px;
    }

    .finished {
        color: #86efac;

        font-weight: 700;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# HELPERS
# ============================================================

def safe_filename(name: str) -> str:
    """
    Create a safe filename.
    """

    name = re.sub(
        r'[<>:"/\\|?*]',
        "_",
        str(name or "technical_blog")
    )

    name = re.sub(
        r"\s+",
        "_",
        name.strip()
    )

    name = name.strip("._ ")

    return name[:150] or "technical_blog"


# ============================================================
# MODEL HELPERS
# ============================================================

def model_dump(value):
    if hasattr(value, "model_dump"):
        return value.model_dump()

    if isinstance(value, dict):
        return value

    return value


def task_dict(task):
    task = model_dump(task)

    return {
        "id": task.get("id", ""),
        "title": task.get("title", ""),
        "goal": task.get("goal", ""),
        "bullets": task.get("bullets", []),
        "target_words": task.get("target_words", 0),
        "section_type": task.get("section_type", ""),
        "requires_code": task.get(
            "requires_code",
            False
        ),
        "requires_citations": task.get(
            "requires_citations",
            False
        ),
    }


def evidence_dict(item):
    item = model_dump(item)

    return {
        "title": item.get("title", ""),
        "url": item.get("url", ""),
        "published_at": item.get(
            "published_at"
        ),
        "snippet": item.get(
            "snippet",
            ""
        ),
        "source": item.get(
            "source"
        ),
    }


# ============================================================
# INITIAL STATE
# ============================================================

def initial_state(topic):

    return {
        "topic": topic,

        "mode": None,

        "needs_research": None,

        "queries": None,

        "evidence": None,

        "plan": None,

        "sections": [],

        "final": None,

        "merged_md": "",

        "md_with_placeholders": "",

        "image_specs": [],
    }


# ============================================================
# LOG RENDERER
# ============================================================

def render_logs(log_text):

    if not log_text.strip():
        return

    escaped = html.escape(
        log_text.strip()
    )

    st.markdown(
        f'<div class="log">{escaped}</div>',
        unsafe_allow_html=True,
    )


# ============================================================
# SOURCE RENDERER
# ============================================================

def render_sources(evidence):

    if not evidence:

        st.info(
            "No research sources were returned."
        )

        return

    st.markdown(
        f"**{len(evidence)} unique sources collected.**"
    )

    for raw in evidence:

        e = evidence_dict(raw)

        title = (
            e["title"]
            or e["url"]
            or "Source"
        )

        url = e["url"]

        if url:

            link = (
                f'<a href="{html.escape(url)}" '
                f'target="_blank">'
                f'{html.escape(title)}'
                f'</a>'
            )

        else:

            link = html.escape(title)

        meta = " · ".join(
            x
            for x in [
                e.get("source"),
                e.get("published_at"),
            ]
            if x
        )

        snippet = html.escape(
            (
                e.get("snippet")
                or ""
            )[:600]
        )

        st.markdown(
            f"""
            <div class="source">

                {link}

                <div class="source-meta">
                    {html.escape(meta)}
                </div>

                <div
                    style="
                        margin-top:7px;
                        color:#aab4c5;
                        font-size:.84rem
                    "
                >
                    {snippet}
                </div>

            </div>
            """,
            unsafe_allow_html=True,
        )


# ============================================================
# PLAN RENDERER
# ============================================================

def render_plan(plan):

    if not plan:

        st.warning(
            "No plan was returned."
        )

        return

    p = model_dump(plan)

    st.markdown(
        f"### {html.escape(str(
            p.get(
                'blog_title',
                'Untitled Blog'
            )
        ))}"
    )

    st.caption(
        f"Audience: "
        f"{p.get('audience', '—')} · "
        f"Tone: "
        f"{p.get('tone', '—')}"
    )

    for raw_task in p.get(
        "tasks",
        []
    ):

        task = task_dict(
            raw_task
        )

        badges = []

        if task["requires_code"]:
            badges.append(
                "💻 Code"
            )

        if task["requires_citations"]:
            badges.append(
                "🔗 Citations"
            )

        badges_html = " ".join(

            f"""
            <span
                style="
                    display:inline-block;
                    padding:4px 8px;
                    margin-right:5px;
                    border-radius:999px;
                    background:rgba(129,140,248,.10);
                    border:1px solid rgba(129,140,248,.20);
                    color:#c7d2fe;
                    font-size:.70rem
                "
            >
                {b}
            </span>
            """

            for b in badges
        )

        bullets = "".join(

            f"<li>{html.escape(str(b))}</li>"

            for b in task["bullets"]
        )

        st.markdown(
            f"""
            <div class="task-card">

                <div class="task-id">

                    Section {task['id']}
                    ·
                    {html.escape(
                        str(task['section_type'])
                    )}

                </div>

                <div class="task-title">

                    {html.escape(
                        str(task['title'])
                    )}

                </div>

                <div class="muted">

                    {html.escape(
                        str(task['goal'])
                    )}

                </div>

                <div style="margin:10px 0">

                    {badges_html}

                </div>

                <ul>

                    {bullets}

                </ul>

                <div class="source-meta">

                    Target:
                    {task['target_words']}
                    words

                </div>

            </div>
            """,
            unsafe_allow_html=True,
        )


# ============================================================
# IMAGE RENDERER
# ============================================================

def render_images(image_specs):

    if not image_specs:

        st.info(
            "No images were requested by "
            "the image planner."
        )

        return

    for i, raw in enumerate(
        image_specs,
        1
    ):

        spec = model_dump(raw)

        st.markdown(
            f"""
            <div class="task-card">

                <div class="task-id">

                    Visual {i}

                </div>

                <div class="task-title">

                    {html.escape(
                        str(
                            spec.get(
                                "caption",
                                "Technical visual"
                            )
                        )
                    )}

                </div>

                <div class="muted">

                    {html.escape(
                        str(
                            spec.get(
                                "filename",
                                "image.png"
                            )
                        )
                    )}

                </div>

            </div>
            """,
            unsafe_allow_html=True,
        )

        filename = str(
            spec.get(
                "filename",
                ""
            )
        )

        if filename:

            image_path = (
                Path("images")
                / filename
            )

            if image_path.exists():

                st.image(
                    str(image_path),
                    use_container_width=True
                )

        with st.expander(
            "Image prompt"
        ):

            st.code(
                str(
                    spec.get(
                        "prompt",
                        ""
                    )
                ),
                language="text",
            )


# ============================================================
# IMAGE → BASE64
# ============================================================

def image_to_base64(image_path):

    """
    Convert local image into a base64 data URI.

    This makes the downloaded HTML/PDF
    completely self-contained.
    """

    try:

        mime_types = {

            ".png":
                "image/png",

            ".jpg":
                "image/jpeg",

            ".jpeg":
                "image/jpeg",

            ".gif":
                "image/gif",

            ".webp":
                "image/webp",

            ".svg":
                "image/svg+xml",
        }

        mime = mime_types.get(
            image_path.suffix.lower(),
            "application/octet-stream"
        )

        image_data = image_path.read_bytes()

        encoded = base64.b64encode(
            image_data
        ).decode("utf-8")

        return (
            f"data:{mime};base64,"
            f"{encoded}"
        )

    except Exception:

        return None


# ============================================================
# FIND LOCAL IMAGE
# ============================================================

def find_local_image(image_src):

    """
    Try several possible locations for
    generated images.
    """

    image_src = image_src.strip()

    image_src = (
        image_src
        .strip('"')
        .strip("'")
    )

    # Remove query strings/fragments
    image_src = image_src.split("?")[0]
    image_src = image_src.split("#")[0]

    possible_paths = [

        # Exact path from Markdown
        Path(image_src),

        # images/filename.png
        Path("images") / Path(
            image_src
        ).name,

        # Generated directory
        Path("generated") / Path(
            image_src
        ).name,

    ]

    for path in possible_paths:

        if path.exists() and path.is_file():

            return path

    return None


# ============================================================
# EMBED MARKDOWN IMAGES
# ============================================================

def prepare_markdown_images(md_text):

    """
    Convert local Markdown images:

        ![](images/example.png)

    into:

        ![](data:image/png;base64,...)

    This prevents broken images when the
    HTML/PDF is downloaded.
    """

    pattern = (
        r'!\[([^\]]*)\]\(([^)]+)\)'
    )

    def replace_image(match):

        alt_text = match.group(1)

        image_src = match.group(2).strip()

        # Already embedded
        if image_src.startswith(
            "data:"
        ):

            return match.group(0)

        # Remote image
        if image_src.startswith(
            (
                "http://",
                "https://",
                "//"
            )
        ):

            return match.group(0)

        image_path = find_local_image(
            image_src
        )

        if not image_path:

            return match.group(0)

        encoded = image_to_base64(
            image_path
        )

        if not encoded:

            return match.group(0)

        return (
            f"![{alt_text}]"
            f"({encoded})"
        )

    return re.sub(
        pattern,
        replace_image,
        md_text
    )


# ============================================================
# MARKDOWN → HTML
# ============================================================

def markdown_to_html(md_text):

    """
    Convert Markdown into HTML.
    """

    return markdown.markdown(

        md_text,

        extensions=[
            "extra",
            "fenced_code",
            "tables",
            "toc",
            "sane_lists",
        ],
    )


# ============================================================
# COMPLETE HTML DOCUMENT
# ============================================================

def create_html_document(
    final_md,
    title
):

    """
    Creates a complete standalone HTML
    document.

    Images are embedded directly into
    the HTML.
    """

    md_with_images = (
        prepare_markdown_images(
            final_md
        )
    )

    body_html = markdown_to_html(
        md_with_images
    )

    safe_title = html.escape(
        title
    )

    html_document = f"""
<!DOCTYPE html>

<html lang="en">

<head>

<meta charset="UTF-8">

<meta
    name="viewport"
    content="width=device-width,
             initial-scale=1.0"
>

<title>
    {safe_title}
</title>

<style>

* {{
    box-sizing: border-box;
}}

body {{

    margin: 0;

    padding: 40px 20px;

    background: #080b12;

    color: #e5e7eb;

    font-family:
        Inter,
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        sans-serif;

    line-height: 1.75;
}}

.article {{

    max-width: 900px;

    margin: auto;

    padding: 50px;

    border-radius: 24px;

    background: #0f131d;

    border:
        1px solid rgba(255,255,255,.08);

    box-shadow:
        0 25px 80px rgba(0,0,0,.3);
}}

h1 {{

    font-size: 2.8rem;

    line-height: 1.15;

    margin-top: 0;

    margin-bottom: 30px;

    color: #f8fafc;
}}

h2 {{

    margin-top: 45px;

    font-size: 2rem;

    color: #f1f5f9;

    border-bottom:
        1px solid rgba(255,255,255,.08);

    padding-bottom: 10px;
}}

h3 {{

    margin-top: 32px;

    font-size: 1.4rem;

    color: #e2e8f0;
}}

p {{

    color: #cbd5e1;

    font-size: 1rem;
}}

strong {{

    color: #f8fafc;
}}

em {{

    color: #c4b5fd;
}}

ul,
ol {{

    color: #cbd5e1;

    padding-left: 28px;
}}

li {{

    margin: 8px 0;
}}

blockquote {{

    margin: 25px 0;

    padding: 15px 20px;

    border-left:
        4px solid #818cf8;

    background:
        rgba(129,140,248,.08);

    color: #cbd5e1;
}}

pre {{

    overflow-x: auto;

    padding: 20px;

    border-radius: 14px;

    background: #090d15;

    border:
        1px solid rgba(255,255,255,.08);
}}

code {{

    font-family:
        Consolas,
        Monaco,
        "Courier New",
        monospace;
}}

:not(pre) > code {{

    padding: 3px 6px;

    border-radius: 5px;

    background:
        rgba(255,255,255,.08);

    color: #c4b5fd;
}}

img {{

    display: block;

    max-width: 100%;

    height: auto;

    margin: 30px auto;

    border-radius: 14px;
}}

table {{

    width: 100%;

    border-collapse: collapse;

    margin: 25px 0;
}}

th,
td {{

    padding: 10px 14px;

    border:
        1px solid rgba(255,255,255,.1);

    text-align: left;
}}

th {{

    background:
        rgba(255,255,255,.05);
}}

a {{

    color: #93c5fd;
}}

@media print {{

    body {{

        background: white;

        color: black;

        padding: 0;
    }}

    .article {{

        max-width: none;

        border: none;

        box-shadow: none;

        background: white;

        padding: 0;
    }}

    h1,
    h2,
    h3 {{

        color: black;
    }}

    p,
    li {{

        color: #222;
    }}

    pre {{

        background: #f5f5f5;

        border:
            1px solid #ddd;
    }}

}}

</style>

</head>

<body>

<main class="article">

{body_html}

</main>

</body>

</html>
"""

    return html_document


# ============================================================
# HTML → PDF
# ============================================================

def create_pdf(
    html_document
):

    """
    Convert complete HTML into a PDF
    using WeasyPrint.
    """

    try:

        from weasyprint import HTML

    except ImportError:

        return None

    try:

        pdf_bytes = (
            HTML(
                string=html_document,
                base_url=str(
                    Path.cwd()
                )
            )
            .write_pdf()
        )

        return pdf_bytes

    except Exception as exc:

        st.warning(
            "PDF generation failed: "
            f"{exc}"
        )

        return None


# ============================================================
# FINAL ARTICLE RENDERER
# ============================================================

def render_final(final_md):

    if not final_md:

        st.warning(
            "The backend completed without "
            "returning final Markdown."
        )

        return

    # ========================================================
    # METRICS
    # ========================================================

    word_count = len(
        re.findall(
            r"\b[\w'-]+\b",
            final_md
        )
    )

    a, b = st.columns(2)

    with a:

        st.metric(
            "Final words",
            f"{word_count:,}"
        )

    with b:

        st.metric(
            "Characters",
            f"{len(final_md):,}"
        )

    # ========================================================
    # FRONTEND PREVIEW
    # ========================================================

    # This remains exactly what your users see.
    st.markdown(final_md)

    # ========================================================
    # EXTRACT TITLE
    # ========================================================

    lines = final_md.splitlines()

    first_line = (
        lines[0]
        if lines
        else "Technical Blog"
    )

    title = re.sub(
        r"^#+\s*",
        "",
        first_line
    ).strip()

    if not title:

        title = "Technical Blog"

    # ========================================================
    # SAFE FILE NAME
    # ========================================================

    filename_base = safe_filename(
        title
    )

    # ========================================================
    # EMBED LOCAL IMAGES
    # ========================================================

    markdown_with_images = (
        prepare_markdown_images(
            final_md
        )
    )

    # ========================================================
    # CREATE STANDALONE HTML
    # ========================================================

    html_document = (
        create_html_document(
            final_md,
            title
        )
    )

    # ========================================================
    # CREATE PDF
    # ========================================================

    pdf_bytes = create_pdf(
        html_document
    )

    # ========================================================
    # DOWNLOAD SECTION
    # ========================================================

    st.markdown("---")

    st.markdown(
        "### 📥 Download your article"
    )

    st.caption(
        "The HTML and PDF versions include "
        "your generated images."
    )

    col1, col2, col3 = st.columns(3)

    # ========================================================
    # MARKDOWN
    # ========================================================

    with col1:

        st.download_button(

            "📝 Markdown",

            data=final_md.encode(
                "utf-8"
            ),

            file_name=(
                f"{filename_base}.md"
            ),

            mime="text/markdown",

            use_container_width=True,

        )

    # ========================================================
    # HTML
    # ========================================================

    with col2:

        st.download_button(

            "🌐 HTML",

            data=html_document.encode(
                "utf-8"
            ),

            file_name=(
                f"{filename_base}.html"
            ),

            mime="text/html",

            use_container_width=True,

        )

    # ========================================================
    # PDF
    # ========================================================

    with col3:

        if pdf_bytes:

            st.download_button(

                "📕 PDF",

                data=pdf_bytes,

                file_name=(
                    f"{filename_base}.pdf"
                ),

                mime="application/pdf",

                use_container_width=True,

            )

        else:

            st.button(

                "📕 PDF unavailable",

                disabled=True,

                use_container_width=True,

            )


# ============================================================
# SESSION STATE
# ============================================================

if "topic" not in st.session_state:

    st.session_state.topic = ""


if "result" not in st.session_state:

    st.session_state.result = None


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown(
        "## ✦ Blog Studio"
    )

    st.caption(
        "Technical blog generator"
    )

    st.markdown("---")

    st.markdown(
        "### Pipeline"
    )

    pipeline = [

        (
            "01",
            "🔀 Router",
            "Decide research mode"
        ),

        (
            "02",
            "🔎 Research",
            "Collect web evidence"
        ),

        (
            "03",
            "🧠 Planner",
            "Create 5–7 sections"
        ),

        (
            "04",
            "✍️ Workers",
            "Write sections in parallel"
        ),

        (
            "05",
            "🧩 Merge",
            "Restore correct section order"
        ),

        (
            "06",
            "🖼️ Images",
            "Plan and generate visuals"
        ),

        (
            "07",
            "📄 Final",
            "Return complete Markdown"
        ),

    ]

    for number, name, desc in pipeline:

        st.markdown(
            f"""
            <div style="margin:11px 0">

                <div style="font-weight:750">

                    <span
                        style="color:#818cf8"
                    >
                        {number}
                    </span>

                    &nbsp;

                    {name}

                </div>

                <div
                    style="
                        color:#7f8a9e;
                        font-size:.73rem;
                        margin-left:31px
                    "
                >
                    {desc}
                </div>

            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("---")

    st.markdown(
        "### Quick topics"
    )

    examples = [

        "The State of Multimodal LLMs in 2026",

        "Production RAG architecture",

        "LangGraph agent workflows",

        "Vector databases explained",

    ]

    for example in examples:

        if st.button(

            example,

            key=f"example_{example}",

            use_container_width=True,

        ):

            st.session_state.topic = (
                example
            )

            st.rerun()


# ============================================================
# HERO
# ============================================================

st.markdown(
    """
    <div class="hero">

        <span>
    ✦ AI TECHNICAL BLOG ENGINE
</span>

<h1>
    From <span>thought</span> → research → creation.
</h1>

<p>
    Give AI a topic. Watch intelligence unfold.
    Research, reasoning, writing, merging, and visual generation —
    orchestrated live through a powerful LangGraph workflow.
</p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# TOPIC INPUT
# ============================================================

topic = st.text_area(

    "Blog topic",

    value=st.session_state.topic,

    placeholder=(
        "Example: "
        "The State of Multimodal LLMs in 2026"
    ),

    height=100,

)

st.session_state.topic = topic


generate = st.button(

    "✦  Generate Blog",

    type="primary",

    use_container_width=True,

    disabled=not topic.strip(),

)


# ============================================================
# LIVE PIPELINE
# ============================================================

if generate:

    # --------------------------------------------------------
    # Clear previous result
    # --------------------------------------------------------

    st.session_state.result = None

    topic = topic.strip()

    state = initial_state(
        topic
    )

    st.markdown("---")

    st.markdown(
        "## ⚡ Live generation"
    )

    overall = st.progress(

        0,

        text=(
            "Starting LangGraph pipeline…"
        ),

    )

    completed_nodes = 0

    total_expected_nodes = 7

    accumulated = dict(
        state
    )

    # --------------------------------------------------------
    # Capture backend print() statements
    # --------------------------------------------------------

    stdout_buffer = io.StringIO()

    try:

        with contextlib.redirect_stdout(
            stdout_buffer
        ):

            stream = app.stream(

                state,

                stream_mode="updates",

            )

            last_stdout_len = 0

            for update in stream:

                # =================================================
                # CAPTURE NEW BACKEND OUTPUT
                # =================================================

                current_output = (
                    stdout_buffer.getvalue()
                )

                new_output = (
                    current_output[
                        last_stdout_len:
                    ]
                )

                last_stdout_len = len(
                    current_output
                )

                # =================================================
                # LANGGRAPH UPDATE
                # =================================================

                if not isinstance(
                    update,
                    dict
                ):

                    continue

                for (
                    node_name,
                    node_output
                ) in update.items():

                    if not isinstance(
                        node_output,
                        dict
                    ):

                        continue

                    # ---------------------------------------------
                    # Merge returned state
                    # ---------------------------------------------

                    for (
                        key,
                        value
                    ) in node_output.items():

                        if key == "sections":

                            old = (
                                accumulated.get(
                                    "sections"
                                )
                                or []
                            )

                            accumulated[
                                "sections"
                            ] = (
                                old
                                + list(
                                    value
                                    or []
                                )
                            )

                        else:

                            accumulated[
                                key
                            ] = value

                    completed_nodes += 1

                    progress_value = min(

                        int(
                            completed_nodes
                            /
                            total_expected_nodes
                            * 100
                        ),

                        99,

                    )

                    overall.progress(

                        progress_value,

                        text=(
                            f"Completed: "
                            f"{node_name}"
                        ),

                    )

                    # =================================================
                    # ROUTER
                    # =================================================

                    if node_name == "router":

                        with st.container():

                            st.markdown(
                                """
                                <div class="stage">

                                    <div class="stage-title">

                                        🔀 Router completed

                                    </div>

                                    <div class="stage-subtitle">

                                        The backend decided whether
                                        this topic needs research.

                                    </div>

                                </div>
                                """,
                                unsafe_allow_html=True,
                            )

                            render_logs(
                                new_output
                            )

                            mode = (
                                accumulated.get(
                                    "mode"
                                )
                            )

                            needs = (
                                accumulated.get(
                                    "needs_research"
                                )
                            )

                            st.success(

                                f"Research needed: "
                                f"{'Yes' if needs else 'No'}"
                                f" · "
                                f"Mode: "
                                f"{mode or 'unknown'}"

                            )

                    # =================================================
                    # RESEARCH
                    # =================================================

                    elif node_name == "research":

                        with st.container():

                            st.markdown(
                                """
                                <div class="stage">

                                    <div class="stage-title">

                                        🔎 Research completed

                                    </div>

                                    <div class="stage-subtitle">

                                        All Tavily searches
                                        have finished.

                                    </div>

                                </div>
                                """,
                                unsafe_allow_html=True,
                            )

                            render_logs(
                                new_output
                            )

                            evidence = (
                                accumulated.get(
                                    "evidence"
                                )
                                or []
                            )

                            render_sources(
                                evidence
                            )

                    # =================================================
                    # PLANNER
                    # =================================================

                    elif node_name == "orchestrator":

                        with st.container():

                            st.markdown(
                                """
                                <div class="stage">

                                    <div class="stage-title">

                                        🧠 Planning completed

                                    </div>

                                    <div class="stage-subtitle">

                                        The article structure
                                        is ready.

                                    </div>

                                </div>
                                """,
                                unsafe_allow_html=True,
                            )

                            render_logs(
                                new_output
                            )

                            render_plan(
                                accumulated.get(
                                    "plan"
                                )
                            )

                    # =================================================
                    # WORKER
                    # =================================================

                    elif node_name == "worker":

                        sections = (
                            node_output.get(
                                "sections"
                            )
                            or []
                        )

                        with st.container():

                            st.markdown(
                                """
                                <div class="stage">

                                    <div class="stage-title">

                                        ✍️ Section completed

                                    </div>

                                    <div class="stage-subtitle">

                                        A parallel worker has
                                        finished its assigned
                                        section.

                                    </div>

                                </div>
                                """,
                                unsafe_allow_html=True,
                            )

                            render_logs(
                                new_output
                            )

                            for (
                                section_id,
                                section_md
                            ) in sections:

                                st.markdown(

                                    f"""
                                    ###

                                    <span
                                        class="finished"
                                    >
                                        ✓ Section
                                        {section_id}
                                        finished
                                    </span>
                                    """,

                                    unsafe_allow_html=True,

                                )

                                st.markdown(
                                    f"""
                                    <div class="section-content">

                                        {section_md}

                                    </div>
                                    """,
                                    unsafe_allow_html=True,
                                )

                    # =================================================
                    # MERGE
                    # =================================================

                    elif node_name == "merge_content":

                        with st.container():

                            st.markdown(
                                """
                                <div class="stage">

                                    <div class="stage-title">

                                        🧩 Sections merged

                                    </div>

                                    <div class="stage-subtitle">

                                        Parallel sections have
                                        been restored to the
                                        correct 1 → N order.

                                    </div>

                                </div>
                                """,
                                unsafe_allow_html=True,
                            )

                            render_logs(
                                new_output
                            )

                            merged = (
                                accumulated.get(
                                    "merged_md"
                                )
                                or ""
                            )

                            if merged:

                                with st.expander(
                                    "Preview merged article",
                                    expanded=False,
                                ):

                                    st.markdown(
                                        merged
                                    )

                    # =================================================
                    # IMAGE DECISION
                    # =================================================

                    elif node_name == "decide_images":

                        with st.container():

                            st.markdown(
                                """
                                <div class="stage">

                                    <div class="stage-title">

                                        🖼️ Image planning
                                        completed

                                    </div>

                                    <div class="stage-subtitle">

                                        The backend decided
                                        whether technical
                                        visuals add value.

                                    </div>

                                </div>
                                """,
                                unsafe_allow_html=True,
                            )

                            render_logs(
                                new_output
                            )

                            specs = (
                                accumulated.get(
                                    "image_specs"
                                )
                                or []
                            )

                            if specs:

                                st.success(

                                    f"{len(specs)} "
                                    f"image(s) requested."

                                )

                                render_images(
                                    specs
                                )

                            else:

                                st.info(
                                    "ℹ️ No images requested."
                                )

                    # =================================================
                    # FINAL OUTPUT
                    # =================================================

                    elif (
                        node_name
                        == "generate_and_place_images"
                    ):

                        with st.container():

                            st.markdown(
                                """
                                <div class="stage">

                                    <div class="stage-title">

                                        📄 Final output
                                        completed

                                    </div>

                                    <div class="stage-subtitle">

                                        The final Markdown
                                        has been returned
                                        by the backend.

                                    </div>

                                </div>
                                """,
                                unsafe_allow_html=True,
                            )

                            render_logs(
                                new_output
                            )

                            final_md = (

                                node_output.get(
                                    "final"
                                )

                                or accumulated.get(
                                    "final"
                                )

                                or ""

                            )

                            accumulated[
                                "final"
                            ] = final_md

                            if final_md:

                                render_final(
                                    final_md
                                )

                            else:

                                st.error(
                                    "The graph completed, "
                                    "but final Markdown "
                                    "was empty."
                                )

        # ====================================================
        # GRAPH COMPLETE
        # ====================================================

        overall.progress(

            100,

            text=(
                "✅ Complete — all LangGraph "
                "stages finished."
            ),

        )

        # ====================================================
        # SAVE FRONTEND COPY
        # ====================================================

        final_md = (
            accumulated.get(
                "final"
            )
            or ""
        )

        if final_md:

            output_dir = Path(
                "generated"
            )

            output_dir.mkdir(
                exist_ok=True
            )

            lines = (
                final_md.splitlines()
            )

            first_line = (

                lines[0]
                if lines
                else topic

            )

            title = re.sub(

                r"^#+\s*",

                "",

                first_line

            ).strip()

            if not title:

                title = topic

            output_path = (
                output_dir
                / f"{safe_filename(title)}.md"
            )

            output_path.write_text(

                final_md,

                encoding="utf-8"

            )

            st.success(

                f"📄 Frontend copy saved: "
                f"{output_path}"

            )

        st.session_state.result = (
            accumulated
        )

    except Exception as exc:

        st.error(
            "❌ The LangGraph pipeline failed."
        )

        st.exception(
            exc
        )

        logs = (
            stdout_buffer.getvalue()
        )

        if logs:

            with st.expander(
                "Backend logs",
                expanded=True
            ):

                st.code(
                    logs,
                    language="text"
                )


# ============================================================
# RESULTS FROM PREVIOUS RUN
# ============================================================

elif st.session_state.result:

    result = (
        st.session_state.result
    )

    st.markdown("---")

    st.markdown(
        "## 📖 Last generated result"
    )

    final_md = (
        result.get(
            "final"
        )
        or ""
    )

    if final_md:

        render_final(
            final_md
        )

    else:

        st.warning(
            "No final Markdown was stored."
        )

    with st.expander(
        "Show research sources"
    ):

        render_sources(
            result.get(
                "evidence"
            )
            or []
        )

    with st.expander(
        "Show generated plan"
    ):

        render_plan(
            result.get(
                "plan"
            )
        )

    with st.expander(
        "Show image plan"
    ):

        render_images(
            result.get(
                "image_specs"
            )
            or []
        )
