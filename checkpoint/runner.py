"""Run a self-hosted model as an analyst on a Checkpoint workspace.

The model is served locally through an Ollama-compatible chat endpoint. It is given one tool,
`run_python`, and works until it has written `submission.json`. Every piece of code it writes
is executed inside a macOS sandbox that has no network access, can write only inside the
workspace, and cannot read the sealed benchmark material. Nothing leaves the machine.

    python -m checkpoint.runner --workspace /path/to/workspace --model gemma4:12b

The workspace must contain INSTRUCTIONS.md and the cohort files (a copy of
benchmark/<version>/public plus one of the briefs).
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request

SYSTEM = (
    "You are a careful data analyst. You work by calling the run_python tool, which runs "
    "Python 3 (standard library only; numpy, pandas and scipy are not installed) with the "
    "workspace folder as the current directory and returns what the code printed. There is no "
    "internet access. Read INSTRUCTIONS.md first by printing it. Work in small steps and look at "
    "the output of each step before writing the next. When your analysis is complete, write "
    "submission.json in the current directory in exactly the shape the instructions give, check "
    "that it parses, then reply with the single word DONE and no tool call."
)
TOOLS = [{"type": "function", "function": {
    "name": "run_python",
    "description": "Run Python 3 code in the workspace and return its printed output.",
    "parameters": {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]}}}]


def sandbox_profile(workspace, deny_read):
    rules = ["(version 1)", "(allow default)", "(deny network*)",
             '(deny file-write* (subpath "/"))',
             f'(allow file-write* (subpath "{workspace}"))',
             '(allow file-write* (literal "/dev/null") (literal "/dev/stdout") (literal "/dev/stderr"))']
    rules += [f'(deny file-read* (subpath "{p}"))' for p in deny_read]
    return "\n".join(rules)


def run_code(code, workspace, step, deny_read, timeout=180, limit=6000):
    path = os.path.join(workspace, f"_step_{step:02d}.py")
    with open(path, "w") as fh:
        fh.write(code)
    cmd = ["sandbox-exec", "-p", sandbox_profile(workspace, deny_read), sys.executable, "-I", path]
    try:
        p = subprocess.run(cmd, cwd=workspace, capture_output=True, text=True, timeout=timeout)
        out = p.stdout + (("\n[stderr]\n" + p.stderr) if p.stderr.strip() else "")
    except subprocess.TimeoutExpired:
        out = f"[timed out after {timeout} seconds]"
    out = out.strip() or "[no output]"
    return out if len(out) <= limit else out[:limit] + f"\n[output truncated, {len(out)} characters in total]"


def chat(host, model, messages, options):
    body = json.dumps({"model": model, "messages": messages, "tools": TOOLS, "stream": False,
                       "options": options}).encode()
    req = urllib.request.Request(host.rstrip("/") + "/api/chat", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=1800) as resp:
        return json.load(resp)["message"]


def extract_code(text):
    """Fallback for models that write a fenced code block instead of calling the tool."""
    if "```" not in text:
        return None
    block = text.split("```", 2)[1]
    return block.split("\n", 1)[1] if block.split("\n", 1)[0].strip().lower() in ("python", "py", "") and "\n" in block else block


def run(workspace, model, host="http://127.0.0.1:11434", max_steps=40, deny_read=(), num_ctx=16384, chat_fn=chat, output_limit=6000):
    workspace = os.path.realpath(workspace)
    deny_read = [os.path.realpath(p) for p in deny_read]
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": "Begin. The workspace is your current directory."}]
    log = open(os.path.join(workspace, "transcript.jsonl"), "w")
    started = time.time()
    for step in range(1, max_steps + 1):
        msg = chat_fn(host, model, messages, {"num_ctx": num_ctx, "temperature": 0.2})
        messages.append(msg)
        calls = msg.get("tool_calls") or []
        code = None
        if calls:
            args = calls[0]["function"].get("arguments", {})
            code = (json.loads(args) if isinstance(args, str) else args).get("code")
        elif msg.get("content"):
            code = extract_code(msg["content"])
        log.write(json.dumps({"step": step, "assistant": msg.get("content", ""), "code": code}) + "\n")
        if code is None:
            if os.path.exists(os.path.join(workspace, "submission.json")):
                break
            messages.append({"role": "user", "content": "submission.json does not exist yet. Continue with run_python."})
            continue
        out = run_code(code, workspace, step, deny_read, limit=output_limit)
        log.write(json.dumps({"step": step, "output": out}) + "\n")
        log.flush()
        messages.append({"role": "tool", "content": out} if calls else {"role": "user", "content": "Output:\n" + out})
    log.close()
    done = os.path.exists(os.path.join(workspace, "submission.json"))
    return {"model": model, "steps": step, "seconds": round(time.time() - started), "submission_written": done}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--host", default="http://127.0.0.1:11434")
    ap.add_argument("--max-steps", type=int, default=40)
    ap.add_argument("--num-ctx", type=int, default=16384)
    ap.add_argument("--deny-read", action="append", default=[],
                    help="folder the model's code must not read (repeatable), e.g. the sealed benchmark folder")
    ap.add_argument("--output-limit", type=int, default=6000,
                    help="characters of each step's output returned to the model")
    a = ap.parse_args()
    print(json.dumps(run(a.workspace, a.model, a.host, a.max_steps, a.deny_read, a.num_ctx,
                         output_limit=a.output_limit)))


if __name__ == "__main__":
    main()
