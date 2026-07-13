"""Autonomous agent loop: snapshot -> policy -> Browser action -> repeat.

Two policies, chosen automatically:
- `ollama_policy`: asks a local Ollama model (stdlib `urllib` HTTP call to
  http://localhost:11434) to pick the next action from the pruned snapshot
  text alone.
- `rule_based_policy`: a small deterministic state machine tailored to the
  one task this build demos (search Wikipedia, follow the right result,
  extract a fact). Used whenever Ollama isn't reachable, so the wow shot
  never depends on an optional runtime being installed.

Every step is logged with both the snapshot-token and raw-HTML-token counts
of the page the agent was looking at, so render_report.py can draw the
"agent saw N tokens, the raw page was M" comparison per PRD's wow shot.
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

if __name__ == "__main__" and __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from barebrowse.browser import Browser, BrowserError
from barebrowse.tokens import estimate_tokens

OLLAMA_URL = "http://localhost:11434"


class AgentError(Exception):
    pass


def is_ollama_available(base_url=OLLAMA_URL, timeout=1.5):
    try:
        with urllib.request.urlopen(f"{base_url}/api/tags", timeout=timeout):
            return True
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def call_ollama(prompt, model, base_url=OLLAMA_URL, timeout=30):
    payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
    req = urllib.request.Request(
        f"{base_url}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode())
    return body.get("response", "")


_ACTION_RE = re.compile(r"ACTION:\s*(type|click|done)\b(.*)", re.I)


def _parse_llm_action(text):
    """Pull the first `ACTION: ...` line out of free-form model output."""
    for line in text.splitlines():
        m = _ACTION_RE.search(line)
        if not m:
            continue
        verb = m.group(1).lower()
        tail = m.group(2).strip()
        if verb == "type" and tail:
            ref, _, rest = tail.partition(" ")
            return {"type": "type", "ref": ref, "text": rest.strip()}
        if verb == "click" and tail:
            return {"type": "click", "ref": tail}
        if verb == "done":
            return {"type": "done", "success": True, "extracted": tail or None}
    return None


def _build_prompt(snapshot, task, history):
    history_lines = [
        f"- {h['type']} {h.get('ref', '')} {h.get('text', '')}".strip()
        for h in history
    ] or ["(none yet)"]
    return f"""You are a web-browsing agent. You only see a pruned accessibility-tree
snapshot of the page, never raw HTML. Elements you can act on are marked
with a ref like [e12].

TASK: {task['description']}
Search query to use if you need to search: {task['query']}
You are trying to reach a page about: {task['target_substring']}

Steps taken so far:
{chr(10).join(history_lines)}

Current page snapshot:
{snapshot.render()}

