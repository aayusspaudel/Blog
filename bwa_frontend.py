import streamlit as st
from pathlib import Path
from datetime import datetime
import contextlib
import io
import html
import re
import json

# ============================================================
# YOUR LANGGRAPH BACKEND
# ============================================================
# Keep backend.py and this file in the same folder.
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
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: Inter, sans-serif;
    }

    .stApp {
        background:
            radial-gradient(circle at 10% 0%, rgba(99,102,241,.12), transparent 28%),
            radial-gradient(circle at 90% 8%, rgba(14,165,233,.10), transparent 25%),
            #080b12;
    }

    [data-testid="stHeader"] {
        background: rgba(8,11,18,.75);
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0d111b, #090c13);
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
            linear-gradient(135deg, rgba(99,102,241,.18), rgba(14,165,233,.07)),
            rgba(15,18,28,.86);
        box-shadow: 0 25px 80px rgba(0,0,0,.28);
        margin-bottom: 22px;
    }

    .hero-badge {
        display: inline-block;
        padding: 6px 11px;
        border-radius: 999px;
        color: #c7d2fe;
        background: rgba(129,140,248,.12);
        border: 1px solid rgba(129,140,248,.25);
        font-size: .74rem;
        font-weight: 800;
        letter-spacing: .8px;
    }

    .hero h1 {
        font-size: clamp(2.1rem, 4vw, 3.35rem);
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
        border: 1px solid rgba(255,255,255,.08);
        border-radius: 20px;
        background: rgba(15,19,29,.78);
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
        font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
        font-size: .82rem;
        line-height: 1.65;
        color: #cbd5e1;
        background: #090d15;
        border: 1px solid rgba(255,255,255,.06);
        padding: 12px 14px;
        border-radius: 12px;
        margin-top: 12px;
        white-space: pre-wrap;
    }

    .source {
        padding: 12px 14px;
        border-radius: 13px;
        border: 1px solid rgba(255,255,255,.07);
        background: rgba(9,13,21,.65);
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
        border: 1px solid rgba(255,255,255,.08);
        background: rgba(15,19,29,.78);
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
        border: 1px solid rgba(255,255,255,.08);
        background: rgba(9,13,21,.72);
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
        border-top: 1px solid rgba(255,255,255,.06);
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
    name = re.sub(r'[<>:"/\\|?*]', "_", str(name or "technical_blog"))
    name = re.sub(r"\s+", "_", name.strip())
    name = name.strip("._ ")
    return (name[:150] or "technical_blog") + ".md"


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
        "requires_code": task.get("requires_code", False),
        "requires_citations": task.get("requires_citations", False),
    }


def evidence_dict(item):
    item = model_dump(item)
    return {
        "title": item.get("title", ""),
        "url": item.get("url", ""),
        "published_at": item.get("published_at"),
        "snippet": item.get("snippet", ""),
        "source": item.get("source"),
    }


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


def render_logs(log_text):
    if not log_text.strip():
        return

    # Escape HTML so backend errors/messages cannot break the page.
    escaped = html.escape(log_text.strip())
    st.markdown(
        f'<div class="log">{escaped}</div>',
        unsafe_allow_html=True,
    )