Respond with EXACTLY ONE line in one of these forms:
ACTION: type <ref> <text to type>
ACTION: click <ref>
ACTION: done <fact you extracted, or leave blank if you cannot complete the task>
"""


def ollama_policy(browser, task, history, model="llama3.2"):
    prompt = _build_prompt(browser.snapshot, task, history)
    text = call_ollama(prompt, model)
    action = _parse_llm_action(text)
    if action is None:
        raise AgentError(f"could not parse an ACTION out of model output: {text!r}")
    return action


def rule_based_policy(browser, task, history):
    """Deterministic fallback: type query -> submit -> click target link -> extract."""
    snap = browser.snapshot
    title = snap.title or ""

    if task["target_substring"].lower() in title.lower():
        text = snap.render()
        m = re.search(task["extract_regex"], text, re.I)
        return {
            "type": "done",
            "success": bool(m),
            "extracted": m.group(1) if m else None,
        }

    if not history:
        for ref, entry in snap.ref_index.items():
            if entry["role"] == "textbox" and entry["form"] is not None:
                return {"type": "type", "ref": ref, "text": task["query"]}
        return {"type": "done", "success": False, "extracted": None,
                "reason": "no search box found on start page"}

    if history[-1]["type"] == "type":
        ref = history[-1]["ref"]
        entry = snap.find_ref(ref)
        form_ctx = entry["form"] if entry else None
        if form_ctx and form_ctx.get("submit_refs"):
            return {"type": "click", "ref": form_ctx["submit_refs"][0]}
        return {"type": "done", "success": False, "extracted": None,
                "reason": "typed query but found no submit button for its form"}

    for ref, entry in snap.ref_index.items():
        if entry["role"] == "link" and task["target_substring"].lower() in (entry["name"] or "").lower():
            return {"type": "click", "ref": ref}

    return {"type": "done", "success": False, "extracted": None,
            "reason": f"no link containing {task['target_substring']!r} found in results"}


def choose_policy(policy_name, model):
    if policy_name == "rule":
        return "rule", rule_based_policy
    if policy_name == "ollama":
        return "ollama", lambda b, t, h: ollama_policy(b, t, h, model=model)
    # auto
    if is_ollama_available():
        return "ollama", lambda b, t, h: ollama_policy(b, t, h, model=model)
    return "rule", rule_based_policy


def run_once(task, policy_fn, policy_name, timeout=10):
    browser = Browser(timeout=timeout)
    history = []
    steps_log = []
    try:
        browser.goto(task["start_url"])
    except BrowserError as e:
        return {
            "policy": policy_name, "success": False, "extracted": None,
            "final_url": None, "final_title": None, "steps": [],
            "error": f"failed to load start_url: {e}",
        }

    max_steps = task.get("max_steps", 6)
    for step_i in range(max_steps):
        snap = browser.snapshot
        step_record = {
            "step": step_i,
            "url": browser.url,
            "title": snap.title,
            "snapshot_text": snap.render(),
            "snapshot_tokens": snap.token_count(),
            "raw_html_tokens": estimate_tokens(browser.html),
        }

        try:
            action = policy_fn(browser, task, history)
        except AgentError as e:
            step_record["action"] = {"type": "error", "reason": str(e)}
            steps_log.append(step_record)
            return {
                "policy": policy_name, "success": False, "extracted": None,
                "final_url": browser.url, "final_title": snap.title,
                "steps": steps_log, "error": str(e),
            }

        step_record["action"] = action
        steps_log.append(step_record)
        history.append(action)

        if action["type"] == "done":
            return {
                "policy": policy_name,
                "success": bool(action.get("success")),
                "extracted": action.get("extracted"),
                "final_url": browser.url,
                "final_title": snap.title,
                "steps": steps_log,
                "error": None if action.get("success") else action.get("reason"),
            }

        try:
            if action["type"] == "type":
                browser.type(action["ref"], action["text"])
            elif action["type"] == "click":
                browser.click(action["ref"])
            else:
                raise AgentError(f"unknown action type {action['type']!r}")
        except (BrowserError, AgentError) as e:
            return {
                "policy": policy_name, "success": False, "extracted": None,
                "final_url": browser.url, "final_title": snap.title,
                "steps": steps_log, "error": str(e),
            }

    return {
        "policy": policy_name, "success": False, "extracted": None,
        "final_url": browser.url,
        "final_title": browser.snapshot.title if browser.snapshot else None,
        "steps": steps_log, "error": f"exceeded max_steps={max_steps}",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the barebrowse autonomous agent.")
    parser.add_argument("--task", default="task.json")
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--out", default="run_log.jsonl")
    parser.add_argument("--policy", choices=["auto", "rule", "ollama"], default="auto")
    args = parser.parse_args(argv)

    with open(args.task) as f:
        task = json.load(f)

    policy_name, policy_fn = choose_policy(args.policy, task.get("ollama_model", "llama3.2"))
    print(f"policy: {policy_name}")

    results = []
    with open(args.out, "w") as out:
        for i in range(args.runs):
            result = run_once(task, policy_fn, policy_name)
            result["run"] = i
            results.append(result)
            out.write(json.dumps(result) + "\n")
            status = "OK" if result["success"] else "FAIL"
            print(f"run {i}: {status} extracted={result['extracted']!r} url={result['final_url']}")

    successes = sum(1 for r in results if r["success"])
    print(f"success rate: {successes}/{args.runs} ({100.0 * successes / args.runs:.0f}%)")
    return 0 if successes else 1


if __name__ == "__main__":
    sys.exit(main())