def render_sources(evidence):
    if not evidence:
        st.info("No research sources were returned.")
        return

    st.markdown(f"**{len(evidence)} unique sources collected.**")

    for raw in evidence:
        e = evidence_dict(raw)

        title = e["title"] or e["url"] or "Source"
        url = e["url"]

        if url:
            link = (
                f'<a href="{html.escape(url)}" target="_blank">'
                f'{html.escape(title)}</a>'
            )
        else:
            link = html.escape(title)

        meta = " · ".join(
            x for x in [
                e.get("source"),
                e.get("published_at"),
            ]
            if x
        )

        snippet = html.escape((e.get("snippet") or "")[:600])

        st.markdown(
            f"""
            <div class="source">
                {link}
                <div class="source-meta">{html.escape(meta)}</div>
                <div style="margin-top:7px;color:#aab4c5;font-size:.84rem">
                    {snippet}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_plan(plan):
    if not plan:
        st.warning("No plan was returned.")
        return

    p = model_dump(plan)

    st.markdown(f"### {html.escape(str(p.get('blog_title', 'Untitled Blog')))}")
    st.caption(
        f"Audience: {p.get('audience', '—')} · "
        f"Tone: {p.get('tone', '—')}"
    )

    for raw_task in p.get("tasks", []):
        task = task_dict(raw_task)

        badges = []
        if task["requires_code"]:
            badges.append("💻 Code")
        if task["requires_citations"]:
            badges.append("🔗 Citations")

        badges_html = " ".join(
            f'<span style="display:inline-block;padding:4px 8px;'
            f'margin-right:5px;border-radius:999px;'
            f'background:rgba(129,140,248,.10);'
            f'border:1px solid rgba(129,140,248,.20);'
            f'color:#c7d2fe;font-size:.70rem">{b}</span>'
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
                    Section {task['id']} · {html.escape(str(task['section_type']))}
                </div>
                <div class="task-title">
                    {html.escape(str(task['title']))}
                </div>
                <div class="muted">
                    {html.escape(str(task['goal']))}
                </div>
                <div style="margin:10px 0">{badges_html}</div>
                <ul>{bullets}</ul>
                <div class="source-meta">
                    Target: {task['target_words']} words
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_images(image_specs):
    if not image_specs:
        st.info("No images were requested by the image planner.")
        return

    for i, raw in enumerate(image_specs, 1):
        spec = model_dump(raw)

        st.markdown(
            f"""
            <div class="task-card">
                <div class="task-id">Visual {i}</div>
                <div class="task-title">
                    {html.escape(str(spec.get('caption', 'Technical visual')))}
                </div>
                <div class="muted">
                    {html.escape(str(spec.get('filename', 'image.png')))}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        filename = str(spec.get("filename", ""))
        if filename:
            image_path = Path("images") / filename
            if image_path.exists():
                st.image(str(image_path), use_container_width=True)

        with st.expander("Image prompt"):
            st.code(str(spec.get("prompt", "")), language="text")


def render_final(final_md):
    if not final_md:
        st.warning("The backend completed without returning final Markdown.")
        return

    word_count = len(re.findall(r"\b[\w'-]+\b", final_md))

    a, b = st.columns(2)
    with a:
        st.metric("Final words", f"{word_count:,}")
    with b:
        st.metric("Characters", f"{len(final_md):,}")

    # This is the important part: display the FINAL returned state,
    # not the Markdown file sitting in VS Code.
    st.markdown(final_md)

    filename = safe_filename(
        final_md.split("\n", 1)[0].lstrip("# ").strip()
    )

    st.download_button(
        "⬇️ Download Final Markdown",
        data=final_md.encode("utf-8"),
        file_name=filename,
        mime="text/markdown",
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
    st.markdown("## ✦ Blog Studio")
    st.caption("Technical blog generator")

    st.markdown("---")
    st.markdown("### Pipeline")

    pipeline = [
        ("01", "🔀 Router", "Decide research mode"),
        ("02", "🔎 Research", "Collect web evidence"),
        ("03", "🧠 Planner", "Create 5–7 sections"),
        ("04", "✍️ Workers", "Write sections in parallel"),
        ("05", "🧩 Merge", "Restore correct section order"),
        ("06", "🖼️ Images", "Plan and generate visuals"),
        ("07", "📄 Final", "Return complete Markdown"),
    ]

    for number, name, desc in pipeline:
        st.markdown(
            f"""
            <div style="margin:11px 0">
                <div style="font-weight:750">
                    <span style="color:#818cf8">{number}</span>
                    &nbsp;{name}
                </div>
                <div style="color:#7f8a9e;font-size:.73rem;margin-left:31px">
                    {desc}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.markdown("### Quick topics")

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
            st.session_state.topic = example
            st.rerun()


# ============================================================
# HERO
# ============================================================
st.markdown(
    """
    <div class="hero">
        <span class="hero-badge">AI TECHNICAL BLOG GENERATOR</span>
        <h1>From topic → research → article.</h1>
        <p>
            Watch every LangGraph stage appear as it completes.
            Research, planning, parallel section writing, merging,
            image decisions, and the final Markdown are shown separately.
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
    placeholder="Example: The State of Multimodal LLMs in 2026",
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
    # Clear previous result.
    st.session_state.result = None

    topic = topic.strip()
    state = initial_state(topic)

    st.markdown("---")
    st.markdown("## ⚡ Live generation")

    overall = st.progress(0, text="Starting LangGraph pipeline…")

    # One persistent container per completed event.
    # Because app.stream() yields after each node, these appear
    # progressively instead of waiting for the entire graph.
    completed_nodes = 0
    total_expected_nodes = 7

    accumulated = dict(state)

    # --------------------------------------------------------
    # IMPORTANT:
    # redirect_stdout captures the backend's existing print()
    # statements. We read the new output after EVERY graph
    # update. This means your existing messages such as:
    #
    # 🔎 Searching: ...
    # ✅ Collected ...
    # 🧠 Generating plan ...
    # ✅ Finished section ...
    #
    # are shown by the frontend without changing backend.py.
    # --------------------------------------------------------
    stdout_buffer = io.StringIO()

    try:
        with contextlib.redirect_stdout(stdout_buffer):
            stream = app.stream(
                state,
                stream_mode="updates",
            )

            for update in stream:
                # --------------------------------------------
                # Capture only NEW backend console output.
                # --------------------------------------------
                current_output = stdout_buffer.getvalue()

                if "last_stdout_len" not in locals():
                    last_stdout_len = 0

                new_output = current_output[last_stdout_len:]
                last_stdout_len = len(current_output)

                # --------------------------------------------
                # LangGraph update may contain one node or a
                # worker update.
                # --------------------------------------------
                if not isinstance(update, dict):
                    continue

                for node_name, node_output in update.items():
                    if not isinstance(node_output, dict):
                        continue

                    # Merge returned state locally.
                    for key, value in node_output.items():
                        if key == "sections":
                            old = accumulated.get("sections") or []
                            accumulated["sections"] = old + list(value or [])
                        else:
                            accumulated[key] = value

                    completed_nodes += 1
                    progress_value = min(
                        int(completed_nodes / total_expected_nodes * 100),
                        99,
                    )
                    overall.progress(
                        progress_value,
                        text=f"Completed: {node_name}",
                    )

                    # ----------------------------------------
                    # ROUTER
                    # ----------------------------------------
                    if node_name == "router":
                        with st.container():
                            st.markdown(
                                """
                                <div class="stage">
                                    <div class="stage-title">
                                        🔀 Router completed
                                    </div>
                                    <div class="stage-subtitle">
                                        The backend decided whether this topic needs research.
                                    </div>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )

                            render_logs(new_output)

                            mode = accumulated.get("mode")
                            needs = accumulated.get("needs_research")

                            st.success(
                                f"Research needed: {'Yes' if needs else 'No'}  ·  "
                                f"Mode: {mode or 'unknown'}"
                            )

                    # ----------------------------------------
                    # RESEARCH
                    # ----------------------------------------
                    elif node_name == "research":
                        with st.container():
                            st.markdown(
                                """
                                <div class="stage">
                                    <div class="stage-title">
                                        🔎 Research completed
                                    </div>
                                    <div class="stage-subtitle">
                                        All Tavily searches have finished.
                                    </div>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )

                            render_logs(new_output)

                            evidence = accumulated.get("evidence") or []
                            render_sources(evidence)

                    # ----------------------------------------
                    # PLANNER
                    # ----------------------------------------
                    elif node_name == "orchestrator":
                        with st.container():
                            st.markdown(
                                """
                                <div class="stage">
                                    <div class="stage-title">
                                        🧠 Planning completed
                                    </div>
                                    <div class="stage-subtitle">
                                        The article structure is ready.
                                    </div>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )

                            render_logs(new_output)
                            render_plan(accumulated.get("plan"))

                    # ----------------------------------------
                    # WORKER
                    # ----------------------------------------
                    elif node_name == "worker":
                        # Worker output is:
                        # {"sections": [(task.id, section_md)]}
                        sections = node_output.get("sections") or []

                        with st.container():
                            st.markdown(
                                """
                                <div class="stage">
                                    <div class="stage-title">
                                        ✍️ Section completed
                                    </div>
                                    <div class="stage-subtitle">
                                        A parallel worker has finished its assigned section.
                                    </div>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )

                            render_logs(new_output)

                            for section_id, section_md in sections:
                                st.markdown(
                                    f"### <span class='finished'>✓ Section {section_id} finished</span>",
                                    unsafe_allow_html=True,
                                )
                                st.markdown(
                                    f'<div class="section-content">{section_md}</div>',
                                    unsafe_allow_html=True,
                                )

                    # ----------------------------------------
                    # MERGE
                    # ----------------------------------------
                    elif node_name == "merge_content":
                        with st.container():
                            st.markdown(
                                """
                                <div class="stage">
                                    <div class="stage-title">
                                        🧩 Sections merged
                                    </div>
                                    <div class="stage-subtitle">
                                        Parallel sections have been restored to the correct 1 → N order.
                                    </div>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )

                            render_logs(new_output)

                            merged = accumulated.get("merged_md") or ""
                            if merged:
                                with st.expander(
                                    "Preview merged article",
                                    expanded=False,
                                ):
                                    st.markdown(merged)

                    # ----------------------------------------
                    # IMAGE DECISION
                    # ----------------------------------------
                    elif node_name == "decide_images":
                        with st.container():
                            st.markdown(
                                """
                                <div class="stage">
                                    <div class="stage-title">
                                        🖼️ Image planning completed
                                    </div>
                                    <div class="stage-subtitle">
                                        The backend decided whether technical visuals add value.
                                    </div>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )

                            render_logs(new_output)

                            specs = accumulated.get("image_specs") or []

                            if specs:
                                st.success(
                                    f"{len(specs)} image(s) requested."
                                )
                                render_images(specs)
                            else:
                                st.info("ℹ️ No images requested.")

                    # ----------------------------------------
                    # IMAGE GENERATION / FINAL
                    # ----------------------------------------
                    elif node_name == "generate_and_place_images":
                        with st.container():
                            st.markdown(
                                """
                                <div class="stage">
                                    <div class="stage-title">
                                        📄 Final output completed
                                    </div>
                                    <div class="stage-subtitle">
                                        The final Markdown has been returned by the backend.
                                    </div>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )

                            render_logs(new_output)

                            final_md = (
                                node_output.get("final")
                                or accumulated.get("final")
                                or ""
                            )

                            accumulated["final"] = final_md

                            if final_md:
                                render_final(final_md)
                            else:
                                st.error(
                                    "The graph completed, but final Markdown was empty."
                                )

        # The graph has finished. Capture anything printed after
        # the last yielded update.
        remaining_output = stdout_buffer.getvalue()

        if remaining_output:
            # Do not duplicate logs that were already rendered.
            pass

        overall.progress(
            100,
            text="✅ Complete — all LangGraph stages finished.",
        )

        # ----------------------------------------------------
        # SAVE A FRONTEND-CONTROLLED COPY.
        #
        # This is intentionally separate from the backend's
        # Windows filename handling. It guarantees a clean,
        # valid filename for the frontend download/archive.
        # ----------------------------------------------------
        final_md = accumulated.get("final") or ""

        if final_md:
            output_dir = Path("generated")
            output_dir.mkdir(exist_ok=True)

            # Extract title safely.
            first_line = final_md.splitlines()[0] if final_md.splitlines() else topic
            title = re.sub(r"^#+\s*", "", first_line).strip() or topic

            output_path = output_dir / safe_filename(title)
            output_path.write_text(final_md, encoding="utf-8")

            st.success(
                f"📄 Frontend copy saved: {output_path}"
            )

        st.session_state.result = accumulated

    except Exception as exc:
        st.error("❌ The LangGraph pipeline failed.")

        # Show the real Python error instead of hiding it.
        st.exception(exc)

        # Show any backend logs captured before failure.
        logs = stdout_buffer.getvalue()
        if logs:
            with st.expander("Backend logs", expanded=True):
                st.code(logs, language="text")


# ============================================================
# RESULTS FROM PREVIOUS RUN
# ============================================================
elif st.session_state.result:
    result = st.session_state.result

    st.markdown("---")
    st.markdown("## 📖 Last generated result")

    final_md = result.get("final") or ""

    if final_md:
        render_final(final_md)
    else:
        st.warning("No final Markdown was stored.")

    with st.expander("Show research sources"):
        render_sources(result.get("evidence") or [])

    with st.expander("Show generated plan"):
        render_plan(result.get("plan"))

    with st.expander("Show image plan"):
        render_images(result.get("image_specs") or [])
